"""
Telegram Comments Fetcher
Безопасное получение комментариев из Telegram Discussion Group с защитой от бана.

Usage:
    python -m src.data.telegram_comments_fetcher
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

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from models.base import SessionLocal
from models.post import Post
from models.comment import Comment
from utils.entities_converter import entities_to_markdown_from_telethon


logger = logging.getLogger(__name__)


class SafeTelegramCommentsFetcher:
    """
    Безопасное получение комментариев из Telegram с rate limiting.
    """

    # Rate limiting настройки
    DELAY_BETWEEN_POSTS = 2.0  # 2 секунды между постами
    MAX_RETRIES = 3
    BATCH_COMMIT_SIZE = 50  # Коммитить каждые 50 комментариев

    def __init__(self, api_id: int, api_hash: str, session_name: str = 'telegram_fetcher'):
        """
        Initialize fetcher.

        Args:
            api_id: Telegram API ID from my.telegram.org
            api_hash: Telegram API Hash from my.telegram.org
            session_name: Session file name (будет создан .session файл)
        """
        self.api_id = api_id
        self.api_hash = api_hash
        self.session_name = session_name
        self.client = None
        self.stats = {
            'posts_processed': 0,
            'comments_found': 0,
            'comments_saved': 0,
            'errors': 0
        }

    async def fetch_with_retry(self, func, *args, **kwargs):
        """
        Выполняет функцию с retry при FloodWait.

        Args:
            func: Async функция для выполнения
            *args, **kwargs: Аргументы для функции

        Returns:
            Результат функции
        """
        for attempt in range(self.MAX_RETRIES):
            try:
                return await func(*args, **kwargs)
            except FloodWaitError as e:
                wait_time = e.seconds + 10  # +10 сек для безопасности
                print(f"⚠️  FloodWait! Telegram просит подождать {wait_time} секунд...")
                print(f"   Это нормально, ждём и продолжаем...")
                await asyncio.sleep(wait_time)
            except Exception as e:
                print(f"❌ Ошибка на попытке {attempt + 1}/{self.MAX_RETRIES}: {e}")
                if attempt == self.MAX_RETRIES - 1:
                    raise
                await asyncio.sleep(5 * (attempt + 1))

        return None

    async def get_discussion_replies(
        self,
        channel,
        post_id: int
    ) -> List[Dict[str, Any]]:
        """
        Получает комментарии Discussion Group для поста.

        Args:
            channel: Telegram channel entity
            post_id: ID поста (telegram_message_id)

        Returns:
            Список комментариев
        """
        try:
            # Получаем пост
            message = await self.client.get_messages(channel, ids=post_id)

            if not message or not hasattr(message, 'replies') or not message.replies:
                return []

            # Получаем Discussion Group
            if not message.replies.comments:
                return []

            # Получаем все комментарии
            comments = []
            async for reply in self.client.iter_messages(
                channel,
                reply_to=post_id,
                limit=None  # Все комментарии
            ):
                if reply.message:  # Только текстовые сообщения
                    # Получить author_id в зависимости от типа
                    author_id = None
                    if reply.from_id:
                        if hasattr(reply.from_id, 'user_id'):
                            author_id = str(reply.from_id.user_id)
                        elif hasattr(reply.from_id, 'channel_id'):
                            author_id = str(reply.from_id.channel_id)
                        elif hasattr(reply.from_id, 'chat_id'):
                            author_id = str(reply.from_id.chat_id)

                    # Convert comment entities to markdown
                    comment_markdown = entities_to_markdown_from_telethon(
                        reply.message,
                        reply.entities
                    )

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
            error_msg = str(e)

            # If it's just "no comments", that's OK
            if "no attribute 'replies'" in error_msg or "replies.comments" in error_msg:
                return []

            # If it's invalid message ID - just skip this post
            if "MsgIdInvalid" in error_msg or "invalid" in error_msg.lower():
                print(f"⚠️  (пропускаем - service message)")
                return []

            # Other errors - also skip and continue
            print(f"⚠️  (ошибка: {e})")
            return []

    def _get_author_name(self, message: Message) -> str:
        """Извлекает имя автора из сообщения."""
        if hasattr(message, 'sender') and message.sender:
            sender = message.sender
            if hasattr(sender, 'first_name'):
                name = sender.first_name or ''
                if hasattr(sender, 'last_name') and sender.last_name:
                    name += f' {sender.last_name}'
                return name.strip() or 'Unknown'
            elif hasattr(sender, 'title'):
                return sender.title
        return 'Unknown'

    def get_posts_from_db(self, db: Session, channel_id: str) -> List[tuple]:
        """
        Получает список постов из БД для указанного канала.

        Args:
            db: Database session
            channel_id: Telegram channel ID для фильтрации

        Returns:
            List of (post_id, telegram_message_id) tuples
        """
        # Filter posts by channel_id to avoid MsgIdInvalidError and ensure multi-expert support
        posts = db.query(Post.post_id, Post.telegram_message_id).filter(
            Post.channel_id == channel_id  # Параметризованный channel_id
        ).order_by(Post.created_at).all()
        return [(p.post_id, p.telegram_message_id) for p in posts]

    def save_comments_to_db(self, db: Session, comments: List[Dict[str, Any]], channel_id: str) -> int:
        """
        Сохраняет комментарии в БД для указанного канала.

        Args:
            db: Database session
            comments: Список комментариев для сохранения
            channel_id: Telegram channel ID для фильтрации

        Returns:
            Количество реально сохраненных комментариев (без дубликатов)
        """
        from sqlalchemy.exc import IntegrityError

        saved_count = 0
        for comment_data in comments:
            # Найти post_id по telegram_message_id AND channel_id
            # CRITICAL: Filter by channel_id to avoid saving comments to wrong expert's posts
            post = db.query(Post).filter(
                Post.telegram_message_id == comment_data['parent_telegram_message_id'],
                Post.channel_id == channel_id  # Параметризованный channel_id
            ).first()

            if not post:
                continue

            # Создать Comment
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

            # Use a SAVEPOINT per comment so duplicates don't roll back the whole batch
            savepoint = db.begin_nested()
            try:
                db.add(comment)
                db.flush()  # Проверить UNIQUE constraint сразу
            except IntegrityError:
                from sqlalchemy.exc import InvalidRequestError
                savepoint.rollback()
                try:
                    db.expunge(comment)
                except InvalidRequestError:
                    pass  # Object уже выгружен из сессии
                logger.debug(
                    "Duplicate telegram_comment_id=%s for post_id=%s",
                    comment.telegram_comment_id,
                    comment.post_id,
                )
                continue
            else:
                savepoint.commit()
                saved_count += 1
                logger.debug(
                    "Saved telegram_comment_id=%s for post_id=%s",
                    comment.telegram_comment_id,
                    comment.post_id,
                )

        return saved_count

    async def fetch_all_comments(
        self,
        channel_username: str,
        channel_id: str
    ) -> Dict[str, int]:
        """
        Основная функция получения всех комментариев для указанного канала.

        Args:
            channel_username: Username канала (например: 'nobilix' или 'the_ai_architect')
            channel_id: Telegram channel ID для фильтрации постов

        Returns:
            Статистика импорта
        """
        print("=" * 60)
        print("🚀 Telegram Comments Fetcher")
        print("=" * 60)

        # Подключение к Telegram
        print("\n📱 Подключение к Telegram...")
        self.client = TelegramClient(self.session_name, self.api_id, self.api_hash)
        await self.client.start()
        print("✅ Подключено!")

        # Получить канал
        print(f"\n🔍 Поиск канала: {channel_username}")
        try:
            channel = await self.client.get_entity(channel_username)
            print(f"✅ Найден: {channel.title}")
        except Exception as e:
            print(f"❌ Ошибка: не могу найти канал {channel_username}")
            print(f"   {e}")
            return self.stats

        # Получить список постов из БД
        print("\n📊 Получение списка постов из БД...")
        db = SessionLocal()
        try:
            posts = self.get_posts_from_db(db, channel_id)
            print(f"✅ Найдено {len(posts)} постов в БД")

            # Оценка времени
            estimated_minutes = (len(posts) * self.DELAY_BETWEEN_POSTS) / 60
            print(f"⏱️  Примерное время: {estimated_minutes:.1f} минут")
            print(f"   (с учётом задержек {self.DELAY_BETWEEN_POSTS}с между постами)")

            print("\n" + "=" * 60)
            print("🔄 Начинаю импорт комментариев...")
            print("=" * 60 + "\n")

            # Обработка постов
            batch_comments = []

            for i, (post_id, telegram_message_id) in enumerate(posts, 1):
                print(f"[{i}/{len(posts)}] Пост #{telegram_message_id}...", end=' ')

                # Получить комментарии с retry
                comments = await self.fetch_with_retry(
                    self.get_discussion_replies,
                    channel,
                    telegram_message_id
                )

                if comments:
                    print(f"✅ {len(comments)} комментариев")
                    batch_comments.extend(comments)
                    self.stats['comments_found'] += len(comments)
                else:
                    print("—")

                self.stats['posts_processed'] += 1

                # Коммит батчами
                if len(batch_comments) >= self.BATCH_COMMIT_SIZE:
                    print(f"\n💾 Сохранение {len(batch_comments)} комментариев в БД...")
                    self.save_comments_to_db(db, batch_comments, channel_id)
                    db.commit()
                    batch_comments = []

                # Задержка между постами
                await asyncio.sleep(self.DELAY_BETWEEN_POSTS)

            # Сохранить оставшиеся комментарии
            if batch_comments:
                print(f"\n💾 Сохранение последних {len(batch_comments)} комментариев...")
                self.save_comments_to_db(db, batch_comments, channel_id)
                db.commit()

            print("\n" + "=" * 60)
            print("✅ ИМПОРТ ЗАВЕРШЁН!")
            print("=" * 60)
            print(f"\n📊 Статистика:")
            print(f"   Обработано постов: {self.stats['posts_processed']}")
            print(f"   Найдено комментариев: {self.stats['comments_found']}")
            print(f"   Сохранено в БД: {self.stats['comments_saved']}")
            print(f"   Ошибок: {self.stats['errors']}")

        finally:
            db.close()
            await self.client.disconnect()

        return self.stats


async def main():
    """Main function for interactive usage."""
    print("\n" + "=" * 60)
    print("🤖 Telegram Comments Fetcher - Interactive Mode")
    print("=" * 60 + "\n")

    # Попытка получить credentials из .env
    api_id = os.getenv('TELEGRAM_API_ID')
    api_hash = os.getenv('TELEGRAM_API_HASH')
    channel_username = os.getenv('TELEGRAM_CHANNEL')

    # Если не в .env, спросить интерактивно
    if not api_id:
        print("📝 Введите Telegram API credentials")
        print("   (получить на https://my.telegram.org)\n")
        api_id = input("API_ID: ").strip()

    if not api_hash:
        api_hash = input("API_HASH: ").strip()

    if not channel_username:
        channel_username = input("Channel username (например: refat_talks): ").strip()

    # Валидация
    try:
        api_id = int(api_id)
    except ValueError:
        print("❌ API_ID должен быть числом!")
        return

    if not api_hash or not channel_username:
        print("❌ API_HASH и Channel username обязательны!")
        return

    # Убрать @ если есть
    if channel_username.startswith('@'):
        channel_username = channel_username[1:]

    print(f"\n✅ Credentials получены")
    print(f"   API_ID: {api_id}")
    print(f"   Channel: @{channel_username}\n")

    # Подтверждение
    confirm = input("❓ Начать импорт? (y/n): ").strip().lower()
    if confirm != 'y':
        print("❌ Отменено")
        return

    # Запуск импорта
    fetcher = SafeTelegramCommentsFetcher(api_id, api_hash)
    await fetcher.fetch_all_comments(channel_username, channel_id)

    print("\n✅ Готово! Комментарии импортированы в БД.")
    print("   Проверьте через: sqlite3 data/experts.db 'SELECT COUNT(*) FROM comments;\'\n")


if __name__ == '__main__':
    asyncio.run(main())
