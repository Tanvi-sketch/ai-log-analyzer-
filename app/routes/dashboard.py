"""
Dashboard routes — aggregated metrics from incidents collection.
All endpoints follow the { success, data } envelope pattern.
"""
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Query
from app.database.connection import get_collection
from app.utils.serializers import serialize_doc

router = APIRouter()

SEVERITY_WEIGHT = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}


async def _all_incidents() -> list[dict]:
    col = get_collection("incidents")
    cursor = col.find({}).sort("uploaded_at", -1)
    return [serialize_doc(d) async for d in cursor]


# ── /api/kpi-metrics ──────────────────────────────────────────────────────────

@router.get("/kpi-metrics")
async def kpi_metrics():
    incidents = await _all_incidents()
    total = len(incidents)

    if total == 0:
        return {"success": True, "data": {"requestsPerSecond": 0, "avgLatency": 0, "errorRate": 0, "uptime": 100.0}}

    critical_count = sum(1 for i in incidents if i.get("severity") == "CRITICAL")
    high_count = sum(1 for i in incidents if i.get("severity") == "HIGH")

    error_rate = round((critical_count + high_count) / total * 100, 2)
    uptime = round(max(0.0, 100.0 - (critical_count * 2.5) - (high_count * 0.8)), 2)

    avg_confidence = sum(i.get("confidence_score", 0.5) for i in incidents) / total
    avg_latency = round(120 + (1 - avg_confidence) * 480)

    timeline_events = sum(len(i.get("timeline", [])) for i in incidents)
    rps = round(timeline_events / max(total, 1) * 10, 1)

    return {
        "success": True,
        "data": {
            "requestsPerSecond": rps,
            "avgLatency": avg_latency,
            "errorRate": error_rate,
            "uptime": uptime,
        },
    }


# ── /api/system-health ────────────────────────────────────────────────────────

@router.get("/system-health")
async def system_health():
    incidents = await _all_incidents()

    service_stats: dict[str, dict] = {}
    for inc in incidents:
        sev = inc.get("severity", "LOW")
        weight = SEVERITY_WEIGHT.get(sev, 1)
        for svc in inc.get("affected_services", []):
            if svc not in service_stats:
                service_stats[svc] = {"total": 0, "weight_sum": 0, "incidents": 0}
            service_stats[svc]["total"] += 1
            service_stats[svc]["weight_sum"] += weight
            service_stats[svc]["incidents"] += 1

    services = []
    for name, stats in list(service_stats.items())[:10]:
        avg_w = stats["weight_sum"] / stats["total"]
        status = "critical" if avg_w >= 3.5 else ("degraded" if avg_w >= 2.0 else "healthy")
        cpu = min(95, round(avg_w * 18 + stats["incidents"] * 2))
        memory = min(95, round(avg_w * 15 + stats["incidents"] * 1.5))

        services.append({
            "name": name,
            "status": status,
            "cpu": cpu,
            "memory": memory,
            "requests": stats["incidents"] * 100,
        })

    services.insert(0, {
        "name": "LogAnalyzer",
        "status": "healthy",
        "cpu": 12,
        "memory": 34,
        "requests": len(incidents) * 50,
    })

    return {"success": True, "data": services}


# ── /api/analytics ────────────────────────────────────────────────────────────

@router.get("/analytics")
async def analytics(hours: int = Query(default=24, ge=1, le=168)):
    col = get_collection("incidents")
    since = datetime.now(tz=timezone.utc) - timedelta(hours=hours)

    bucket_map: dict[str, dict] = {}
    cursor = col.find({"uploaded_at": {"$gte": since}}).sort("uploaded_at", 1)
    async for doc in cursor:
        inc = serialize_doc(doc)
        ts = doc.get("uploaded_at", datetime.now(tz=timezone.utc))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        hour_key = ts.strftime("%H:00")
        if hour_key not in bucket_map:
            bucket_map[hour_key] = {"requests": 0, "latency": 120, "errors": 0, "count": 0}
        sev = inc.get("severity", "LOW")
        weight = SEVERITY_WEIGHT.get(sev, 1)
        bucket_map[hour_key]["requests"] += max(1, len(inc.get("timeline", []))) * 12
        bucket_map[hour_key]["latency"] = round(120 + weight * 45)
        bucket_map[hour_key]["errors"] += 1 if sev in ("HIGH", "CRITICAL") else 0
        bucket_map[hour_key]["count"] += 1

    result = []
    now = datetime.now(tz=timezone.utc)
    for h in range(hours - 1, -1, -1):
        t = now - timedelta(hours=h)
        k = t.strftime("%H:00")
        entry = bucket_map.get(k, {"requests": 0, "latency": 120, "errors": 0})
        result.append({"time": k, "requests": entry["requests"], "latency": entry["latency"], "errors": entry["errors"]})

    return {"success": True, "data": result}


# ── /api/timeline-events ──────────────────────────────────────────────────────

@router.get("/timeline-events")
async def timeline_events(limit: int = Query(default=10, ge=1, le=50)):
    incidents = await _all_incidents()
    events = []
    for inc in incidents[:limit]:
        sev = inc.get("severity", "LOW")
        status = "critical" if sev in ("CRITICAL", "HIGH") else ("warning" if sev == "MEDIUM" else "info")
        events.append({
            "id": inc["id"],
            "title": f"[{sev}] {inc.get('filename', 'unknown')} — {inc.get('summary', '')[:80]}",
            "timestamp": inc.get("uploaded_at"),
            "status": status,
        })
    return {"success": True, "data": events}


# ── /api/alerts-metrics ───────────────────────────────────────────────────────

@router.get("/alerts-metrics")
async def alerts_metrics():
    incidents = await _all_incidents()
    return {
        "success": True,
        "data": {
            "critical": sum(1 for i in incidents if i.get("severity") == "CRITICAL"),
            "warning": sum(1 for i in incidents if i.get("severity") in ("HIGH", "MEDIUM")),
            "info": sum(1 for i in incidents if i.get("severity") == "LOW"),
            "resolved": 0,
        },
    }


# ── /api/logs ─────────────────────────────────────────────────────────────────

@router.get("/logs")
async def logs(
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=20, ge=1, le=100),
    level: str | None = None,
):
    incidents = await _all_incidents()
    all_logs = []

    for inc in incidents:
        for ev in inc.get("timeline", []):
            ev_level = str(ev.get("level", "INFO")).lower()
            if ev_level in ("critical", "fatal", "exception", "error"):
                ev_level = "error"
            elif ev_level in ("warning", "warn", "failed", "timeout"):
                ev_level = "warning"
            elif ev_level == "debug":
                ev_level = "debug"
            else:
                ev_level = "info"

            all_logs.append({
                "id": f"{inc['id']}_{len(all_logs)}",
                "level": ev_level,
                "message": ev.get("event", ""),
                "service": inc.get("filename", "unknown"),
                "timestamp": ev.get("timestamp") or inc.get("uploaded_at"),
                "context": {"incident_id": inc["id"], "severity": inc.get("severity")},
            })

    if level:
        all_logs = [l for l in all_logs if l["level"] == level.lower()]

    total = len(all_logs)
    start = (page - 1) * pageSize
    return {
        "success": True,
        "data": {
            "items": all_logs[start: start + pageSize],
            "total": total,
            "page": page,
            "pageSize": pageSize,
            "hasMore": (start + pageSize) < total,
        },
    }


# ── /api/reports ──────────────────────────────────────────────────────────────

@router.get("/reports")
async def reports():
    incidents = await _all_incidents()
    return {
        "success": True,
        "data": [
            {
                "id": inc["id"],
                "name": f"Incident Report — {inc.get('filename', 'unknown')}",
                "type": "incident",
                "generatedAt": inc.get("uploaded_at"),
                "data": {
                    "severity": inc.get("severity"),
                    "summary": inc.get("summary"),
                    "confidence_score": inc.get("confidence_score"),
                    "affected_services": inc.get("affected_services", []),
                },
            }
            for inc in incidents[:20]
        ],
    }


@router.post("/reports/generate")
async def generate_report(body: dict):
    report_type = body.get("type", "incident")
    incidents = await _all_incidents()
    data: dict = {}

    if report_type == "incident":
        data = {
            "total": len(incidents),
            "by_severity": {
                sev: sum(1 for i in incidents if i.get("severity") == sev)
                for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
            },
        }
    elif report_type == "performance":
        scores = [i.get("confidence_score", 0.5) for i in incidents]
        data = {"avg_confidence": round(sum(scores) / max(len(scores), 1), 3), "total_analyzed": len(incidents)}
    elif report_type == "health":
        data = {
            "critical_incidents": sum(1 for i in incidents if i.get("severity") == "CRITICAL"),
            "total": len(incidents),
        }

    return {
        "success": True,
        "data": {
            "id": f"report_{datetime.now(tz=timezone.utc).strftime('%Y%m%d%H%M%S')}",
            "name": f"{report_type.capitalize()} Report",
            "type": report_type,
            "generatedAt": datetime.now(tz=timezone.utc).isoformat(),
            "data": data,
        },
    }


# ── /api/incidents-paginated ──────────────────────────────────────────────────

@router.get("/incidents-paginated")
async def incidents_paginated(
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=10, ge=1, le=100),
):
    col = get_collection("incidents")
    total = await col.count_documents({})
    skip = (page - 1) * pageSize

    cursor = (
        col.find(
            {},
            {
                "filename": 1,
                "uploaded_at": 1,
                "severity": 1,
                "summary": 1,
                "confidence_score": 1,
                "affected_services": 1,
            },
        )
        .sort("uploaded_at", -1)
        .skip(skip)
        .limit(pageSize)
    )

    items = []
    async for doc in cursor:
        inc = serialize_doc(doc)
        sev = inc.get("severity", "MEDIUM").upper()
        mapped = "critical" if sev == "CRITICAL" else ("warning" if sev in ("HIGH", "MEDIUM") else "info")
        items.append({
            "id": inc["id"],
            "type": "Log Analysis",
            "component": inc.get("filename", "unknown"),
            "severity": mapped,
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
            "hasMore": (skip + pageSize) < total,
        },
    }
