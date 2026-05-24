"""
Chat history route — separated from chat.py for cleaner module structure.
"""
from fastapi import APIRouter, Query
from app.database.connection import get_collection
from app.utils.serializers import serialize_doc

router = APIRouter()


@router.get("/chat/history")
async def get_chat_history(limit: int = Query(default=50, ge=1, le=200)):
    col = get_collection("chat_history")
    cursor = col.find({}).sort("timestamp", -1).limit(limit)
    docs = [serialize_doc(d) async for d in cursor]
    docs.reverse()
    return {"success": True, "data": docs}


@router.delete("/chat/history")
async def clear_chat_history():
    """Clear all chat history."""
    col = get_collection("chat_history")
    result = await col.delete_many({})
    return {"success": True, "data": {"deleted": result.deleted_count}}
