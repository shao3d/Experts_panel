from fastapi import APIRouter, Header, HTTPException, BackgroundTasks, status
import os
import logging
from src.services.sync_orchestrator import run_full_cron_job

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/cron/run-sync", status_code=status.HTTP_202_ACCEPTED)
async def trigger_cron_sync(
    background_tasks: BackgroundTasks,
    x_cron_secret: str = Header(..., alias="X-Cron-Secret")
):
    """
    Triggers the full sync + drift analysis pipeline in background.
    Protected by X-Cron-Secret header.
    """
    expected_secret = os.getenv("CRON_SECRET")
    if not expected_secret:
        logger.error("CRON_SECRET env var is not set!")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Server configuration error")
    
    if x_cron_secret != expected_secret:
        logger.warning("Unauthorized cron attempt")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid credentials")

    background_tasks.add_task(run_full_cron_job)
    logger.info("Cron job triggered via API")
    return {"message": "Cron job accepted and running in background"}
