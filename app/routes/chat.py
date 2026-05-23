import json
from fastapi import APIRouter, HTTPException
from app.models.incident import ChatRequest, ChatResponse
from app.services.ai_service import chat_with_logs
from app.services.incident_service import get_incident_by_id

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
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

    try:
        reply = await chat_with_logs(messages, incident_context)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")

    return ChatResponse(reply=reply, incident_context_used=incident_context_used)
