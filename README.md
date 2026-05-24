# RootLensAI Backend v2.1.0

Enterprise AI observability backend — FastAPI + Groq + MongoDB.

## What's New in v2.1.0

- **WebSocket telemetry streaming** — `/api/ws/telemetry` for live log/metric events
- **Improved AI prompts** — richer root cause analysis with structured reasoning
- **Better error handling** — typed exceptions, cleaner retry logic
- **Readiness endpoint** — `/api/health/ready` checks DB connectivity
- **Structured logging** — configurable log level via `LOG_LEVEL` env var
- **Timezone-aware datetimes** — all UTC timestamps use timezone.utc
- **Chat history management** — DELETE `/api/chat/history` to clear history
- **Improved analytics** — better hourly bucketing with timezone handling
- **Cleaner module structure** — `chat_history` route separated from `chat`

## Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env: set GROQ_API_KEY and MONGODB_URI

# 3. Run development server
uvicorn app.main:app --reload --port 8000
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Liveness check |
| GET | `/api/health/ready` | Readiness check (DB) |
| POST | `/api/upload-log` | Upload log file |
| POST | `/api/analyze` | AI analysis |
| GET | `/api/incidents` | List incidents |
| GET | `/api/incidents/{id}` | Incident detail |
| GET | `/api/kpi-metrics` | KPI dashboard metrics |
| GET | `/api/system-health` | Service health |
| GET | `/api/analytics` | Time-series analytics |
| GET | `/api/timeline-events` | Recent events |
| GET | `/api/alerts-metrics` | Alert counts |
| GET | `/api/logs` | Paginated log entries |
| POST | `/api/chat` | AI chat |
| GET | `/api/chat/history` | Chat history |
| DELETE | `/api/chat/history` | Clear chat history |
| WS | `/api/ws/telemetry` | Live telemetry stream |

## WebSocket Telemetry

Connect to `ws://localhost:8000/api/ws/telemetry` for a real-time stream of log and metric events:

```json
{ "type": "log", "level": "error", "service": "api-gateway", "message": "...", "timestamp": "..." }
{ "type": "metric", "service": "cache", "metric": "cpu_pct", "value": 74.2, "timestamp": "..." }
{ "type": "heartbeat", "message": "connected", "timestamp": "..." }
```

Send `"ping"` to receive a heartbeat response.

## Environment Variables

See `.env.example` for all configuration options.
