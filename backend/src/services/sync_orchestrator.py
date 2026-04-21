import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.data.channel_syncer import TelegramChannelSyncer
from src.models.base import SessionLocal
from src.models.post import Post

logger = logging.getLogger(__name__)

def get_all_experts(db: Session) -> List[Dict[str, Any]]:
    """
    Получает всех экспертов из expert_metadata с их статистикой из posts.
    """
    # Query expert_metadata for all experts, excluding video_hub
    experts_query = text("""
        SELECT expert_id, channel_username
        FROM expert_metadata
        WHERE expert_id != 'video_hub'
        ORDER BY expert_id
    """)

    expert_metadata = db.execute(experts_query).fetchall()
    experts = []

    for expert_id, channel_username in expert_metadata:
        # Get stats from posts table for this expert
        stats_query = text("""
            SELECT
                channel_id,
                channel_name,
                MIN(telegram_message_id) as min_message_id,
                MAX(telegram_message_id) as max_message_id,
                COUNT(*) as post_count
            FROM posts
            WHERE expert_id = :expert_id
            GROUP BY channel_id, channel_name
        """)

        stats = db.execute(stats_query, {"expert_id": expert_id}).fetchone()

        if not stats:
            print(f"⚠️  Expert {expert_id} has no posts in database")
            continue

        channel_id, channel_name, min_id, max_id, count = stats

        experts.append({
            'expert_id': expert_id,
            'channel_id': channel_id,
            'channel_username': channel_username,
            'channel_name': channel_name,
            'min_message_id': min_id,
            'max_message_id': max_id,
            'post_count': count
        })

    return experts

def run_preflight_checks():
    """
    Run preflight checks before sync.
    Raises exceptions on failure.
    """
    # Check 1: Session file exists
    session_name = os.getenv('TELEGRAM_SESSION_NAME', 'telegram_fetcher')
    
    # Try finding session in current dir or script dir or parent dirs
    possible_paths = [
        Path(f"{session_name}.session"),
        Path("/app/data") / f"{session_name}.session",  # Production Volume Path
        Path(__file__).parent / f"{session_name}.session",
        # Check backend root (src/services/../../)
        Path(__file__).parent.parent.parent / f"{session_name}.session"
    ]
    
    session_path = None
    for p in possible_paths:
        if p.exists():
            session_path = p
            break
            
    if not session_path:
        error_msg = (
            "❌ ERROR: Telegram session file not found\n"
            f"Searched in: {[str(p) for p in possible_paths]}\n"
            f"Expected file: {session_name}.session"
        )
        raise FileNotFoundError(error_msg)
    
    # Set env var for Syncer
    os.environ['TELEGRAM_SESSION_PATH'] = str(session_path.resolve())

    # Check 2: API credentials present
    required_vars = ['TELEGRAM_API_ID', 'TELEGRAM_API_HASH']
    missing = [v for v in required_vars if not os.getenv(v)]

    if missing:
        error_msg = f"❌ ERROR: Missing environment variables: {', '.join(missing)}"
        raise EnvironmentError(error_msg)

    print("✅ Preflight checks passed", file=sys.stderr)

def create_pending_drift_records(db: Session, expert_id: str, post_ids: List[int]):
    """Creates pending drift records for new posts."""
    for post_id in post_ids:
        existing = db.execute(text("""
            SELECT 1 FROM comment_group_drift WHERE post_id = :post_id
        """), {"post_id": post_id}).fetchone()

        if not existing:
            has_comments = db.execute(text("""
                SELECT 1 FROM comments WHERE post_id = :post_id LIMIT 1
            """), {"post_id": post_id}).fetchone()

            status = 'pending' if has_comments else 'no-comments'

            db.execute(text("""
                INSERT INTO comment_group_drift
                (post_id, has_drift, drift_topics, analyzed_at, analyzed_by, expert_id)
                VALUES (:post_id, 0, NULL, datetime('now'), :status, :expert_id)
            """), {"post_id": post_id, "expert_id": expert_id, "status": status})

def reset_drift_records_to_pending(db: Session, post_ids: List[int], expert_id: Optional[str] = None):
    """Resets drift records for updated posts."""
    if not post_ids:
        return

    for post_id in post_ids:
        has_comments = db.execute(text("""
            SELECT 1 FROM comments WHERE post_id = :post_id LIMIT 1
        """), {"post_id": post_id}).fetchone()

        status = 'pending' if has_comments else 'no-comments'

        result = db.execute(text("""
            UPDATE comment_group_drift
            SET analyzed_by = :status,
                drift_topics = NULL,
                analyzed_at = datetime('now')
            WHERE post_id = :post_id
        """), {"post_id": post_id, "status": status})

        if result.rowcount == 0:
            resolved_expert_id = expert_id
            if not resolved_expert_id:
                expert_row = db.execute(text("""
                    SELECT expert_id FROM posts WHERE post_id = :post_id
                """), {"post_id": post_id}).fetchone()
                resolved_expert_id = expert_row[0] if expert_row else None

            if resolved_expert_id:
                db.execute(text("""
                    INSERT INTO comment_group_drift
                    (post_id, has_drift, drift_topics, analyzed_at, analyzed_by, expert_id)
                    VALUES (:post_id, 0, NULL, datetime('now'), :status, :expert_id)
                """), {
                    "post_id": post_id,
                    "status": status,
                    "expert_id": resolved_expert_id
                })

def print_multi_expert_summary(results: List[Dict[str, Any]], start_time: datetime):
    """Print summary to stderr."""
    print(file=sys.stderr)
    print("=" * 80, file=sys.stderr)
    print("MULTI-EXPERT SYNC COMPLETE", file=sys.stderr)
    print("=" * 80, file=sys.stderr)

    total_new_posts = 0
    total_updated_posts = 0
    total_new_comments = 0
    total_pending_new = 0
    total_pending_reset = 0
    successful_experts = 0

    for result in results:
        expert_id = result['expert_id']
        reset_count = result.get('reset_count', 0)
        new_drift_count = len(result['new_comment_groups'])

        if result['success']:
            successful_experts += 1
            print(f"✅ {expert_id}: SUCCESS", file=sys.stderr)
        else:
            print(f"❌ {expert_id}: FAILED", file=sys.stderr)

        print(f"   New posts: {len(result['new_posts'])}", file=sys.stderr)
        print(f"   Updated posts: {len(result['updated_posts'])}", file=sys.stderr)
        print(f"   New comments: {result['stats'].get('total_comments', 0)}", file=sys.stderr)
        print(f"   Pending Drift Analysis: New={new_drift_count}, Reset={reset_count}", file=sys.stderr)
        print(file=sys.stderr)

        total_new_posts += len(result['new_posts'])
        total_updated_posts += len(result['updated_posts'])
        total_new_comments += result['stats'].get('total_comments', 0)
        total_pending_new += new_drift_count
        total_pending_reset += reset_count

    print("📈 TOTAL SUMMARY:", file=sys.stderr)
    print(f"   Experts processed: {successful_experts}/{len(results)}", file=sys.stderr)
    print(f"   Total new posts: {total_new_posts}", file=sys.stderr)
    print(f"   Total updated posts: {total_updated_posts}", file=sys.stderr)
    print(f"   Total new comments: {total_new_comments}", file=sys.stderr)
    print(f"   Total Pending Drift Tasks: {total_pending_new + total_pending_reset}", file=sys.stderr)
    
    duration = (datetime.utcnow() - start_time).total_seconds()
    print(f"   Total duration: {duration:.1f}s", file=sys.stderr)
    print("=" * 80, file=sys.stderr)

async def run_cron_pipeline(dry_run: bool = False, depth: int = 10) -> Dict[str, Any]:
    """
    Executes the full multi-expert sync pipeline.
    """
    load_dotenv()
    run_preflight_checks()

    api_id = int(os.getenv('TELEGRAM_API_ID'))
    api_hash = os.getenv('TELEGRAM_API_HASH')
    session_name = os.getenv('TELEGRAM_SESSION_NAME', 'telegram_fetcher')

    print("🔄 MULTI-EXPERT TELEGRAM SYNC (Service)", file=sys.stderr)
    print(f"Mode: {'DRY-RUN' if dry_run else 'LIVE'}, Depth: {depth}", file=sys.stderr)

    db = SessionLocal()
    try:
        experts = get_all_experts(db)
        if not experts:
            return {'success': False, 'error': 'No experts found'}

        # Resolve session path
        session_path_env = os.getenv('TELEGRAM_SESSION_PATH')
        session_name_arg = str(Path(session_path_env).with_suffix('')) if session_path_env else session_name

        syncer = TelegramChannelSyncer(api_id=api_id, api_hash=api_hash, session_name=session_name_arg)
        syncer.RECENT_POSTS_DEPTH = depth

        results = []
        start_time = datetime.utcnow()

        for i, expert in enumerate(experts, 1):
            print(f"[{i}/{len(experts)}] Syncing {expert['expert_id']}...", file=sys.stderr)
            try:
                result = await syncer.sync_channel_incremental(
                    channel_username=expert['channel_username'],
                    expert_id=expert['expert_id'],
                    dry_run=dry_run
                )
                result['expert_id'] = expert['expert_id']
                result['reset_count'] = 0

                if not dry_run and result['success']:
                    if result['new_posts']:
                        # Get post_ids for new telegram_message_ids
                        # Using comma-separated string for IN clause safely
                        ids_str = ','.join(map(str, result['new_posts']))
                        if ids_str:
                            new_post_ids = db.execute(text(f"SELECT post_id FROM posts WHERE expert_id = :expert_id AND telegram_message_id IN ({ids_str})"), {"expert_id": expert['expert_id']}).fetchall()
                            post_ids = [row[0] for row in new_post_ids]
                            create_pending_drift_records(db, expert['expert_id'], post_ids)

                    if result['stats'].get('total_comments', 0) > 0 and result['updated_posts']:
                        ids_str = ','.join(map(str, result['updated_posts']))
                        if ids_str:
                            posts_with_new = db.execute(text(f"""
                                SELECT DISTINCT p.post_id FROM posts p 
                                WHERE p.expert_id = :expert_id 
                                AND p.telegram_message_id IN ({ids_str}) 
                                AND EXISTS (SELECT 1 FROM comments c WHERE c.post_id = p.post_id)
                            """), {"expert_id": expert['expert_id']}).fetchall()
                            post_ids = [row[0] for row in posts_with_new]
                            if post_ids:
                                reset_drift_records_to_pending(db, post_ids, expert['expert_id'])
                                result['reset_count'] = len(post_ids)
                    
                    db.commit()
                
                results.append(result)
            except Exception as e:
                print(f"❌ Failed {expert['expert_id']}: {e}", file=sys.stderr)
                results.append({
                    'expert_id': expert['expert_id'], 'success': False, 
                    'new_posts': [], 'updated_posts': [], 'new_comment_groups': [], 
                    'stats': {'total_comments': 0}, 'errors': [str(e)]
                })

        print_multi_expert_summary(results, start_time)
        
        return {
            'success': all(r['success'] for r in results),
            'experts_processed': len(results),
            'expert_results': results
        }
    finally:
        db.close()
