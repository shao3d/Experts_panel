import sqlite3
import os

def clean_old_posts(db_path, expert_id, cutoff_date):
    print(f"Connecting to DB at {db_path}...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get all posts for the expert
    cursor.execute("SELECT post_id, created_at FROM posts WHERE expert_id = ?", (expert_id,))
    all_posts = cursor.fetchall()

    new_post_ids = set()
    old_post_ids = set()

    for pid, created_at in all_posts:
        if created_at and created_at >= cutoff_date:
            new_post_ids.add(pid)
        else:
            old_post_ids.add(pid)

    print(f"Found {len(new_post_ids)} posts >= {cutoff_date}")
    print(f"Found {len(old_post_ids)} posts < {cutoff_date}")

    # Find all links to ensure we don't delete old posts linked by new posts
    cursor.execute("SELECT source_post_id, target_post_id FROM links")
    links = cursor.fetchall()

    old_posts_to_keep = set()
    for source, target in links:
        if source in new_post_ids and target in old_post_ids:
            old_posts_to_keep.add(target)
        if target in new_post_ids and source in old_post_ids:
            old_posts_to_keep.add(source)

    print(f"Keeping {len(old_posts_to_keep)} old posts because they are linked to new ones.")

    posts_to_delete = list(old_post_ids - old_posts_to_keep)
    print(f"Total old posts to delete: {len(posts_to_delete)}")

    if posts_to_delete:
        batch_size = 500
        for i in range(0, len(posts_to_delete), batch_size):
            batch = posts_to_delete[i:i+batch_size]
            placeholders = ','.join('?' for _ in batch)
            
            # Delete from comment_group_drift
            cursor.execute(f"DELETE FROM comment_group_drift WHERE post_id IN ({placeholders})", batch)
            
            # Delete from comments
            cursor.execute(f"DELETE FROM comments WHERE post_id IN ({placeholders})", batch)
            
            # Delete from links
            cursor.execute(f"DELETE FROM links WHERE source_post_id IN ({placeholders}) OR target_post_id IN ({placeholders})", batch + batch)
            
            # Delete from posts
            cursor.execute(f"DELETE FROM posts WHERE post_id IN ({placeholders})", batch)
            
        conn.commit()
        print("Deletion successful!")
    else:
        print("Nothing to delete.")

    conn.close()

if __name__ == '__main__':
    db_file = os.path.join(os.path.dirname(__file__), '..', 'data', 'experts.db')
    clean_old_posts(db_file, 'silicbag', '2025-01-01')
