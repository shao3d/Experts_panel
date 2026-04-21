#!/usr/bin/env python3
"""
Безопасное удаление старых постов (до 2024) у экспертов polyakov и ai_grabli.

Скрипт удаляет:
- 34 поста (25 ai_grabli + 9 polyakov)
- 10 комментариев (cascade)
- 3 ссылки (cascade)  
- 7 drift-записей (вручную, т.к. нет cascade)

Перед удалением создаётся backup!
"""

import os
import sys
import shutil
from datetime import datetime
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.cli.bootstrap import bootstrap_cli, get_sqlite_db_path

BACKEND_DIR, logger = bootstrap_cli(
    __file__,
    logger_name="scripts.prune_old_posts",
)

# Настройки
DB_PATH = get_sqlite_db_path(BACKEND_DIR)
BACKUP_DIR = BACKEND_DIR / "data" / "backups"

# Эксперты и дата для удаления
EXPERTS_TO_PRUNE = ['polyakov', 'ai_grabli']
CUTOFF_DATE = '2024-01-01'


def create_backup():
    """Создать резервную копию БД."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = BACKUP_DIR / f"experts.db.backup.{timestamp}"
    
    print(f"📦 Создание backup: {backup_path}")
    shutil.copy2(DB_PATH, backup_path)
    
    backup_size = backup_path.stat().st_size / (1024 * 1024)
    print(f"   Размер backup: {backup_size:.2f} MB")
    
    return backup_path


def analyze_impact(session):
    """Проанализировать, что будет удалено."""
    print("\n📊 Анализ данных для удаления:")
    print("-" * 50)
    
    # Посты
    result = session.execute(text("""
        SELECT expert_id, COUNT(*) as count,
               MIN(DATE(created_at)) as oldest,
               MAX(DATE(created_at)) as newest
        FROM posts
        WHERE created_at < :cutoff AND expert_id IN ('polyakov', 'ai_grabli')
        GROUP BY expert_id
    """), {'cutoff': CUTOFF_DATE})
    
    total_posts = 0
    for row in result:
        print(f"   Посты {row.expert_id}: {row.count} шт. ({row.oldest} → {row.newest})")
        total_posts += row.count
    
    # Комментарии
    result = session.execute(text("""
        SELECT p.expert_id, COUNT(*) as count
        FROM comments c
        JOIN posts p ON c.post_id = p.post_id
        WHERE p.created_at < :cutoff AND p.expert_id IN ('polyakov', 'ai_grabli')
        GROUP BY p.expert_id
    """), {'cutoff': CUTOFF_DATE})
    
    total_comments = 0
    for row in result:
        print(f"   Комментарии {row.expert_id}: {row.count} шт.")
        total_comments += row.count
    
    # Drift
    result = session.execute(text("""
        SELECT p.expert_id, COUNT(*) as count
        FROM comment_group_drift cgd
        JOIN posts p ON cgd.post_id = p.post_id
        WHERE p.created_at < :cutoff AND p.expert_id IN ('polyakov', 'ai_grabli')
        GROUP BY p.expert_id
    """), {'cutoff': CUTOFF_DATE})
    
    total_drift = 0
    for row in result:
        print(f"   Drift records {row.expert_id}: {row.count} шт.")
        total_drift += row.count
    
    # Ссылки
    result = session.execute(text("""
        SELECT COUNT(*) as count
        FROM links l
        JOIN posts src ON l.source_post_id = src.post_id
        JOIN posts tgt ON l.target_post_id = tgt.post_id
        WHERE (src.created_at < :cutoff AND src.expert_id IN ('polyakov', 'ai_grabli'))
           OR (tgt.created_at < :cutoff AND tgt.expert_id IN ('polyakov', 'ai_grabli'))
    """), {'cutoff': CUTOFF_DATE})
    
    total_links = result.scalar()
    print(f"   Ссылки (связанные): {total_links} шт.")
    
    print("-" * 50)
    print(f"   ИТОГО: {total_posts} постов, {total_comments} комментариев, {total_drift} drift, {total_links} ссылок")
    
    return total_posts, total_comments, total_drift, total_links


def execute_deletion(session):
    """Выполнить удаление в правильном порядке."""
    print("\n🗑️  Удаление данных...")
    print("-" * 50)
    
    # Шаг 1: Удалить drift-записи (нет cascade)
    result = session.execute(text("""
        DELETE FROM comment_group_drift 
        WHERE post_id IN (
            SELECT post_id FROM posts 
            WHERE created_at < :cutoff AND expert_id IN ('polyakov', 'ai_grabli')
        )
        RETURNING id
    """), {'cutoff': CUTOFF_DATE})
    
    drift_deleted = result.rowcount
    print(f"   ✅ Drift records удалено: {drift_deleted}")
    
    # Шаг 2: Удалить посты (cascade удалит comments и links)
    result = session.execute(text("""
        DELETE FROM posts 
        WHERE created_at < :cutoff AND expert_id IN ('polyakov', 'ai_grabli')
        RETURNING post_id
    """), {'cutoff': CUTOFF_DATE})
    
    posts_deleted = result.rowcount
    print(f"   ✅ Постов удалено: {posts_deleted}")
    
    return posts_deleted, drift_deleted


def verify_deletion(session):
    """Проверить, что всё удалено корректно."""
    print("\n🔍 Проверка после удаления:")
    print("-" * 50)
    
    # Проверить, что посты удалены
    result = session.execute(text("""
        SELECT COUNT(*) FROM posts
        WHERE created_at < :cutoff AND expert_id IN ('polyakov', 'ai_grabli')
    """), {'cutoff': CUTOFF_DATE})
    
    remaining_posts = result.scalar()
    print(f"   Осталось постов: {remaining_posts} (должно быть 0)")
    
    # Проверить, что drift удалены (теперь post_id не существует)
    result = session.execute(text("""
        SELECT COUNT(*) FROM comment_group_drift cgd
        LEFT JOIN posts p ON cgd.post_id = p.post_id
        WHERE p.post_id IS NULL
    """))
    
    orphaned_drift = result.scalar()
    print(f"   Orphaned drift: {orphaned_drift} (проверяем что не появились новые)")
    
    # Проверяем, что удалились drift для наших постов (они должны быть удалены)
    result = session.execute(text("""
        SELECT COUNT(*) FROM comment_group_drift cgd
        WHERE cgd.post_id IN (
            SELECT post_id FROM posts 
            WHERE created_at < :cutoff AND expert_id IN ('polyakov', 'ai_grabli')
        )
    """), {'cutoff': CUTOFF_DATE})
    
    remaining_target_drift = result.scalar()
    print(f"   Осталось drift целевых постов: {remaining_target_drift} (должно быть 0)")
    
    all_ok = (remaining_posts == 0 and remaining_target_drift == 0)
    
    return all_ok


def vacuum_database():
    """Выполнить VACUUM для освобождения места."""
    print("\n🧹 Очистка БД (VACUUM)...")
    
    size_before = DB_PATH.stat().st_size / (1024 * 1024)
    
    engine = create_engine(f"sqlite:///{DB_PATH}")
    with engine.connect() as conn:
        conn.execute(text("VACUUM"))
        conn.commit()
    
    size_after = DB_PATH.stat().st_size / (1024 * 1024)
    freed = size_before - size_after
    
    print(f"   Размер до: {size_before:.2f} MB")
    print(f"   Размер после: {size_after:.2f} MB")
    print(f"   Освобождено: {freed:.2f} MB")


def main():
    print("=" * 60)
    print("🧹 Prune Old Posts - Безопасное удаление старых постов")
    print("=" * 60)
    
    # Проверить существование БД
    if not DB_PATH.exists():
        print(f"❌ Ошибка: БД не найдена: {DB_PATH}")
        sys.exit(1)
    
    print(f"\n📁 БД: {DB_PATH}")
    print(f"📅 Удаляем посты до: {CUTOFF_DATE}")
    print(f"👤 Эксперты: {', '.join(EXPERTS_TO_PRUNE)}")
    
    # Создать backup
    backup_path = create_backup()
    
    # Подключиться к БД
    engine = create_engine(f"sqlite:///{DB_PATH}")
    Session = sessionmaker(bind=engine)
    
    with Session() as session:
        # Анализ
        total_posts, total_comments, total_drift, total_links = analyze_impact(session)
        
        if total_posts == 0:
            print("\n⚠️  Нет данных для удаления!")
            sys.exit(0)
        
        # Подтверждение
        print(f"\n⚠️  ВНИМАНИЕ: Будет удалено {total_posts} постов и связанных данных!")
        print(f"   Backup создан: {backup_path}")
        
        if os.environ.get('FORCE_DELETE') == '1':
            confirm = 'y'
        else:
            confirm = input("\n❓ Продолжить удаление? [y/N]: ").strip().lower()
        
        if confirm != 'y':
            print("❌ Отменено пользователем")
            sys.exit(0)
        
        try:
            # Выполнить удаление
            posts_deleted, drift_deleted = execute_deletion(session)
            
            # Проверить
            all_ok = verify_deletion(session)
            
            if all_ok:
                session.commit()
                print("\n✅ Транзакция успешно завершена!")
            else:
                print("\n❌ Обнаружены проблемы! Откат транзакции...")
                session.rollback()
                sys.exit(1)
                
        except Exception as e:
            print(f"\n❌ Ошибка: {e}")
            session.rollback()
            sys.exit(1)
    
    # VACUUM (вне транзакции)
    vacuum_database()
    
    print("\n" + "=" * 60)
    print("✅ Готово! Старые посты удалены.")
    print("=" * 60)


if __name__ == "__main__":
    main()
