#!/usr/bin/env python3
"""
Скрипт для применения миграций к PostgreSQL базе данных на Railway
"""

import os
import psycopg2
import sys
from pathlib import Path

def get_postgres_connection(db_url: str) -> psycopg2.extensions.connection:
    """Подключение к PostgreSQL базе данных"""
    return psycopg2.connect(db_url)

def apply_migration(pg_conn: psycopg2.extensions.connection, migration_path: str):
    """Применить одну миграцию"""
    migration_name = Path(migration_path).name

    try:
        with open(migration_path, 'r', encoding='utf-8') as f:
            migration_sql = f.read()

        cursor = pg_conn.cursor()

        # Проверяем, применялась ли уже эта миграция
        cursor.execute("""
            SELECT COUNT(*) FROM applied_migrations WHERE migration_name = %s
        """, (migration_name,))

        if cursor.fetchone()[0] > 0:
            print(f"  ✅ Миграция {migration_name} уже применена, пропускаем")
            return

        # Применяем миграцию
        cursor.execute(migration_sql)

        # Записываем применение миграции
        cursor.execute("""
            INSERT INTO applied_migrations (migration_name, applied_at)
            VALUES (%s, NOW())
        """, (migration_name,))

        pg_conn.commit()
        print(f"  ✅ Миграция {migration_name} применена успешно")

    except Exception as e:
        print(f"  ❌ Ошибка при применении миграции {migration_name}: {e}")
        pg_conn.rollback()
        raise

def ensure_migration_table(pg_conn: psycopg2.extensions.connection):
    """Создать таблицу для отслеживания примененных миграций"""
    cursor = pg_conn.cursor()

    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS applied_migrations (
                id SERIAL PRIMARY KEY,
                migration_name VARCHAR(255) UNIQUE NOT NULL,
                applied_at TIMESTAMP DEFAULT NOW()
            )
        """)
        pg_conn.commit()
        print("✅ Таблица миграций создана или уже существует")

    except Exception as e:
        print(f"❌ Ошибка при создании таблицы миграций: {e}")
        pg_conn.rollback()
        raise

def apply_migrations():
    """Основная функция применения миграций"""

    # Проверка переменных окружения
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        print("❌ Ошибка: переменная окружения DATABASE_URL не установлена")
        print("Пожалуйста, установите DATABASE_URL для PostgreSQL подключения")
        sys.exit(1)

    print(f"🔄 Начинаю применение миграций к PostgreSQL")
    print(f"   База данных: {database_url.split('@')[1] if '@' in database_url else 'PostgreSQL'}")
    print()

    try:
        # Подключение к базе данных
        pg_conn = get_postgres_connection(database_url)
        print("✅ Подключение к PostgreSQL установлено")
        print()

        # Создаем таблицу для отслеживания миграций
        ensure_migration_table(pg_conn)
        print()

        # Получаем список файлов миграций
        migrations_dir = Path("migrations")
        migration_files = sorted([
            f for f in migrations_dir.glob("*.sql")
            if f.name.startswith(("00", "01", "02", "03", "04", "05", "06", "07"))
        ])

        if not migration_files:
            print("❌ Файлы миграций не найдены в директории migrations/")
            sys.exit(1)

        print(f"📋 Найдено миграций: {len(migration_files)}")

        for migration_file in migration_files:
            print(f"📋 Применяем миграцию: {migration_file.name}")
            apply_migration(pg_conn, str(migration_file))
            print()

        # Закрытие соединения
        pg_conn.close()

        print("🎉 Все миграции успешно применены!")

    except Exception as e:
        print(f"❌ Ошибка при применении миграций: {e}")
        sys.exit(1)

def main():
    """Точка входа в скрипт"""
    print("=" * 60)
    print("🔄 ПРИМЕНЕНИЕ МИГРАЦИЙ POSTGRESQL")
    print("=" * 60)
    print()

    # Проверка аргументов командной строки
    if len(sys.argv) > 1 and sys.argv[1] in ["-h", "--help"]:
        print("Использование:")
        print("  python apply_postgres_migrations.py")
        print()
        print("Переменные окружения:")
        print("  DATABASE_URL      - URL подключения к PostgreSQL (обязательная)")
        print()
        print("Пример:")
        print("  DATABASE_URL=postgresql://user:pass@host:port/dbname python apply_postgres_migrations.py")
        print()
        print("Примечание:")
        print("  Скрипт применяет все миграции из директории migrations/")
        print("  и отслеживает уже примененные в таблице applied_migrations")
        return

    apply_migrations()

if __name__ == "__main__":
    main()