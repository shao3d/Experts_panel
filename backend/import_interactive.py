"""Interactive import with code input."""
import asyncio
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.cli.bootstrap import bootstrap_cli, run_async
from src.data.telegram_comments_fetcher import SafeTelegramCommentsFetcher
from telethon import TelegramClient

BACKEND_DIR, logger = bootstrap_cli(
    __file__,
    logger_name="cli.import_interactive",
)

async def run():
    api_id = os.getenv('TELEGRAM_API_ID')
    api_hash = os.getenv('TELEGRAM_API_HASH')
    channel = os.getenv('TELEGRAM_CHANNEL', 'nobilix')
    phone = os.getenv('TELEGRAM_PHONE')  # Ваш номер телефона
    code = os.getenv('TELEGRAM_CODE')    # Код из SMS

    if not api_id or not api_hash:
        print("\n❌ ERROR: Missing TELEGRAM_API_ID or TELEGRAM_API_HASH")
        print("   Set them in .env file")
        return

    api_id = int(api_id)

    print(f"\n🚀 Telegram Comments Fetcher")
    print(f"   Channel: @{channel}")

    if not phone:
        print("\n❌ Нужен номер телефона!")
        print("   Установите: TELEGRAM_PHONE=+79123456789")
        return
    
    print(f"   Phone: {phone}")
    
    # Создать клиент
    client = TelegramClient('telegram_fetcher', api_id, api_hash)
    await client.connect()
    
    # Проверить авторизацию
    if not await client.is_user_authorized():
        print("\n📱 Отправка кода на телефон...")
        await client.send_code_request(phone)
        
        if not code:
            print("\n⏸️  ОЖИДАНИЕ КОДА")
            print("   Telegram отправил код на ваш телефон")
            print("   Введите код в чат и запустите снова с TELEGRAM_CODE")
            await client.disconnect()
            return
        
        print(f"\n🔐 Авторизация с кодом...")
        try:
            await client.sign_in(phone, code)
            print("✅ Авторизация успешна!")
        except Exception as e:
            print(f"❌ Ошибка авторизации: {e}")
            await client.disconnect()
            return
    else:
        print("✅ Уже авторизован!")
    
    await client.disconnect()
    
    # Теперь запустить основной импорт
    print("\n🔄 Запуск импорта комментариев...")
    fetcher = SafeTelegramCommentsFetcher(api_id, api_hash, 'telegram_fetcher')
    await fetcher.fetch_all_comments(channel)
    
    print("\n✅ Готово!")

if __name__ == '__main__':
    run_async(run())
