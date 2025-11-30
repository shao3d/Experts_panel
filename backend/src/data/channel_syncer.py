"""
Telegram Channel Syncer
Incremental sync of Telegram channel posts and comments.

Usage:
    from src.data.channel_syncer import TelegramChannelSyncer

    syncer = TelegramChannelSyncer(api_id, api_hash, session_name)
    result = await syncer.sync_channel_incremental(channel_username, dry_run=False)
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
import os
import logging

from telethon import TelegramClient
from telethon.errors import FloodWaitError, ChannelPrivateError
from telethon.tl.types import Message
from sqlalchemy.orm import Session
from sqlalchemy import text

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from models.base import SessionLocal
from models.post import Post
from models.comment import Comment
from models.link import Link, LinkType
from data.telegram_comments_fetcher import SafeTelegramCommentsFetcher
from utils.entities_converter import entities_to_markdown_from_telethon


logger = logging.getLogger(__name__)


class TelegramChannelSyncer(SafeTelegramCommentsFetcher):
    """
    Extends SafeTelegramCommentsFetcher with incremental sync capabilities.

    Features:
    - Fetch new posts since last sync (incremental)
    - Update comments for recent posts (depth=N)
    - Track sync state in database
    - Calculate new comment groups needing drift analysis
    """

    RECENT_POSTS_DEPTH = 10  # Check last 10 posts for new comments (~30 days)

    def __init__(self, api_id: int, api_hash: str, session_name: str = 'telegram_fetcher'):
        """Initialize syncer with Telegram credentials."""
        super().__init__(api_id, api_hash, session_name)
        self.stats = {
            'new_posts_found': 0,
            'new_posts_saved': 0,
            'posts_updated': 0,
            'new_comments_found': 0,
            'new_comments_saved': 0,
            'errors': 0,
            'duration_seconds': 0
        }

    async def sync_channel_incremental(
        self,
        channel_username: str,
        expert_id: str,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Fetch new posts and comments since last sync.

        Args:
            channel_username: Channel to sync (e.g., 'nobilix')
            expert_id: Expert identifier (e.g., 'refat', 'ai_architect')
            dry_run: If True, don't save to database

        Returns:
            {
                "success": bool,
                "new_posts": List[int],  # telegram_message_ids
                "updated_posts": List[int],
                "new_comment_groups": List[int],
                "stats": {...},
                "errors": List[str]
            }
        """
        start_time = datetime.utcnow()
        errors = []
        new_posts = []
        updated_posts = []

        print("=" * 60)
        print("🔄 Telegram Channel Sync")
        print("=" * 60)
        print(f"Mode: {'DRY-RUN' if dry_run else 'LIVE'}")
        print(f"Channel: {channel_username}")
        print()

        # Connect to Telegram
        print("📱 Connecting to Telegram...")
        self.client = TelegramClient(self.session_name, self.api_id, self.api_hash)
        await self.client.start()
        print("✅ Connected!")

        # Get channel entity
        print(f"\n🔍 Finding channel: {channel_username}")
        try:
            channel = await self.client.get_entity(channel_username)
            print(f"✅ Found: {channel.title}")
        except Exception as e:
            error_msg = f"Cannot find channel {channel_username}: {e}"
            print(f"❌ {error_msg}")
            errors.append(error_msg)
            return self._build_result(False, new_posts, updated_posts, [], errors, start_time)

        # Open database
        db = SessionLocal()
        try:
            # Get last synced message ID
            last_synced_id = self._get_last_synced_id(db, channel_username)
            print(f"\n📊 Last synced message ID: {last_synced_id or 'None (first sync)'}")

            # Fetch new posts
            print(f"\n📥 Fetching new posts (min_id={last_synced_id or 0})...")
            new_posts_data = await self._fetch_new_posts(channel, last_synced_id)
            self.stats['new_posts_found'] = len(new_posts_data)
            print(f"✅ Found {len(new_posts_data)} new posts")

            if new_posts_data:
                # Save new posts to database
                if not dry_run:
                    new_posts = self._save_posts_to_db(db, new_posts_data, channel, expert_id)
                    self.stats['new_posts_saved'] = len(new_posts)
                    db.commit()  # Commit now so new posts are visible to next query
                    print(f"✅ Saved {len(new_posts)} new posts")
                else:
                    new_posts = [p['telegram_message_id'] for p in new_posts_data]
                    print(f"[DRY-RUN] Would save {len(new_posts)} posts")

            # OPTIMIZATION RATIONALE:
            # The original logic updated comments in two separate, redundant steps:
            # 1. For the N most recent posts.
            # 2. For all newly fetched posts.
            # This was inefficient because new posts could also be in the "recent"
            # list, leading to them being processed twice.
            #
            # This updated logic is more optimal:
            # 1. It gets a single, unique list of post IDs from both new and recent posts.
            # 2. It makes only one consolidated call to `update_specific_posts_comments`
            #    to process all required posts at once.
            # This avoids redundant API calls and processing, and simplifies the code
            # by allowing the removal of the `update_recent_posts_comments` method.

            # Combine new posts with recent posts to update comments in one go
            # 1. Get recent posts from DB
            recent_posts_query = db.query(Post.telegram_message_id) \
                .filter(Post.expert_id == expert_id) \
                .order_by(Post.telegram_message_id.desc()) \
                .limit(self.RECENT_POSTS_DEPTH)
            recent_post_ids = [p[0] for p in recent_posts_query.all()]

            # 2. Combine new post IDs with recent post IDs, no duplicates
            post_ids_to_update = sorted(list(set(new_posts + recent_post_ids)), reverse=True)

            # 3. Update comments for all these posts
            if post_ids_to_update:
                print(f"\n🔄 Updating comments for {len(post_ids_to_update)} posts (new + recent)...")
                update_result = await self.update_specific_posts_comments(
                    db=db,
                    channel_username=channel_username,
                    expert_id=expert_id,
                    telegram_message_ids=post_ids_to_update,
                    dry_run=dry_run
                )
                updated_posts = update_result.get('updated_posts', [])
                self.stats['posts_updated'] = len(updated_posts)
                self.stats['new_comments_found'] += update_result.get('stats', {}).get('comments_found', 0)
                self.stats['new_comments_saved'] += update_result.get('stats', {}).get('comments_saved', 0)
            else:
                print("\n🔄 No new or recent posts to check for comments.")
                updated_posts = []

            # Update sync state
            if not dry_run and new_posts:
                max_message_id = max(new_posts)
                self._update_sync_state(db, channel_username, max_message_id)
                print(f"✅ Updated sync state: last_synced_message_id = {max_message_id}")

            # Calculate new comment groups needing drift analysis for this expert
            new_comment_groups = self.calculate_new_comment_groups(db, expert_id)
            print(f"\n🎯 Comment groups needing drift analysis: {len(new_comment_groups)}")

            # Commit all changes
            if not dry_run:
                db.commit()
                print("✅ Database committed")

            # Calculate duration
            duration = (datetime.utcnow() - start_time).total_seconds()
            self.stats['duration_seconds'] = duration

            print(f"\n✅ Sync complete! Duration: {duration:.1f}s")

            return self._build_result(True, new_posts, updated_posts, new_comment_groups, errors, start_time)

        except Exception as e:
            db.rollback()
            error_msg = f"Sync failed: {e}"
            print(f"\n❌ {error_msg}")
            errors.append(error_msg)
            self.stats['errors'] += 1
            return self._build_result(False, new_posts, updated_posts, [], errors, start_time)
        finally:
            db.close()
            await self.client.disconnect()

  
    async def update_specific_posts_comments(
        self,
        db: Session,
        channel_username: str,
        expert_id: str,
        telegram_message_ids: List[int],
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Refresh comments for specific posts by telegram_message_ids.

        Args:
            db: Database session
            channel_username: Channel to sync
            expert_id: Expert identifier for filtering posts
            telegram_message_ids: List of specific telegram_message_ids to check
            dry_run: If True, don't save to database

        Returns:
            {
                "updated_posts": List[int],  # telegram_message_ids
                "stats": {"comments_found": int, "comments_saved": int}
            }
        """
        updated_posts = []
        comments_found = 0
        comments_saved = 0

        if not telegram_message_ids:
            return {"updated_posts": [], "stats": {"comments_found": 0, "comments_saved": 0}}

        # Get posts from database for these telegram_message_ids
        posts_data = db.query(Post.post_id, Post.telegram_message_id, Post.channel_id)\
            .filter(Post.expert_id == expert_id)\
            .filter(Post.telegram_message_id.in_(telegram_message_ids))\
            .all()

        if not posts_data:
            return {"updated_posts": [], "stats": {"comments_found": 0, "comments_saved": 0}}

        # Get channel entity
        channel = await self.client.get_entity(channel_username)

        # Create a dict for quick lookup
        posts_dict = {msg_id: (post_id, channel_id) for post_id, msg_id, channel_id in posts_data}

        # Fetch comments for each specific post
        for telegram_message_id in telegram_message_ids:
            if telegram_message_id not in posts_dict:
                continue  # Skip if not found in DB

            post_id, channel_id = posts_dict[telegram_message_id]
            print(f"  📝 New Post #{telegram_message_id}...", end=" ")

            comments = await self.get_discussion_replies(channel, telegram_message_id)
            comments_found += len(comments)

            if comments:
                if not dry_run:
                    logger.debug(
                        "Saving %s comments for post %s (channel %s)",
                        len(comments),
                        telegram_message_id,
                        channel_id,
                    )

                    # Save comments with proper channel_id filtering
                    saved = self.save_comments_to_db(db, comments, channel_id)
                    logger.debug(
                        "Saved %s/%s comments for post %s",
                        saved,
                        len(comments),
                        telegram_message_id,
                    )
                    
                    comments_saved += saved
                    db.commit()
                    if saved == len(comments):
                        print(f"✅ {saved} comments")
                    elif saved > 0:
                        print(f"✅ {saved}/{len(comments)} comments (skipped {len(comments) - saved} duplicates)")
                    else:
                        print(f"⚠️  0/{len(comments)} comments (all duplicates)")
                    
                    # Only mark post as updated if NEW comments were actually saved
                    if saved > 0:
                        updated_posts.append(telegram_message_id)
                else:
                    print(f"[DRY-RUN] Would save {len(comments)} comments")
                    updated_posts.append(telegram_message_id)
            else:
                print("No comments")

            # Rate limiting
            await asyncio.sleep(self.DELAY_BETWEEN_POSTS)

        return {
            "updated_posts": updated_posts,
            "stats": {
                "comments_found": comments_found,
                "comments_saved": comments_saved
            }
        }

    def calculate_new_comment_groups(self, db: Session, expert_id: str) -> List[int]:
        """
        Find posts with new comments that need drift analysis for specific expert.

        Args:
            db: Database session
            expert_id: Expert identifier to filter posts

        Returns:
            List of post_ids that need drift analysis (new comments since last sync)
        """
        # Find posts with comments but no drift records OR posts that need drift analysis reset
        query = text("""
            SELECT DISTINCT c.post_id
            FROM comments c
            JOIN posts p ON c.post_id = p.post_id
            LEFT JOIN comment_group_drift cgd ON c.post_id = cgd.post_id
            WHERE c.telegram_comment_id IS NOT NULL
              AND p.expert_id = :expert_id
              AND (
                cgd.post_id IS NULL  -- No drift record exists
                OR cgd.analyzed_by != 'pending'  -- Already analyzed, needs reset for new comments
              )
            GROUP BY c.post_id
            HAVING COUNT(c.comment_id) >= 1
            ORDER BY c.post_id
        """)

        result = db.execute(query, {"expert_id": expert_id})
        post_ids = [row[0] for row in result.fetchall()]
        return post_ids

    async def _fetch_new_posts(
        self,
        channel,
        min_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch new posts from Telegram channel.

        Args:
            channel: Telegram channel entity
            min_id: Only fetch messages with ID > min_id

        Returns:
            List of post data dicts
        """
        posts = []

        async for message in self.client.iter_messages(
            entity=channel,
            min_id=min_id or 0,
            reverse=True,  # Chronological order (oldest first)
            limit=None     # All new messages
        ):
            if not message.message:  # Skip non-text messages
                continue

            # Extract author info
            author_name = self._get_author_name(message)
            author_id = None
            if message.from_id:
                if hasattr(message.from_id, 'user_id'):
                    author_id = str(message.from_id.user_id)
                elif hasattr(message.from_id, 'channel_id'):
                    author_id = str(message.from_id.channel_id)

            # Extract forward info
            is_forwarded = 0
            forward_from_channel = None
            if message.forward:
                is_forwarded = 1
                if hasattr(message.forward, 'from_id') and hasattr(message.forward.from_id, 'channel_id'):
                    forward_from_channel = str(message.forward.from_id.channel_id)

            # Convert message entities to markdown
            message_markdown = entities_to_markdown_from_telethon(
                message.message,
                message.entities
            )

            posts.append({
                'telegram_message_id': message.id,
                'message_text': message_markdown,
                'author_name': author_name,
                'author_id': author_id,
                'created_at': message.date,
                'edited_at': message.edit_date,
                'view_count': message.views or 0,
                'forward_count': message.forwards or 0,
                'reply_count': message.replies.replies if message.replies else 0,
                'is_forwarded': is_forwarded,
                'forward_from_channel': forward_from_channel,
                'reply_to_msg_id': message.reply_to.reply_to_msg_id if message.reply_to else None
            })

            # Rate limiting
            await asyncio.sleep(self.DELAY_BETWEEN_POSTS)

        return posts

    def _save_posts_to_db(
        self,
        db: Session,
        posts_data: List[Dict[str, Any]],
        channel,
        expert_id: str
    ) -> List[int]:
        """
        Save posts to database.

        Args:
            db: Database session
            posts_data: List of post data dicts
            channel: Telegram channel entity
            expert_id: Expert identifier

        Returns:
            List of saved telegram_message_ids
        """
        saved_ids = []

        for post_data in posts_data:
            # Create Post record
            post = Post(
                channel_id=str(channel.id),
                channel_name=channel.title,
                telegram_message_id=post_data['telegram_message_id'],
                expert_id=expert_id,
                message_text=post_data['message_text'],
                author_name=post_data['author_name'],
                author_id=post_data['author_id'],
                created_at=post_data['created_at'],
                edited_at=post_data['edited_at'],
                view_count=post_data['view_count'],
                forward_count=post_data['forward_count'],
                reply_count=post_data['reply_count'],
                is_forwarded=post_data['is_forwarded'],
                forward_from_channel=post_data['forward_from_channel']
            )

            db.add(post)
            db.flush()  # Get post_id

            # Create REPLY link if this is a reply
            if post_data['reply_to_msg_id']:
                target_post = db.query(Post).filter(
                    Post.telegram_message_id == post_data['reply_to_msg_id']
                ).first()

                if target_post:
                    link = Link(
                        source_post_id=post.post_id,
                        target_post_id=target_post.post_id,
                        link_type=LinkType.REPLY.value,
                        created_at=datetime.utcnow()
                    )
                    db.add(link)

            saved_ids.append(post_data['telegram_message_id'])

        return saved_ids

    def _get_last_synced_id(self, db: Session, channel_username: str) -> Optional[int]:
        """Get last synced message ID from sync_state table."""
        result = db.execute(
            text("SELECT last_synced_message_id FROM sync_state WHERE channel_username = :channel"),
            {"channel": channel_username}
        ).fetchone()

        return result[0] if result else None

    def _update_sync_state(
        self,
        db: Session,
        channel_username: str,
        max_message_id: int
    ):
        """Update sync state with new max message ID."""
        # Check if record exists
        exists = db.execute(
            text("SELECT 1 FROM sync_state WHERE channel_username = :channel"),
            {"channel": channel_username}
        ).fetchone()

        if exists:
            db.execute(
                text("""UPDATE sync_state
                        SET last_synced_message_id = :max_id,
                            last_synced_at = :now,
                            total_posts_synced = total_posts_synced + :new_posts,
                            total_comments_synced = total_comments_synced + :new_comments
                        WHERE channel_username = :channel"""),
                {
                    "max_id": max_message_id,
                    "now": datetime.utcnow(),
                    "new_posts": self.stats['new_posts_saved'],
                    "new_comments": self.stats['new_comments_saved'],
                    "channel": channel_username
                }
            )
        else:
            db.execute(
                text("""INSERT INTO sync_state
                        (channel_username, last_synced_message_id, last_synced_at, total_posts_synced, total_comments_synced)
                        VALUES (:channel, :max_id, :now, :new_posts, :new_comments)"""),
                {
                    "channel": channel_username,
                    "max_id": max_message_id,
                    "now": datetime.utcnow(),
                    "new_posts": self.stats['new_posts_saved'],
                    "new_comments": self.stats['new_comments_saved']
                }
            )

    def _build_result(
        self,
        success: bool,
        new_posts: List[int],
        updated_posts: List[int],
        new_comment_groups: List[int],
        errors: List[str],
        start_time: datetime
    ) -> Dict[str, Any]:
        """Build standardized result dictionary."""
        duration = (datetime.utcnow() - start_time).total_seconds()
        self.stats['duration_seconds'] = duration

        return {
            "success": success,
            "new_posts": new_posts,
            "updated_posts": updated_posts,
            "new_comment_groups": new_comment_groups,
            "stats": {
                "total_posts": len(new_posts),
                "total_comments": self.stats['new_comments_saved'],
                "groups_need_drift": len(new_comment_groups),
                "duration_seconds": duration
            },
            "errors": errors
        }
