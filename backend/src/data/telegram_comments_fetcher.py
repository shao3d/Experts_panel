import os
import logging
import asyncio
import sys
from datetime import datetime
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, FloodWaitError
from telethon.tl.functions.messages import GetHistoryRequest
from telethon.tl.types import Message
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

# Setup basic logging
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Add parent directory to path for imports
sys.path.append(str(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from src.models.base import SessionLocal
from src.models.post import Post
from src.models.comment import Comment
from src.utils.entities_converter import entities_to_markdown_from_telethon


class SafeTelegramCommentsFetcher:
    def __init__(self, api_id: int, api_hash: str, session_name: str = 'telegram_fetcher'):
        self.api_id = api_id
        self.api_hash = api_hash
        
        # Handle session path
        session_path = os.getenv('TELEGRAM_SESSION_PATH')
        if session_path:
            self.session_path = session_path
            logger.info(f"Using session file from env: {self.session_path}")
        else:
            # Fallback to local directory
            self.session_path = os.path.join(os.getcwd(), session_name)
            logger.info(f"Using default session path: {self.session_path}")

        self.client = TelegramClient(self.session_path, api_id, api_hash)
        self.RECENT_POSTS_DEPTH = 10 # Default depth

    async def _get_channel_entity(self, channel_username: str):
        """Safely resolve channel entity."""
        try:
            if channel_username.startswith('@'):
                channel_username = channel_username[1:]
            entity = await self.client.get_entity(channel_username)
            return entity
        except ValueError:
            logger.error(f"Could not find channel: {channel_username}")
            return None
        except Exception as e:
            logger.error(f"Error resolving channel: {e}")
            return None

    async def fetch_with_retry(self, func, *args, **kwargs):
        """Retry wrapper for FloodWait."""
        MAX_RETRIES = 3
        for attempt in range(MAX_RETRIES):
            try:
                return await func(*args, **kwargs)
            except FloodWaitError as e:
                wait_time = e.seconds + 10
                print(f"⚠️  FloodWait! Waiting {wait_time}s...")
                await asyncio.sleep(wait_time)
            except Exception as e:
                print(f"❌ Error attempt {attempt+1}: {e}")
                if attempt == MAX_RETRIES - 1:
                    raise
                await asyncio.sleep(5)
        return None

    async def get_discussion_replies(self, channel, post_id: int) -> List[Dict[str, Any]]:
        """Get comments for a post."""
        try:
            message = await self.client.get_messages(channel, ids=post_id)
            if not message or not message.replies or not message.replies.comments:
                return []

            comments = []
            async for reply in self.client.iter_messages(channel, reply_to=post_id):
                if reply.message:
                    author_id = None
                    if reply.from_id:
                        if hasattr(reply.from_id, 'user_id'): author_id = str(reply.from_id.user_id)
                        elif hasattr(reply.from_id, 'channel_id'): author_id = str(reply.from_id.channel_id)
                    
                    comment_markdown = entities_to_markdown_from_telethon(reply.message, reply.entities)
                    
                    comments.append({
                        'telegram_comment_id': reply.id,
                        'parent_telegram_message_id': post_id,
                        'content': comment_markdown,
                        'author_name': self._get_author_name(reply),
                        'author_id': author_id,
                        'created_at': reply.date
                    })
            return comments
        except Exception as e:
            if "MsgIdInvalid" not in str(e):
                logger.warning(f"Error getting replies for {post_id}: {e}")
            return []

    def _get_author_name(self, message):
        if message.sender:
            if hasattr(message.sender, 'first_name'):
                name = message.sender.first_name or ''
                if hasattr(message.sender, 'last_name') and message.sender.last_name:
                    name += f' {message.sender.last_name}'
                return name.strip() or 'Unknown'
            if hasattr(message.sender, 'title'):
                return message.sender.title
        return "Unknown"

    def get_posts_from_db(self, db: Session, channel_id: str) -> List[tuple]:
        posts = db.query(Post.post_id, Post.telegram_message_id).filter(
            Post.channel_id == str(channel_id)
        ).order_by(Post.created_at).all()
        return [(p.post_id, p.telegram_message_id) for p in posts]

    def save_comments_to_db(self, db: Session, comments: List[Dict[str, Any]], channel_id: str) -> int:
        saved_count = 0
        for comment_data in comments:
            post = db.query(Post).filter(
                Post.telegram_message_id == comment_data['parent_telegram_message_id'],
                Post.channel_id == str(channel_id)
            ).first()

            if not post: continue

            comment = Comment(
                post_id=post.post_id,
                comment_text=comment_data['content'],
                author_name=comment_data['author_name'],
                author_id=comment_data['author_id'],
                created_at=comment_data['created_at'],
                updated_at=datetime.utcnow(),
                telegram_comment_id=comment_data['telegram_comment_id'],
                parent_telegram_message_id=comment_data['parent_telegram_message_id']
            )

            savepoint = db.begin_nested()
            try:
                db.add(comment)
                db.flush()
            except IntegrityError:
                savepoint.rollback()
                # Safe expunge
                try:
                    db.expunge(comment)
                except:
                    pass
                continue
            else:
                savepoint.commit()
                saved_count += 1
        return saved_count

    async def fetch_all_comments(self, channel_username: str, channel_id: str = None):
        """
        Fetch comments.
        channel_id is optional filter.
        """
        print(f"\n📱 Connecting to Telegram...")
        self.client = TelegramClient(self.session_path, self.api_id, self.api_hash)
        await self.client.start()
        print("✅ Connected!")

        try:
            channel = await self.client.get_entity(channel_username)
            print(f"✅ Found channel: {channel.title} ({channel.id})")
        except Exception as e:
            print(f"❌ Channel not found: {e}")
            return

        # If interactive mode (no channel_id passed), use the resolved one
        target_channel_id = str(channel.id)
        if channel_id and str(channel_id) != target_channel_id:
             print(f"⚠️ Channel ID mismatch! Expected {channel_id}, got {target_channel_id}")
        
        # Use the real ID for DB lookups
        db_channel_id = target_channel_id

        print("\n📊 Fetching posts from DB...")
        db = SessionLocal()
        try:
            posts = self.get_posts_from_db(db, db_channel_id)
            print(f"✅ Found {len(posts)} posts in DB")
            
            for i, (post_id, telegram_message_id) in enumerate(posts, 1):
                print(f"[{i}/{len(posts)}] Post #{telegram_message_id}...", end=' ', flush=True)
                comments = await self.fetch_with_retry(self.get_discussion_replies, channel, telegram_message_id)
                
                if comments:
                    print(f"✅ {len(comments)} comments")
                    self.save_comments_to_db(db, comments, db_channel_id)
                    db.commit()
                else:
                    print("—")
                
                await asyncio.sleep(1) # Rate limit
                
        finally:
            db.close()
            await self.client.disconnect()

async def main():
    """Interactive CLI entry point."""
    load_dotenv()
    
    print("\n" + "="*60)
    print("🤖 Telegram Comments Fetcher - Interactive Mode")
    print("="*60 + "\n")

    api_id = os.getenv("TELEGRAM_API_ID") or input("API_ID: ")
    api_hash = os.getenv("TELEGRAM_API_HASH") or input("API_HASH: ")
    channel_username = os.getenv("TELEGRAM_CHANNEL") or input("Channel: ")
    
    if not api_id or not api_hash: return

    try:
        api_id = int(api_id)
    except ValueError: return

    if input("\n❓ Start import? (y/n): ").lower() != 'y': return

    fetcher = SafeTelegramCommentsFetcher(api_id, api_hash)
    await fetcher.fetch_all_comments(channel_username) # channel_id is optional now!

if __name__ == "__main__":
    asyncio.run(main())