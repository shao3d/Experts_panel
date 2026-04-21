import argparse
import sqlite3
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.cli.bootstrap import bootstrap_cli, get_sqlite_db_path

BACKEND_DIR, logger = bootstrap_cli(
    __file__,
    logger_name="scripts.compare_cleanup",
)
DEFAULT_CURRENT_DB_PATH = get_sqlite_db_path(BACKEND_DIR)
DEFAULT_BACKUP_DB_PATH = BACKEND_DIR / "data" / "backups" / "experts.db.20251128_235102.bak"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare post counts per expert between current and backup SQLite databases.",
    )
    parser.add_argument("--current-db", default=str(DEFAULT_CURRENT_DB_PATH), help="Path to current SQLite DB")
    parser.add_argument("--backup-db", default=str(DEFAULT_BACKUP_DB_PATH), help="Path to backup SQLite DB")
    return parser.parse_args()


def get_expert_counts(db_path: Path):
    counts = {}
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT expert_id, COUNT(*) FROM posts GROUP BY expert_id")
            for expert_id, count in cursor.fetchall():
                counts[expert_id] = count
    except Exception as e:
        print(f"Error reading {db_path}: {e}")
    return counts


def compare_dbs(current_db_path: Path, backup_db_path: Path) -> int:

    if not backup_db_path.exists():
        print(f"Backup file not found at {backup_db_path}")
        return 1

    print(f"Comparing:\n  OLD: {backup_db_path.name}\n  NEW: {current_db_path.name}")

    old_counts = get_expert_counts(backup_db_path)
    new_counts = get_expert_counts(current_db_path)

    # Gather all expert IDs
    all_experts = set(old_counts.keys()) | set(new_counts.keys())

    print("\n📊 Post Reduction Analysis:")
    print(f"{ 'Expert ID':<20} | { 'Old':<6} | { 'New':<6} | { 'Removed':<6}")
    print("-" * 46)

    total_old = 0
    total_new = 0
    total_removed = 0

    # Sort by removed count descending
    diffs = []
    for expert_id in all_experts:
        old = old_counts.get(expert_id, 0)
        new = new_counts.get(expert_id, 0)
        removed = old - new
        
        total_old += old
        total_new += new
        total_removed += removed
        
        if removed > 0:
            diffs.append((expert_id, old, new, removed))

    # Sort by most removed
    diffs.sort(key=lambda x: x[3], reverse=True)

    for expert_id, old, new, removed in diffs:
        print(f"{expert_id:<20} | {old:<6} | {new:<6} | -{removed:<6}")

    print("-" * 46)
    print(f"{ 'TOTAL':<20} | {total_old:<6} | {total_new:<6} | -{total_removed:<6}")
    return 0

if __name__ == "__main__":
    args = parse_args()
    raise SystemExit(
        compare_dbs(Path(args.current_db).resolve(), Path(args.backup_db).resolve())
    )
