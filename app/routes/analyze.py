from fastapi import APIRouter, HTTPException
from app.models.incident import AnalyzeRequest, AnalyzeResponse, TimelineEvent, SimilarIncident
from app.services.ai_service import analyze_logs
from app.services.incident_service import save_incident

router = APIRouter()


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_log(request: AnalyzeRequest):
    if not request.log_content.strip():
        raise HTTPException(status_code=400, detail="log_content cannot be empty.")

    if len(request.log_content) > 5_000_000:
        raise HTTPException(status_code=413, detail="log_content too large. Max 5MB of text.")

    try:
        analysis = await analyze_logs(request.log_content, request.filename)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI analysis failed: {str(e)}")

    try:
        incident_id = await save_incident(analysis, request.filename, request.log_content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save incident: {str(e)}")

    timeline = [TimelineEvent(**t) if isinstance(t, dict) else t for t in analysis.get("timeline", [])]
    similar = [SimilarIncident(**s) if isinstance(s, dict) else s for s in analysis.get("similar_incidents", [])]

    return AnalyzeResponse(
        incident_id=incident_id,
        severity=analysis["severity"],
        summary=analysis["summary"],
        root_cause=analysis["root_cause"],
        recommendations=analysis["recommendations"],
        confidence_score=analysis["confidence_score"],
        affected_services=analysis["affected_services"],
        timeline=timeline,
        similar_incidents=similar,
        message="Log analyzed and incident stored successfully.",
    )
