import sys
import os
from pathlib import Path
from datetime import datetime
from sqlalchemy import text

# Add parent directory to path to import from src
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent  # backend/
sys.path.append(str(project_root / 'src'))

# Load environment variables just in case (though usually not needed for SessionLocal if env is set)
from dotenv import load_dotenv
load_dotenv(project_root.parent / '.env')

# FORCE DATABASE PATH to be absolute to avoid relative path confusion
db_path = project_root.parent / 'backend' / 'data' / 'experts.db'
os.environ["DATABASE_URL"] = f"sqlite:///{db_path.resolve()}"
print(f"🔧 Using Database: {os.environ['DATABASE_URL']}")

from models.base import SessionLocal

def prune_old_posts():
    """
    Deletes all posts created before January 1, 2025.
    Due to ON DELETE CASCADE in schema, this also deletes linked comments and links.
    """
    db = SessionLocal()
    try:
        print("=" * 60)
        print("🧹 DATABASE CLEANUP TOOL")
        print("=" * 60)
        print("Target: Delete posts older than 2025-01-01")
        
        # Define the cutoff date string for SQL comparison
        # SQLite stores dates as strings 'YYYY-MM-DD HH:MM:SS' usually
        cutoff_date = '2025-01-01 00:00:00'
        
        # Count posts to be deleted
        print("\n📊 Analyzing database...")
        count_query = text("SELECT COUNT(*) FROM posts WHERE created_at < :cutoff")
        count = db.execute(count_query, {"cutoff": cutoff_date}).scalar()
        
        if count == 0:
            print("✅ No old posts found. Database is already clean.")
            return

        print(f"⚠️  Found {count} posts older than {cutoff_date}")
        print("   These posts (and their comments/links) will be permanently deleted.")
        
        # Confirmation
        response = input("\n❓ Type 'delete' to confirm execution: ")
        if response.lower() != 'delete':
            print("❌ Operation cancelled.")
            return

        print("\n🗑️  Deleting...")
        
        # Execute deletion
        delete_query = text("DELETE FROM posts WHERE created_at < :cutoff")
        db.execute(delete_query, {"cutoff": cutoff_date})
        db.commit()
        
        print(f"✅ Successfully deleted {count} posts.")
        
        # Optimize DB size
        print("\n🧹 Running VACUUM to optimize database size...")
        db.execute(text("VACUUM"))
        print("✅ VACUUM complete.")
        
        print("\n✨ Database cleanup finished successfully.")

    except Exception as e:
        print(f"\n❌ Error during pruning: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    prune_old_posts()
