"""Import endpoints for Telegram JSON file uploads."""

import json
import io
import uuid
import asyncio
from typing import Dict, Any
import logging
from datetime import datetime

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from .models import ErrorResponse
from .dependencies import verify_admin_secret
from ..models.base import SessionLocal
from ..data.json_parser import TelegramJsonParser

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(
    prefix="/api",
    tags=["import"],
    dependencies=[Depends(verify_admin_secret)],
)

# Store import job statuses (in production, use Redis or database)
import_jobs = {}


def get_db():
    """Database dependency."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class ImportRequest:
    """Import request model."""
    def __init__(self, file: UploadFile):
        self.file = file
        self.job_id = str(uuid.uuid4())


class ImportResponse:
    """Import response model."""
    def __init__(self, job_id: str, status: str, message: str, statistics: Dict[str, int] = None):
        self.job_id = job_id
        self.status = status
        self.message = message
        self.statistics = statistics
        self.timestamp = datetime.utcnow().isoformat()


def process_import_background(job_id: str, file_content: bytes, filename: str, db: Session):
    """Background task to process import."""
    try:
        # Update job status
        import_jobs[job_id] = {
            "status": "processing",
            "message": f"Processing file: {filename}",
            "progress": 0,
            "started_at": datetime.utcnow().isoformat()
        }

        # Parse JSON content
        try:
            data = json.loads(file_content.decode('utf-8'))
        except json.JSONDecodeError as e:
            import_jobs[job_id] = {
                "status": "failed",
                "message": f"Invalid JSON format: {str(e)}",
                "error": str(e),
                "completed_at": datetime.utcnow().isoformat()
            }
            return

        # Validate Telegram JSON structure
        if 'messages' not in data:
            import_jobs[job_id] = {
                "status": "failed",
                "message": "Invalid Telegram export format: 'messages' field not found",
                "error": "Missing required field: messages",
                "completed_at": datetime.utcnow().isoformat()
            }
            return

        # Create parser and import
        parser = TelegramJsonParser(db)

        # Override parse_file to work with in-memory data
        # Save original method
        original_parse_file = parser.parse_file

        def parse_data(data_dict):
            """Parse from dictionary instead of file."""
            # Extract channel/chat info
            channel_info = parser._extract_channel_info(data_dict)

            # Parse messages
            messages = data_dict.get('messages', [])
            total = len(messages)

            import_jobs[job_id]["total_messages"] = total

            # Process in batches
            batch_size = 100
            for i in range(0, total, batch_size):
                batch = messages[i:i+batch_size]
                parser._process_message_batch(batch, channel_info)

                # Update progress
                progress = min(i + batch_size, total)
                percent = (progress / total) * 100
                import_jobs[job_id]["progress"] = percent
                import_jobs[job_id]["message"] = f"Processing: {progress}/{total} messages"

            # Commit all changes
            try:
                db.commit()
            except Exception as e:
                logger.error(f"Error committing changes: {e}")
                db.rollback()
                parser.stats['errors'] += 1
                raise

            # Create links after all posts are imported
            parser._create_links(messages)

            return parser.stats

        # Run import
        stats = parse_data(data)

        # Update job status with results
        import_jobs[job_id] = {
            "status": "completed",
            "message": "Import completed successfully",
            "statistics": stats,
            "total_messages": len(data.get('messages', [])),
            "channel_name": data.get('name', data.get('title', 'Unknown')),
            "completed_at": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Import job {job_id} failed: {str(e)}")
        import_jobs[job_id] = {
            "status": "failed",
            "message": f"Import failed: {str(e)}",
            "error": str(e),
            "completed_at": datetime.utcnow().isoformat()
        }
    finally:
        db.close()


@router.post("/import")
async def import_telegram_json(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Import Telegram JSON export file.

    Args:
        file: Uploaded JSON file
        background_tasks: FastAPI background tasks
        db: Database session

    Returns:
        Import job information with job_id for status polling
    """
    job_id = str(uuid.uuid4())

    logger.info(f"Starting import job {job_id} for file: {file.filename}")

    # Validate file extension
    if not file.filename.endswith('.json'):
        raise HTTPException(
            status_code=400,
            detail="Invalid file format. Please upload a JSON file."
        )

    # Validate file size (max 50MB)
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
    file_content = await file.read()

    if len(file_content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024*1024)}MB"
        )

    if len(file_content) == 0:
        raise HTTPException(
            status_code=400,
            detail="Empty file uploaded"
        )

    # Quick JSON validation
    try:
        data = json.loads(file_content.decode('utf-8'))
        message_count = len(data.get('messages', []))
        channel_name = data.get('name', data.get('title', 'Unknown'))
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid JSON format: {str(e)}"
        )
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=400,
            detail="File encoding error. Please ensure the file is UTF-8 encoded."
        )

    # Validate Telegram export structure
    if 'messages' not in data:
        raise HTTPException(
            status_code=400,
            detail="Invalid Telegram export format. Missing 'messages' field."
        )

    # Initialize job status
    import_jobs[job_id] = {
        "status": "queued",
        "message": "Import job queued",
        "filename": file.filename,
        "file_size": len(file_content),
        "message_count": message_count,
        "channel_name": channel_name,
        "created_at": datetime.utcnow().isoformat()
    }

    # Start background processing
    background_tasks.add_task(
        process_import_background,
        job_id,
        file_content,
        file.filename,
        db
    )

    return JSONResponse(
        status_code=202,  # Accepted
        content={
            "job_id": job_id,
            "status": "accepted",
            "message": f"Import job started for {message_count} messages from '{channel_name}'",
            "filename": file.filename,
            "file_size": len(file_content),
            "message_count": message_count,
            "channel_name": channel_name,
            "status_url": f"/api/import/status/{job_id}"
        }
    )


@router.get("/import/status/{job_id}")
async def get_import_status(job_id: str):
    """Get status of an import job.

    Args:
        job_id: Import job ID

    Returns:
        Current status of the import job
    """
    if job_id not in import_jobs:
        raise HTTPException(
            status_code=404,
            detail=f"Import job {job_id} not found"
        )

    job_status = import_jobs[job_id]

    return JSONResponse(
        content={
            "job_id": job_id,
            **job_status
        }
    )


@router.get("/import/jobs")
async def list_import_jobs(limit: int = 10):
    """List recent import jobs.

    Args:
        limit: Maximum number of jobs to return

    Returns:
        List of recent import jobs
    """
    # Get recent jobs, sorted by creation time
    jobs_list = []
    for job_id, job_data in import_jobs.items():
        jobs_list.append({
            "job_id": job_id,
            **job_data
        })

    # Sort by created_at or completed_at
    jobs_list.sort(
        key=lambda x: x.get('completed_at', x.get('created_at', '')),
        reverse=True
    )

    return {
        "jobs": jobs_list[:limit],
        "total": len(jobs_list)
    }


@router.delete("/import/jobs")
async def clear_import_jobs():
    """Clear all import job history.

    Returns:
        Confirmation message
    """
    count = len(import_jobs)
    import_jobs.clear()

    return {
        "message": f"Cleared {count} import job records",
        "status": "success"
    }
