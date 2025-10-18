"""JSON parser for Telegram channel exports."""

import json
import argparse
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from models import SessionLocal, Post, Link, LinkType
from models.database import init_db
from utils.entities_converter import entities_to_markdown_from_json


class TelegramJsonParser:
    """Parser for Telegram JSON export files."""

    def __init__(self, session, expert_id: str):
        """Initialize parser with database session.

        Args:
            session: Database session
            expert_id: Expert identifier (e.g., 'refat', 'ai_architect')
        """
        self.session = session
        self.expert_id = expert_id
        self.stats = {
            'posts_imported': 0,
            'links_created': 0,
            'errors': 0,
            'skipped': 0
        }
        # Track posts by telegram_message_id for link resolution
        self.post_id_map = {}

    def parse_file(self, json_path: str) -> Dict[str, int]:
        """Parse Telegram JSON export file and import to database."""
        print(f"Parsing file: {json_path}")

        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            print(f"Error reading JSON file: {e}")
            return self.stats

        # Extract channel/chat info
        channel_info = self._extract_channel_info(data)

        # Parse messages
        messages = data.get('messages', [])
        total = len(messages)
        print(f"Found {total} messages to import")

        # Process in batches for better performance
        batch_size = 100
        for i in range(0, total, batch_size):
            batch = messages[i:i+batch_size]
            self._process_message_batch(batch, channel_info)

            # Show progress
            progress = min(i + batch_size, total)
            percent = (progress / total) * 100
            print(f"Progress: {progress}/{total} ({percent:.1f}%)")

        # Commit all changes
        try:
            self.session.commit()
            print("✅ Import completed successfully!")
        except Exception as e:
            print(f"Error committing changes: {e}")
            self.session.rollback()
            self.stats['errors'] += 1

        # Create links after all posts are imported
        self._create_links(messages)

        return self.stats

    def _extract_channel_info(self, data: Dict) -> Dict[str, str]:
        """Extract channel/chat information from JSON."""
        return {
            'channel_id': str(data.get('id', 'unknown')),
            'channel_name': data.get('name', data.get('title', 'Unknown Channel')),
            'type': data.get('type', 'channel')
        }

    def _process_message_batch(self, messages: List[Dict], channel_info: Dict):
        """Process a batch of messages."""
        for msg in messages:
            try:
                post = self._message_to_post(msg, channel_info)
                if post:
                    self.session.add(post)
                    self.session.flush()  # Get the post_id

                    # Map telegram message ID to our post_id for link resolution
                    if msg.get('id'):
                        self.post_id_map[msg['id']] = post.post_id

                    self.stats['posts_imported'] += 1
            except Exception as e:
                print(f"Error processing message {msg.get('id', 'unknown')}: {e}")
                self.stats['errors'] += 1

    def _message_to_post(self, msg: Dict, channel_info: Dict) -> Optional[Post]:
        """Convert Telegram message to Post model."""
        # Skip service messages
        if msg.get('type') != 'message':
            self.stats['skipped'] += 1
            return None

        # Extract text content
        text = self._extract_text(msg)
        if not text and not msg.get('media_type'):
            self.stats['skipped'] += 1
            return None

        # Parse timestamps
        created_at = self._parse_timestamp(msg.get('date'))
        edited_at = self._parse_timestamp(msg.get('edited'))

        # Extract media metadata
        media_metadata = self._extract_media_metadata(msg)

        # Create Post object
        post = Post(
            channel_id=channel_info['channel_id'],
            channel_name=channel_info['channel_name'],
            telegram_message_id=msg.get('id'),
            expert_id=self.expert_id,
            message_text=text,
            author_name=msg.get('from', msg.get('author', '')),
            author_id=msg.get('from_id', ''),
            created_at=created_at,
            edited_at=edited_at,
            view_count=msg.get('views', 0),
            forward_count=msg.get('forwards', 0),
            media_metadata=media_metadata,
            is_forwarded=1 if msg.get('forwarded_from') else 0,
            forward_from_channel=msg.get('forwarded_from')
        )

        return post

    def _extract_text(self, msg: Dict) -> str:
        """Extract text content from message and convert entities to markdown."""
        text = msg.get('text', '')

        # Convert entities to markdown using the utility function
        markdown_text = entities_to_markdown_from_json(text)

        return markdown_text.strip() if markdown_text else ''

    def _parse_timestamp(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse Telegram timestamp format."""
        if not date_str:
            return None

        try:
            # Telegram uses ISO format: "2023-01-01T12:00:00"
            return datetime.fromisoformat(date_str.replace('T', ' '))
        except:
            try:
                # Alternative format
                return datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
            except:
                return None

    def _extract_media_metadata(self, msg: Dict) -> Optional[Dict]:
        """Extract media metadata from message."""
        media_type = msg.get('media_type')
        if not media_type:
            return None

        metadata = {
            'type': media_type,
            'mime_type': msg.get('mime_type'),
            'file': msg.get('file'),
            'file_name': msg.get('file_name'),
            'duration': msg.get('duration_seconds'),
            'width': msg.get('width'),
            'height': msg.get('height'),
            'thumbnail': msg.get('thumbnail')
        }

        # Remove None values
        metadata = {k: v for k, v in metadata.items() if v is not None}

        return metadata if metadata else None

    def _create_links(self, messages: List[Dict]):
        """Create Link records for replies, forwards, and text links."""
        print("\nCreating links between posts...")
        import re

        for msg in messages:
            # Skip non-messages
            if msg.get('type') != 'message' or msg.get('id') not in self.post_id_map:
                continue

            source_post_id = self.post_id_map[msg['id']]

            # Handle replies
            reply_to = msg.get('reply_to_message_id')
            if reply_to and reply_to in self.post_id_map:
                target_post_id = self.post_id_map[reply_to]
                self._create_link(source_post_id, target_post_id, LinkType.REPLY)

            # Handle text_link elements (links in text to other posts)
            text = msg.get('text')
            if isinstance(text, list):
                for item in text:
                    if isinstance(item, dict) and item.get('type') == 'text_link':
                        href = item.get('href', '')
                        # Extract post ID from t.me links (e.g., https://t.me/channelname/123)
                        match = re.search(r't\.me/[\w]+/(\d+)', href)
                        if match:
                            linked_msg_id = int(match.group(1))
                            if linked_msg_id in self.post_id_map:
                                target_post_id = self.post_id_map[linked_msg_id]
                                self._create_link(source_post_id, target_post_id, LinkType.MENTION)

            # Handle forwards (if we want to track them as links)
            if msg.get('forwarded_from'):
                # For now, we just store the forward source in the post
                # Could create links if we have the original posts
                pass

        try:
            self.session.commit()
            print(f"✅ Created {self.stats['links_created']} links")
        except Exception as e:
            print(f"Error creating links: {e}")
            self.session.rollback()

    def _create_link(self, source_id: int, target_id: int, link_type: LinkType):
        """Create a link between two posts."""
        # Check if link already exists
        existing = self.session.query(Link).filter(
            Link.source_post_id == source_id,
            Link.target_post_id == target_id,
            Link.link_type == link_type.value
        ).first()

        if existing:
            return  # Skip duplicate

        try:
            link = Link(
                source_post_id=source_id,
                target_post_id=target_id,
                link_type=link_type.value,
                created_at=datetime.utcnow()
            )
            self.session.add(link)
            self.session.flush()  # Flush to catch constraint errors immediately
            self.stats['links_created'] += 1
        except Exception as e:
            self.session.rollback()
            # Ignore duplicate link errors
            if 'UNIQUE constraint failed' not in str(e):
                print(f"Error creating link: {e}")


def main():
    """CLI interface for JSON parser."""
    parser = argparse.ArgumentParser(description='Import Telegram JSON exports to database')
    parser.add_argument('json_file', help='Path to Telegram JSON export file')
    parser.add_argument('--init-db', action='store_true',
                       help='Initialize database before import')
    parser.add_argument('--dry-run', action='store_true',
                       help='Parse without saving to database')
    parser.add_argument('--expert-id', required=True,
                       help='Expert identifier (e.g., refat, ai_architect)')

    args = parser.parse_args()

    # Validate file exists
    if not Path(args.json_file).exists():
        print(f"Error: File not found: {args.json_file}")
        return 1

    # Initialize database if requested
    if args.init_db:
        print("Initializing database...")
        init_db()

    # Create database session
    session = SessionLocal()

    try:
        # Parse and import
        parser = TelegramJsonParser(session, expert_id=args.expert_id)
        stats = parser.parse_file(args.json_file)

        # Print statistics
        print("\n" + "="*50)
        print("Import Statistics:")
        print(f"  Posts imported: {stats['posts_imported']}")
        print(f"  Links created: {stats['links_created']}")
        print(f"  Messages skipped: {stats['skipped']}")
        print(f"  Errors: {stats['errors']}")
        print("="*50)

    finally:
        session.close()

    return 0


if __name__ == "__main__":
    exit(main())