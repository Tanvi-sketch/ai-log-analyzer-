import json
from datetime import datetime
from fastapi import APIRouter, HTTPException
from app.models.incident import ChatRequest, ChatResponse
from app.services.ai_service import chat_with_logs
from app.services.incident_service import get_incident_by_id
from app.database.connection import get_collection
from app.utils.serializers import serialize_doc

router = APIRouter()


async def _save_message(role: str, content: str) -> dict:
    col = get_collection("chat_history")
    doc = {"role": role, "content": content, "timestamp": datetime.utcnow()}
    result = await col.insert_one(doc)
    return {"id": str(result.inserted_id), "role": role, "content": content,
            "timestamp": doc["timestamp"].isoformat()}


@router.get("/chat/history")
async def get_chat_history(limit: int = 50):
    col = get_collection("chat_history")
    cursor = col.find({}).sort("timestamp", -1).limit(limit)
    docs = [serialize_doc(d) async for d in cursor]
    docs.reverse()
    return {"success": True, "data": docs}


@router.post("/chat")
async def chat(request: ChatRequest):
    """
    Accepts either:
      - Legacy: { messages: [{role, content}], incident_id? }
      - Simple: { message: str }  (single string wrapped by frontend)
    """
    if not request.messages:
        raise HTTPException(status_code=400, detail="messages list cannot be empty.")

    incident_context: str | None = None
    incident_context_used = False

    if request.incident_id:
        incident = await get_incident_by_id(request.incident_id)
        if incident:
            incident_context = (
                f"Filename: {incident.get('filename')}\n"
                f"Severity: {incident.get('severity')}\n"
                f"Summary: {incident.get('summary')}\n"
                f"Root Cause: {incident.get('root_cause')}\n"
                f"Recommendations: {json.dumps(incident.get('recommendations', []))}\n"
                f"Affected Services: {', '.join(incident.get('affected_services', []))}\n"
                f"Confidence Score: {incident.get('confidence_score')}"
            )
            incident_context_used = True

    messages = [{"role": m.role, "content": m.content} for m in request.messages]

    # Persist user messages
    for m in messages:
        if m["role"] == "user":
            await _save_message("user", m["content"])

    try:
        reply = await chat_with_logs(messages, incident_context)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")

    saved = await _save_message("assistant", reply)

    return {
        "success": True,
        "data": {
            "id": saved["id"],
            "role": "assistant",
            "content": reply,
            "timestamp": saved["timestamp"],
            "incident_context_used": incident_context_used,
        },
    }
