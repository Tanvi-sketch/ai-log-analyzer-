from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
import io

from app.services.incident_service import get_incident_by_id, list_incidents, count_incidents
from app.services.pdf_service import build_report

router = APIRouter()


@router.get("/incidents")
async def get_incidents(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
):
    incidents = await list_incidents(skip=skip, limit=limit)
    total = await count_incidents()

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "incidents": incidents,
    }


@router.get("/incidents/{incident_id}")
async def get_incident(incident_id: str):
    incident = await get_incident_by_id(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found.")
    return incident


@router.get("/incidents/{incident_id}/report")
async def download_incident_report(incident_id: str):
    incident = await get_incident_by_id(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found.")

    try:
        pdf_bytes = build_report(incident)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")

    filename = f"incident_report_{incident_id[:8]}.pdf"

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
