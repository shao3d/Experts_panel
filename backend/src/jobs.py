import logging
import subprocess
import sys
import os
from pathlib import Path
from datetime import datetime
from src.services.drift_scheduler_service import DriftSchedulerService
from src.models.base import SessionLocal

# Configure logging
CRON_LOG_FILE = Path("/app/data/logs/cron_jobs.log")
# Fallback for local dev
if not CRON_LOG_FILE.parent.exists():
    if os.path.exists("backend/data"):
        CRON_LOG_FILE = Path("backend/data/logs/cron_jobs.log")
    else:
        CRON_LOG_FILE = Path("data/logs/cron_jobs.log")

CRON_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(str(CRON_LOG_FILE)),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("cron_job_runner")

def run_sync_and_drift_job():
    """
    Main Cron Job entry point.
    1. Runs sync_channel_multi_expert.py as a subprocess.
    2. Runs DriftSchedulerService directly.
    """
    logger.info("⏰ CRON JOB STARTED: Sync + Drift Analysis")

    # --- Step 1: Run Sync ---
    try:
        logger.info("Phase 1: Starting Telegram Sync...")
        
        # Path to the sync script
        # Assuming we are running from backend/ root or similar
        project_root = Path(__file__).parent.parent
        sync_script = project_root / "sync_channel_multi_expert.py"
        
        if not sync_script.exists():
             # Try relative path if running from inside src
             sync_script = Path("sync_channel_multi_expert.py")
        
        # Run sync as subprocess with DIRECT file logging
        # This avoids buffering issues where prints are lost
        with open(str(CRON_LOG_FILE), "a") as log_f:
            log_f.write(f"\n--- Sync started at {datetime.now()} ---\n")
            log_f.flush()
            
            process = subprocess.Popen(
                [sys.executable, str(sync_script)],
                stdout=log_f,      # Direct to file
                stderr=subprocess.STDOUT, # Merge stderr
                text=True,
                env={**os.environ, "SYNC_DEPTH": "10"}
            )
            
            process.wait()
        
        if process.returncode == 0:
            logger.info("✅ Sync Phase completed successfully.")
        else:
            logger.error(f"❌ Sync Phase failed with return code {process.returncode}")
            logger.error("Skipping drift analysis due to sync failure.")
            return

    except Exception as e:
        logger.error(f"❌ Critical error during sync phase: {str(e)}")
        return

    # --- Step 2: Run Drift Analysis ---
    try:
        logger.info("Phase 2: Starting Drift Analysis (Gemini)...")
        
        db = SessionLocal()
        try:
            scheduler = DriftSchedulerService(db)
            scheduler.run_full_cycle()
            logger.info("✅ Drift analysis cycle completed.")
        except Exception as e:
            logger.error(f"❌ Error during drift analysis phase: {str(e)}")
        finally:
            db.close()

    except Exception as e:
        logger.error(f"❌ Critical error initializing drift service: {str(e)}")

    logger.info("💤 CRON JOB FINISHED")
