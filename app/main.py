"""
RootLensAI Backend — Production-grade FastAPI application.
"""
import asyncio
import json
import logging
import random
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.database.connection import connect_db, disconnect_db
from app.routes import analyze, chat, chat_history, dashboard, health, incidents, upload
from app.config.settings import settings

logger = logging.getLogger(__name__)

# ── WebSocket connection manager ───────────────────────────────────────────────

class TelemetryBroadcaster:
    def __init__(self):
        self._connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._connections.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self._connections:
            self._connections.remove(ws)

    async def broadcast(self, event: dict):
        dead = []
        for ws in self._connections:
            try:
                await ws.send_json(event)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

broadcaster = TelemetryBroadcaster()

MOCK_SERVICES = ["api-gateway", "auth-service", "db-proxy", "cache", "ml-pipeline", "worker-queue"]
MOCK_MESSAGES = [
    ("info", "Health check passed — latency 12ms"),
    ("info", "Request handled in 45ms — status 200"),
    ("info", "Cache hit ratio: 94.3% — pool healthy"),
    ("warning", "Connection pool at 78% capacity"),
    ("warning", "Response time elevated: 320ms (threshold: 300ms)"),
    ("error", "Timeout connecting to upstream service after 5000ms"),
    ("error", "Retry attempt 2/3 — service unavailable"),
    ("info", "Worker processed 142 jobs in last 60s"),
    ("debug", "GC cycle completed — heap freed 18MB"),
    ("info", "Deployment rollout: 25% traffic shifted"),
]

async def _telemetry_loop():
    while True:
        await asyncio.sleep(random.uniform(2, 5))
        if not broadcaster._connections:
            continue
        level, msg = random.choice(MOCK_MESSAGES)
        service = random.choice(MOCK_SERVICES)
        event = {
            "type": "log",
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "level": level,
            "service": service,
            "message": msg,
        }
        await broadcaster.broadcast(event)
        if random.random() < 0.3:
            await broadcaster.broadcast({
                "type": "metric",
                "timestamp": datetime.now(tz=timezone.utc).isoformat(),
                "service": service,
                "metric": random.choice(["cpu_pct", "memory_mb", "rps", "latency_p99"]),
                "value": round(random.uniform(10, 95), 1),
            })

@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    task = asyncio.create_task(_telemetry_loop())
    try:
        yield
    finally:
        task.cancel()
        await disconnect_db()

app = FastAPI(
    title="RootLensAI API",
    description="Enterprise AI observability — log analysis, incident management, AI root cause analysis.",
    version="2.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception: %s", exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"success": False, "error": "Internal server error", "detail": str(exc)},
    )

app.include_router(health.router, prefix="/api", tags=["Health"])
app.include_router(upload.router, prefix="/api", tags=["Upload"])
app.include_router(analyze.router, prefix="/api", tags=["Analyze"])
app.include_router(incidents.router, prefix="/api", tags=["Incidents"])
app.include_router(chat.router, prefix="/api", tags=["Chat"])
app.include_router(chat_history.router, prefix="/api", tags=["Chat History"])
app.include_router(dashboard.router, prefix="/api", tags=["Dashboard"])

@app.websocket("/api/ws/telemetry")
async def ws_telemetry(websocket: WebSocket):
    await broadcaster.connect(websocket)
    await websocket.send_json({
        "type": "heartbeat",
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "message": "RootLensAI telemetry stream connected",
    })
    try:
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                if data == "ping":
                    await websocket.send_json({"type": "heartbeat", "timestamp": datetime.now(tz=timezone.utc).isoformat()})
            except asyncio.TimeoutError:
                pass
    except WebSocketDisconnect:
        broadcaster.disconnect(websocket)
    except Exception:
        broadcaster.disconnect(websocket)

@app.get("/")
async def root():
    return {"status": "RootLensAI API running", "version": "2.1.0", "docs": "/docs", "ws": "/api/ws/telemetry"}
