# AI Log Analyzer — Backend

A production-ready FastAPI backend that ingests `.log` / `.txt` files, parses log events, runs AI-powered root cause analysis via OpenAI, stores incidents in MongoDB, and exposes a full REST API including PDF report generation and an AI chatbot.

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Framework | FastAPI 0.115 |
| Runtime | Python 3.11 |
| Database | MongoDB (Motor async driver) |
| AI | OpenAI GPT-4o |
| Validation | Pydantic v2 |
| Server | Uvicorn |
| PDF | ReportLab |

---

## Project Structure

```
backend/
├── app/
│   ├── config/
│   │   └── settings.py          # Environment-based config
│   ├── database/
│   │   └── connection.py        # MongoDB async connection
│   ├── models/
│   │   └── incident.py          # Pydantic models
│   ├── routes/
│   │   ├── analyze.py           # POST /api/analyze
│   │   ├── chat.py              # POST /api/chat
│   │   ├── health.py            # GET  /api/health
│   │   ├── incidents.py         # GET  /api/incidents[/{id}]
│   │   └── upload.py            # POST /api/upload-log
│   ├── services/
│   │   ├── ai_service.py        # OpenAI analysis + chat
│   │   ├── incident_service.py  # MongoDB CRUD + similarity
│   │   └── pdf_service.py       # ReportLab PDF generation
│   ├── utils/
│   │   ├── log_parser.py        # Log parsing utilities
│   │   └── serializers.py       # MongoDB doc serializers
│   └── main.py                  # App entry point
├── uploads/                     # Uploaded log files (gitignored)
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

---

## Setup

### 1. Clone and create virtual environment

```bash
git clone <repo-url>
cd backend
python3.11 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:

```
MONGODB_URI=mongodb://localhost:27017
DATABASE_NAME=log_analyzer
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-4o
UPLOAD_DIR=uploads
MAX_FILE_SIZE_MB=50
ALLOWED_ORIGINS=["http://localhost:3000"]
```

### 4. Run

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Interactive API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## API Reference

### `GET /api/health`
Returns server and database status.

**Response:**
```json
{
  "status": "ok",
  "timestamp": "2024-01-15T10:30:00",
  "database": "connected"
}
```

---

### `POST /api/upload-log`
Upload a `.log` or `.txt` file.

**Form data:** `file` (multipart/form-data)

**Response:**
```json
{
  "filename": "app.log",
  "log_content": "...",
  "line_count": 842,
  "file_size_bytes": 45231,
  "message": "File uploaded successfully..."
}
```

---

### `POST /api/analyze`
Run AI analysis on log content.

**Request body:**
```json
{
  "log_content": "2024-01-15 ERROR DatabaseService Connection refused...",
  "filename": "app.log"
}
```

**Response:**
```json
{
  "incident_id": "65a1b2c3d4e5f6a7b8c9d0e1",
  "severity": "HIGH",
  "summary": "Database connectivity failure causing cascading service errors.",
  "root_cause": "...",
  "recommendations": ["...", "..."],
  "confidence_score": 0.91,
  "affected_services": ["DatabaseService", "AuthService"],
  "timeline": [...],
  "similar_incidents": [...],
  "message": "Log analyzed and incident stored successfully."
}
```

---

### `GET /api/incidents`
List all incidents (paginated).

**Query params:** `skip` (default: 0), `limit` (default: 50, max: 200)

**Response:**
```json
{
  "total": 120,
  "skip": 0,
  "limit": 50,
  "incidents": [...]
}
```

---

### `GET /api/incidents/{id}`
Get full incident details by MongoDB ID.

---

### `GET /api/incidents/{id}/report`
Download a PDF report for an incident.

Returns: `application/pdf` binary stream.

---

### `POST /api/chat`
AI chatbot with optional incident context.

**Request body:**
```json
{
  "messages": [
    {"role": "user", "content": "What caused the database failure?"}
  ],
  "incident_id": "65a1b2c3d4e5f6a7b8c9d0e1"
}
```

**Response:**
```json
{
  "reply": "Based on the incident, the root cause was...",
  "incident_context_used": true
}
```

---

## MongoDB Document Schema

```json
{
  "_id": "ObjectId",
  "filename": "app.log",
  "uploaded_at": "2024-01-15T10:30:00Z",
  "severity": "HIGH",
  "summary": "...",
  "root_cause": "...",
  "recommendations": ["...", "..."],
  "confidence_score": 0.91,
  "affected_services": ["DatabaseService"],
  "timeline": [
    {"timestamp": "2024-01-15T10:00:00", "event": "...", "level": "ERROR"}
  ],
  "raw_logs": "...",
  "similar_incidents": [
    {
      "incident_id": "...",
      "filename": "prev.log",
      "similarity_score": 0.75,
      "summary": "..."
    }
  ]
}
```

---

## Parsed Log Levels

| Level | Detection Pattern |
|-------|------------------|
| ERROR | `ERROR` |
| WARNING | `WARNING`, `WARN` |
| CRITICAL | `CRITICAL`, `FATAL`, `EXCEPTION` |
| FAILED | `FAILED` |
| TIMEOUT | `TIMEOUT` |

---

## Notes

- Log content is truncated to 12,000 characters of relevant lines before sending to OpenAI to control token cost.
- Similar incident matching uses MongoDB aggregation on `affected_services` overlap — no embedding/vector DB required.
- All endpoints are fully async.
