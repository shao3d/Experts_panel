#!/usr/bin/env python3
"""
Очистка orphaned записей из БД.

Удаляет комментарии, drift-записи и ссылки, ссылающиеся на несуществующие посты.
Это следствие предыдущих "грязных" удалений постов без CASCADE.
"""

import os
import sys
import shutil
from datetime import datetime
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

DB_PATH = Path(__file__).parent.parent / "data" / "experts.db"
BACKUP_DIR = Path(__file__).parent.parent / "data" / "backups"


def create_backup():
    """Создать резервную копию БД."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = BACKUP_DIR / f"experts.db.cleanup_backup.{timestamp}"
    
    print(f"📦 Создание backup: {backup_path}")
    shutil.copy2(DB_PATH, backup_path)
    
    backup_size = backup_path.stat().st_size / (1024 * 1024)
    print(f"   Размер backup: {backup_size:.2f} MB")
    return backup_path


def analyze_orphaned(session):
    """Проанализировать orphaned записи."""
    print("\n📊 Анализ orphaned записей:")
    print("-" * 60)
    
    # Комментарии
    result = session.execute(text("""
        SELECT COUNT(*) FROM comments c
        LEFT JOIN posts p ON c.post_id = p.post_id
        WHERE p.post_id IS NULL
    """))
    orphaned_comments = result.scalar()
    
    # Drift
    result = session.execute(text("""
        SELECT COUNT(*) FROM comment_group_drift d
        LEFT JOIN posts p ON d.post_id = p.post_id
        WHERE p.post_id IS NULL
    """))
    orphaned_drift = result.scalar()
    
    # Ссылки source
    result = session.execute(text("""
        SELECT COUNT(*) FROM links l
        LEFT JOIN posts p ON l.source_post_id = p.post_id
        WHERE p.post_id IS NULL
    """))
    orphaned_links_src = result.scalar()
    
    # Ссылки target
    result = session.execute(text("""
        SELECT COUNT(*) FROM links l
        LEFT JOIN posts p ON l.target_post_id = p.post_id
        WHERE p.post_id IS NULL
    """))
    orphaned_links_tgt = result.scalar()
    
    total = orphaned_comments + orphaned_drift + orphaned_links_src + orphaned_links_tgt
    
    print(f"   Комментарии без поста:     {orphaned_comments:5d}")
    print(f"   Drift без поста:           {orphaned_drift:5d}")
    print(f"   Ссылки (source) без поста: {orphaned_links_src:5d}")
    print(f"   Ссылки (target) без поста: {orphaned_links_tgt:5d}")
    print("-" * 60)
    print(f"   ИТОГО к удалению:          {total:5d} записей")
    
    return orphaned_comments, orphaned_drift, orphaned_links_src, orphaned_links_tgt


def execute_cleanup(session):
    """Выполнить очистку."""
    print("\n🧹 Очистка orphaned записей...")
    print("-" * 60)
    
    # 1. Удалить drift (нет CASCADE)
    result = session.execute(text("""
        DELETE FROM comment_group_drift
        WHERE post_id NOT IN (SELECT post_id FROM posts)
    """))
    drift_deleted = result.rowcount
    print(f"   ✅ Drift удалено: {drift_deleted}")
    
    # 2. Удалить комментарии (нет CASCADE)
    result = session.execute(text("""
        DELETE FROM comments
        WHERE post_id NOT IN (SELECT post_id FROM posts)
    """))
    comments_deleted = result.rowcount
    print(f"   ✅ Комментариев удалено: {comments_deleted}")
    
    # 3. Удалить ссылки (есть CASCADE, но orphaned всё равно чистим)
    result = session.execute(text("""
        DELETE FROM links
        WHERE source_post_id NOT IN (SELECT post_id FROM posts)
           OR target_post_id NOT IN (SELECT post_id FROM posts)
    """))
    links_deleted = result.rowcount
    print(f"   ✅ Ссылок удалено: {links_deleted}")
    
    return comments_deleted, drift_deleted, links_deleted


def verify_cleanup(session):
    """Проверить, что всё очищено."""
    print("\n🔍 Проверка после очистки:")
    print("-" * 60)
    
    result = session.execute(text("""
        SELECT COUNT(*) FROM comments c
        LEFT JOIN posts p ON c.post_id = p.post_id
        WHERE p.post_id IS NULL
    """))
    remaining_comments = result.scalar()
    
    result = session.execute(text("""
        SELECT COUNT(*) FROM comment_group_drift d
        LEFT JOIN posts p ON d.post_id = p.post_id
        WHERE p.post_id IS NULL
    """))
    remaining_drift = result.scalar()
    
    result = session.execute(text("""
        SELECT COUNT(*) FROM links l
        LEFT JOIN posts p ON l.source_post_id = p.post_id
        WHERE p.post_id IS NULL
    """))
    remaining_links_src = result.scalar()
    
    result = session.execute(text("""
        SELECT COUNT(*) FROM links l
        LEFT JOIN posts p ON l.target_post_id = p.post_id
        WHERE p.post_id IS NULL
    """))
    remaining_links_tgt = result.scalar()
    
    print(f"   Осталось orphaned комментариев: {remaining_comments}")
    print(f"   Осталось orphaned drift:        {remaining_drift}")
    print(f"   Осталось orphaned ссылок:       {remaining_links_src + remaining_links_tgt}")
    
    all_clean = (remaining_comments == 0 and remaining_drift == 0 and 
                 remaining_links_src == 0 and remaining_links_tgt == 0)
    
    if all_clean:
        print("   ✅ Всё очищено!")
    else:
        print("   ⚠️  Что-то осталось!")
    
    return all_clean


def vacuum_and_stats():
    """VACUUM и статистика."""
    print("\n🧹 VACUUM базы данных...")
    
    size_before = DB_PATH.stat().st_size / (1024 * 1024)
    
    engine = create_engine(f"sqlite:///{DB_PATH}")
    with engine.connect() as conn:
        conn.execute(text("VACUUM"))
        conn.commit()
    
    size_after = DB_PATH.stat().st_size / (1024 * 1024)
    freed = size_before - size_after
    
    print(f"   Размер до:   {size_before:.2f} MB")
    print(f"   Размер после: {size_after:.2f} MB")
    print(f"   Освобождено:  {freed:.2f} MB ({freed/size_before*100:.1f}%)")


def main():
    print("=" * 60)
    print("🧹 Cleanup Orphaned Records")
    print("=" * 60)
    
    if not DB_PATH.exists():
        print(f"❌ БД не найдена: {DB_PATH}")
        sys.exit(1)
    
    # Создать backup
    backup_path = create_backup()
    
    # Подключиться
    engine = create_engine(f"sqlite:///{DB_PATH}")
    Session = sessionmaker(bind=engine)
    
    with Session() as session:
        # Анализ
        orphaned_comments, orphaned_drift, orphaned_links_src, orphaned_links_tgt = analyze_orphaned(session)
        total = orphaned_comments + orphaned_drift + orphaned_links_src + orphaned_links_tgt
        
        if total == 0:
            print("\n✅ Нет orphaned записей для очистки!")
            sys.exit(0)
        
        # Подтверждение
        print(f"\n⚠️  Будет удалено {total} orphaned записей!")
        print(f"   Backup: {backup_path}")
        
        if os.environ.get('FORCE_CLEANUP') == '1':
            confirm = 'y'
        else:
            confirm = input("\n❓ Продолжить очистку? [y/N]: ").strip().lower()
        
        if confirm != 'y':
            print("❌ Отменено")
            sys.exit(0)
        
        try:
            # Очистка
            comments_deleted, drift_deleted, links_deleted = execute_cleanup(session)
            
            # Проверка
            all_clean = verify_cleanup(session)
            
            if all_clean:
                session.commit()
                print("\n✅ Транзакция успешно завершена!")
            else:
                print("\n❌ Проблемы! Откат...")
                session.rollback()
                sys.exit(1)
                
        except Exception as e:
            print(f"\n❌ Ошибка: {e}")
            session.rollback()
            sys.exit(1)
    
    # VACUUM
    vacuum_and_stats()
    
    print("\n" + "=" * 60)
    print("✅ Готово! Orphaned записи удалены.")
    print("=" * 60)


if __name__ == "__main__":
    main()
