import sqlite3
from pathlib import Path

def get_expert_counts(db_path):
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

def compare_dbs():
    # Paths
    current_db_path = Path("backend/data/experts.db")
    # Using the known backup file
    backup_db_path = Path("backend/data/backups/experts.db.20251128_235102.bak")

    if not backup_db_path.exists():
        print(f"Backup file not found at {backup_db_path}")
        return

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

if __name__ == "__main__":
    compare_dbs()