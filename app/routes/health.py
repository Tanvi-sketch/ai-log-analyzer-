from fastapi import APIRouter
from datetime import datetime
from app.database.connection import get_db

router = APIRouter()


@router.get("/health")
async def health_check():
    db_status = "disconnected"
    try:
        db = get_db()
        await db.command("ping")
        db_status = "connected"
    except Exception:
        pass

    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "database": db_status,
    }
