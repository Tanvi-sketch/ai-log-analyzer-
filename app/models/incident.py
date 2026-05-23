from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from enum import Enum


class SeverityLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class TimelineEvent(BaseModel):
    timestamp: Optional[str] = None
    event: str
    level: str


class SimilarIncident(BaseModel):
    incident_id: str
    filename: str
    similarity_score: float
    summary: str


class IncidentCreate(BaseModel):
    filename: str
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)
    severity: SeverityLevel
    summary: str
    root_cause: str
    recommendations: List[str]
    confidence_score: float = Field(ge=0.0, le=1.0)
    affected_services: List[str]
    timeline: List[TimelineEvent]
    raw_logs: str
    similar_incidents: List[SimilarIncident] = []


class IncidentResponse(BaseModel):
    id: str
    filename: str
    uploaded_at: datetime
    severity: SeverityLevel
    summary: str
    root_cause: str
    recommendations: List[str]
    confidence_score: float
    affected_services: List[str]
    timeline: List[TimelineEvent]
    raw_logs: str
    similar_incidents: List[SimilarIncident]


class IncidentListItem(BaseModel):
    id: str
    filename: str
    uploaded_at: datetime
    severity: SeverityLevel
    summary: str
    confidence_score: float
    affected_services: List[str]


class AnalyzeRequest(BaseModel):
    log_content: str
    filename: str


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    incident_id: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    incident_context_used: bool


class UploadResponse(BaseModel):
    filename: str
    log_content: str
    line_count: int
    file_size_bytes: int
    message: str


class AnalyzeResponse(BaseModel):
    incident_id: str
    severity: SeverityLevel
    summary: str
    root_cause: str
    recommendations: List[str]
    confidence_score: float
    affected_services: List[str]
    timeline: List[TimelineEvent]
    similar_incidents: List[SimilarIncident]
    message: str


class APIResponse(BaseModel):
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None
