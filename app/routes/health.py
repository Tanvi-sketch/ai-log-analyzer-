"""
Health check endpoints — lightweight, no DB dependency for liveness.
"""
import time
from datetime import datetime, timezone
from fastapi import APIRouter
from app.database.connection import get_collection

router = APIRouter()

_start_time = time.time()


@router.get("/health")
async def health():
    """Liveness check — always responds 200 if the process is alive."""
    return {
        "status": "ok",
        "version": "2.1.0",
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "uptime_seconds": round(time.time() - _start_time),
    }


@router.get("/health/ready")
async def readiness():
    """Readiness check — verifies DB connectivity."""
    try:
        col = get_collection("incidents")
        await col.find_one({}, {"_id": 1})
        db_ok = True
        db_error = None
    except Exception as e:
        db_ok = False
        db_error = str(e)

    status_code = 200 if db_ok else 503
    return {
        "status": "ready" if db_ok else "not_ready",
        "database": "connected" if db_ok else f"error: {db_error}",
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
    }
