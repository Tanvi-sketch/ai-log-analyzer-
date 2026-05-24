from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
import io

from app.services.incident_service import get_incident_by_id, list_incidents, count_incidents
from app.services.pdf_service import build_report

router = APIRouter()


@router.get("/incidents")
async def get_incidents(
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=10, ge=1, le=200),
    skip: int = Query(default=None, ge=0),
    limit: int = Query(default=None, ge=1, le=200),
):
    """
    Supports both pagination styles:
    - Frontend style: ?page=1&pageSize=10
    - Legacy: ?skip=0&limit=50
    """
    if skip is not None and limit is not None:
        # Legacy style
        incidents = await list_incidents(skip=skip, limit=limit)
        total = await count_incidents()
        return {"success": True, "data": {"total": total, "skip": skip, "limit": limit, "incidents": incidents}}

    # Frontend paginated style — map to frontend Incident shape
    total = await count_incidents()
    _skip = (page - 1) * pageSize
    raw = await list_incidents(skip=_skip, limit=pageSize)

    items = []
    for inc in raw:
        sev = inc.get("severity", "MEDIUM").lower()
        mapped_sev = "critical" if sev == "critical" else ("warning" if sev in ("high", "medium") else "info")
        items.append({
            "id": inc["id"],
            "type": "Log Analysis",
            "component": inc.get("filename", "unknown"),
            "severity": mapped_sev,
            "duration": "N/A",
            "resolved": False,
            "timestamp": inc.get("uploaded_at"),
            "description": inc.get("summary", ""),
        })

    return {
        "success": True,
        "data": {
            "items": items,
            "total": total,
            "page": page,
            "pageSize": pageSize,
            "hasMore": (_skip + pageSize) < total,
        },
    }


@router.get("/incidents/{incident_id}")
async def get_incident(incident_id: str):
    incident = await get_incident_by_id(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found.")
    return {"success": True, "data": incident}


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
