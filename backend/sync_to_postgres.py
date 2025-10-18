#!/usr/bin/env python3
"""
Скрипт для синхронизации данных из SQLite в PostgreSQL для Railway деплоя
"""

import os
import sqlite3
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime
import json
from typing import List, Dict, Any
import sys

def get_sqlite_connection(db_path: str) -> sqlite3.Connection:
    """Подключение к SQLite базе данных"""
    return sqlite3.connect(db_path)

def get_postgres_connection(db_url: str) -> psycopg2.extensions.connection:
    """Подключение к PostgreSQL базе данных"""
    return psycopg2.connect(db_url)

def copy_table_data(sqlite_conn: sqlite3.Connection, pg_conn: psycopg2.extensions.connection,
                   table_name: str, column_mapping: Dict[str, str] = None):
    """Копирование данных из таблицы SQLite в PostgreSQL"""

    cursor = pg_conn.cursor()

    try:
        # Очистка таблицы перед копированием
        cursor.execute(f"TRUNCATE TABLE {table_name} CASCADE")
        pg_conn.commit()

        # Получение данных из SQLite
        sqlite_cursor = sqlite_conn.cursor()
        sqlite_cursor.execute(f"SELECT * FROM {table_name}")
        rows = sqlite_cursor.fetchall()

        if not rows:
            print(f"  ✅ Таблица {table_name} пуста, пропускаем")
            return

        # Получение имен колонок
        columns = [description[0] for description in sqlite_cursor.description]

        # Применение маппинга колонок если необходимо
        if column_mapping:
            columns = [column_mapping.get(col, col) for col in columns]

        # Подготовка SQL запроса
        placeholders = ', '.join(['%s'] * len(columns))
        sql = f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({placeholders})"

        # Копирование данных
        execute_values(cursor, sql, rows)
        pg_conn.commit()

        print(f"  ✅ Скопировано {len(rows)} записей в таблицу {table_name}")

    except Exception as e:
        print(f"  ❌ Ошибка при копировании таблицы {table_name}: {e}")
        pg_conn.rollback()
        raise

def copy_posts(sqlite_conn: sqlite3.Connection, pg_conn: psycopg2.extensions.connection):
    """Копирование таблицы posts с обработкой JSON полей"""

    cursor = pg_conn.cursor()

    try:
        # Очистка таблицы
        cursor.execute("TRUNCATE TABLE posts CASCADE")
        pg_conn.commit()

        # Получение данных из SQLite
        sqlite_cursor = sqlite_conn.cursor()
        sqlite_cursor.execute("""
            SELECT post_id, telegram_message_id, text, author, created_at,
                   channel_id, channel_username, expert_id
            FROM posts
        """)
        rows = sqlite_cursor.fetchall()

        if not rows:
            print("  ✅ Таблица posts пуста, пропускаем")
            return

        # Подготовка данных
        processed_rows = []
        for row in rows:
            post_id, telegram_message_id, text, author, created_at, channel_id, channel_username, expert_id = row
            processed_rows.append((
                post_id,
                telegram_message_id,
                text,
                author,
                created_at,
                channel_id,
                channel_username,
                expert_id
            ))

        # Копирование данных
        sql = """
            INSERT INTO posts (post_id, telegram_message_id, text, author, created_at,
                             channel_id, channel_username, expert_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        execute_values(cursor, sql, processed_rows)
        pg_conn.commit()

        print(f"  ✅ Скопировано {len(processed_rows)} записей в таблицу posts")

    except Exception as e:
        print(f"  ❌ Ошибка при копировании таблицы posts: {e}")
        pg_conn.rollback()
        raise

def copy_comment_group_drift(sqlite_conn: sqlite3.Connection, pg_conn: psycopg2.extensions.connection):
    """Копирование таблицы comment_group_drift с обработкой JSON полей"""

    cursor = pg_conn.cursor()

    try:
        # Очистка таблицы
        cursor.execute("TRUNCATE TABLE comment_group_drift")
        pg_conn.commit()

        # Получение данных из SQLite
        sqlite_cursor = sqlite_conn.cursor()
        sqlite_cursor.execute("""
            SELECT post_id, has_drift, drift_topics, analyzed_at, analyzed_by, expert_id
            FROM comment_group_drift
        """)
        rows = sqlite_cursor.fetchall()

        if not rows:
            print("  ✅ Таблица comment_group_drift пуста, пропускаем")
            return

        # Подготовка данных с обработкой JSON
        processed_rows = []
        for row in rows:
            post_id, has_drift, drift_topics_json, analyzed_at, analyzed_by, expert_id = row

            # Десериализация JSON из SQLite
            drift_topics = json.loads(drift_topics_json) if drift_topics_json else None

            processed_rows.append((
                post_id,
                has_drift,
                json.dumps(drift_topics) if drift_topics else None,
                analyzed_at,
                analyzed_by,
                expert_id
            ))

        # Копирование данных
        sql = """
            INSERT INTO comment_group_drift (post_id, has_drift, drift_topics, analyzed_at, analyzed_by, expert_id)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        execute_values(cursor, sql, processed_rows)
        pg_conn.commit()

        print(f"  ✅ Скопировано {len(processed_rows)} записей в таблицу comment_group_drift")

    except Exception as e:
        print(f"  ❌ Ошибка при копировании таблицы comment_group_drift: {e}")
        pg_conn.rollback()
        raise

def sync_database():
    """Основная функция синхронизации базы данных"""

    # Проверка переменных окружения
    sqlite_path = os.getenv("SQLITE_DB_PATH", "data/experts.db")
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        print("❌ Ошибка: переменная окружения DATABASE_URL не установлена")
        print("Пожалуйста, установите DATABASE_URL для PostgreSQL подключения")
        sys.exit(1)

    if not os.path.exists(sqlite_path):
        print(f"❌ Ошибка: файл SQLite базы данных не найден: {sqlite_path}")
        sys.exit(1)

    print(f"🔄 Начинаю синхронизацию SQLite → PostgreSQL")
    print(f"   Источник: {sqlite_path}")
    print(f"   Назначение: {database_url.split('@')[1] if '@' in database_url else 'PostgreSQL'}")
    print()

    try:
        # Подключение к базам данных
        sqlite_conn = get_sqlite_connection(sqlite_path)
        pg_conn = get_postgres_connection(database_url)

        print("✅ Подключения к базам данных установлены")
        print()

        # Копирование таблиц в правильном порядке (учитывая зависимости)
        tables_to_copy = [
            ("posts", copy_posts),
            ("links", None),  # Простая таблица
            ("comments", None),  # Простая таблица
            ("sync_state", None),  # Простая таблица
            ("comment_group_drift", copy_comment_group_drift),  # Специальная обработка JSON
        ]

        for table_name, copy_function in tables_to_copy:
            print(f"📋 Копирование таблицы: {table_name}")

            if copy_function:
                copy_function(sqlite_conn, pg_conn)
            else:
                copy_table_data(sqlite_conn, pg_conn, table_name)

            print()

        # Закрытие соединений
        sqlite_conn.close()
        pg_conn.close()

        print("🎉 Синхронизация успешно завершена!")
        print("   Теперь можно перезапустить деплой на Railway")

    except Exception as e:
        print(f"❌ Ошибка при синхронизации: {e}")
        sys.exit(1)

def main():
    """Точка входа в скрипт"""
    print("=" * 60)
    print("🔄 СИНХРОНИЗАЦИЯ SQLITE → POSTGRESQL")
    print("=" * 60)
    print()

    # Проверка аргументов командной строки
    if len(sys.argv) > 1 and sys.argv[1] in ["-h", "--help"]:
        print("Использование:")
        print("  python sync_to_postgres.py")
        print()
        print("Переменные окружения:")
        print("  SQLITE_DB_PATH    - путь к SQLite файлу (по умолчанию: data/experts.db)")
        print("  DATABASE_URL      - URL подключения к PostgreSQL (обязательная)")
        print()
        print("Пример:")
        print("  DATABASE_URL=postgresql://user:pass@host:port/dbname python sync_to_postgres.py")
        return

    sync_database()

if __name__ == "__main__":
    main()