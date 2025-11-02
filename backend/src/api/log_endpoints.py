import logging
from fastapi import APIRouter, Body
from pydantic import BaseModel
from typing import List, Any

# Get the logger configured in main.py
frontend_logger = logging.getLogger("frontend")

router = APIRouter(prefix="/api/v1", tags=["logging"])

class LogEntry(BaseModel):
    timestamp: str
    type: str
    source: str
    message: str
    data: Any = None

@router.post("/log-batch")
async def log_frontend_event_batch(log_entries: List[LogEntry] = Body(...)):
    """Receives a batch of log events from the frontend and logs them."""
    for log_entry in log_entries:
        # Reconstruct a readable log line
        log_line = f"[{log_entry.type.upper()}] [{log_entry.source}] {log_entry.message}"

        # For SSE events, include relevant data in a compact form
        if log_entry.type == 'sse' and log_entry.data:
            sse_data = log_entry.data
            data_parts = []
            if isinstance(sse_data, dict):
                if sse_data.get('phase'):
                    data_parts.append(f"phase: {sse_data.get('phase')}")
                if sse_data.get('status'):
                    data_parts.append(f"status: {sse_data.get('status')}")
                if sse_data.get('expert_id'):
                    data_parts.append(f"expert: {sse_data.get('expert_id')}")
            if data_parts:
                log_line += f" ({', '.join(data_parts)})"

        # For API responses, include status and duration
        elif log_entry.type == 'api' and 'response' in log_entry.source and log_entry.data:
             api_data = log_entry.data
             if isinstance(api_data, dict) and api_data.get('status') and api_data.get('duration') is not None:
                 log_line += f" (status: {api_data.get('status')}, duration: {api_data.get('duration')}ms)"

        frontend_logger.info(log_line)

    return {"status": "logged", "count": len(log_entries)}