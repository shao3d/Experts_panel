import json
import sqlite3
import hashlib
import sys
import os
import re
from datetime import datetime

# === КОНФИГУРАЦИЯ ===
EXPERT_ID = "video_hub"
EXPERT_NAME = "Video Hub (Experts Insights)"
CHANNEL_USERNAME = "video_hub_internal"

def get_db_path():
    """Находит путь к базе данных, отталкиваясь от расположения скрипта."""
    # Получаем абсолютный путь к папке, где лежит скрипт (backend/scripts)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # Поднимаемся на уровень выше (backend/)
    backend_dir = os.path.dirname(script_dir)
    # Корневая папка проекта
    project_root = os.path.dirname(backend_dir)

    # Варианты путей (приоритет: backend/data -> backend -> корень)
    candidates = [
        os.path.join(backend_dir, "data", "experts.db"),
        os.path.join(backend_dir, "data", "experts_panel.db"),
        os.path.join(backend_dir, "experts_panel.db"),
        os.path.join(project_root, "data", "experts.db"),
        os.path.join(project_root, "experts_panel.db")
    ]

    for path in candidates:
        if os.path.exists(path):
            return path
    
    # Если базы нет, возвращаем дефолтный путь для создания
    return candidates[0]

def slugify(text):
    """Превращает имя в ID. Поддерживает кириллицу и латиницу."""
    if not text:
        return "unknown_author"
    
    translit_map = {
        'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'e','ж':'zh','з':'z','и':'i','й':'y','к':'k','л':'l','м':'m','н':'n','о':'o','п':'p','р':'r','с':'s','т':'t','у':'u','ф':'f','х':'h','ц':'ts','ч':'ch','ш':'sh','щ':'sch','ъ':'','ы':'y','ь':'','э':'e','ю':'yu','я':'ya'
    }
    text = text.lower()
    for cyr, lat in translit_map.items():
        text = text.replace(cyr, lat)
    
    text = re.sub(r'[^a-z0-9]+', '_', text)
    return text.strip('_') or "unknown_author"

def generate_virtual_id(url, segment_id):
    """Генерирует уникальный Integer ID для telegram_message_id."""
    hash_str = f"{url}_{segment_id}"
    return int(hashlib.md5(hash_str.encode()).hexdigest(), 16) % (10**9)

def import_video_json(json_path):
    # Абсолютный путь к JSON (если передан относительный)
    if not os.path.isabs(json_path):
        json_path = os.path.abspath(json_path)

    if not os.path.exists(json_path):
        print(f"❌ Файл JSON не найден: {json_path}")
        return

    db_path = get_db_path()
    print(f"🔍 Использую базу данных: {db_path}")

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"❌ Ошибка чтения JSON: {e}")
        return

    meta = data.get("video_metadata", {})
    segments = data.get("segments", [])
    
    if not segments:
        print("⚠️ В JSON нет сегментов для импорта.")
        return

    video_url = meta.get("url", "unknown_url")
    video_title = meta.get("title", "Untitled Video")
    author_name = meta.get("author", "Unknown Expert")
    author_id = slugify(author_name)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # 1. Гарантируем наличие эксперта в метаданных
        cursor.execute("""
            INSERT OR IGNORE INTO expert_metadata (expert_id, display_name, channel_username)
            VALUES (?, ?, ?)
        """, (EXPERT_ID, EXPERT_NAME, CHANNEL_USERNAME))

        print(f"🚀 Импорт: {video_title}")
        print(f"👤 Автор: {author_name} (ID: {author_id})")

        count = 0
        for i, seg in enumerate(segments):
            # Используем индекс i как надежный fallback для segment_id
            seg_id = seg.get("segment_id", i)
            virt_msg_id = generate_virtual_id(video_url, seg_id)
            
            raw_topic_id = seg.get("topic_id", "general")
            # Берем первые 12 символов хеша URL для максимальной уникальности
            url_hash = hashlib.md5(video_url.encode()).hexdigest()[:12]
            composite_topic_id = f"{url_hash}_{raw_topic_id}"

            full_text = f"TITLE: {seg.get('title', '')}\nSUMMARY: {seg.get('summary', '')}\n---\nCONTENT:\n{seg.get('content', '')}"

            media_meta = {
                "type": "video_segment",
                "video_url": f"https://www.youtube.com/watch?v={video_url}" if len(video_url) < 15 and "http" not in video_url else video_url,
                "video_title": video_title,
                "topic_id": composite_topic_id,
                "timestamp_seconds": seg.get("timestamp_seconds", 0),
                "context_bridge": seg.get("context_bridge", ""),
                "original_author": author_name,
                "original_author_id": author_id
            }

            cursor.execute("""
                INSERT OR REPLACE INTO posts (
                    channel_id, channel_name, expert_id, message_text, 
                    author_name, author_id, created_at, telegram_message_id, media_metadata,
                    view_count, forward_count, reply_count, is_forwarded
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                CHANNEL_USERNAME,
                meta.get("channel", "Video Archive"),
                EXPERT_ID,
                full_text,
                author_name,
                author_id,
                datetime.utcnow().isoformat(),
                virt_msg_id,
                json.dumps(media_meta, ensure_ascii=False),
                0, 0, 0, 0
            ))
            count += 1

        conn.commit()
        print(f"✅ Успешно импортировано {count} сегментов.")

    except Exception as e:
        conn.rollback()
        print(f"❌ Ошибка при записи в БД: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 backend/scripts/import_video_json.py <path_to_json>")
    else:
        import_video_json(sys.argv[1])
