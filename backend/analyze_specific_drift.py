import sys
import os
from pathlib import Path
from sqlalchemy import text

# Add backend root to path
sys.path.append(str(Path(__file__).parent))

from src.models.base import SessionLocal
from src.services.drift_scheduler_service import DriftSchedulerService

def analyze_single_post(post_id):
    print(f"🔍 Analyzing drift specifically for Post #{post_id}...")
    
    db = SessionLocal()
    try:
        service = DriftSchedulerService(db)
        
        # 1. Fetch data manually
        query = text("""
            SELECT 
                cgd.post_id,
                p.message_text as post_text
            FROM comment_group_drift cgd
            JOIN posts p ON cgd.post_id = p.post_id
            WHERE cgd.post_id = :post_id
        """)
        row = db.execute(query, {"post_id": post_id}).fetchone()
        
        if not row:
            print(f"❌ Post {post_id} not found in comment_group_drift table.")
            return

        # Fetch comments
        comments_query = text("""
            SELECT author_name, comment_text
            FROM comments
            WHERE post_id = :post_id
            ORDER BY created_at ASC
        """,)
        comments = db.execute(comments_query, {"post_id": post_id}).fetchall()
        
        comments_list = [{"author": c.author_name, "text": c.comment_text} for c in comments]
        print(f"   Found {len(comments_list)} comments.")

        if not comments_list:
             print("   ⚠️ No comments found, skipping analysis.")
             return

        # 2. Run Analysis
        print("   🤖 Sending to Gemini...")
        result = service.analyze_drift(row.post_text, comments_list)
        
        # 3. Show Result
        print("\n✅ Analysis Result:")
        print(f"   Has Drift: {result.get('has_drift')}")
        if result.get('drift_topics'):
            for topic in result['drift_topics']:
                print(f"   - Topic: {topic.get('topic')}")
                print(f"     Context: {topic.get('context')}")
        
        # 4. Update DB (Optional, but good to verify full flow)
        service.update_group_status(post_id, result)
        print("\n💾 Database updated successfully.")

    except Exception as e:
        print(f"\n❌ Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python analyze_specific_drift.py <post_id>")
        sys.exit(1)
    
    analyze_single_post(int(sys.argv[1]))
