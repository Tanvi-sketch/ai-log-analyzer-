import json
import logging
from openai import AsyncOpenAI
from app.config.settings import settings
from app.models.incident import SeverityLevel, TimelineEvent
from app.utils.log_parser import filter_relevant_lines, extract_affected_services, parse_timeline

logger = logging.getLogger(__name__)

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

ANALYSIS_SYSTEM_PROMPT = """You are an expert DevOps and SRE log analysis AI.
Analyze the provided log content and return a JSON object with EXACTLY these fields:
{
  "severity": "LOW|MEDIUM|HIGH|CRITICAL",
  "summary": "string - 2-3 sentence plain English summary",
  "root_cause": "string - detailed root cause analysis",
  "recommendations": ["string", "string", ...],
  "confidence_score": float between 0.0 and 1.0,
  "affected_services": ["string", ...]
}
Rules:
- severity CRITICAL = data loss, full outage, security breach
- severity HIGH = major feature broken, significant errors
- severity MEDIUM = degraded performance, non-critical failures
- severity LOW = warnings, minor issues
- confidence_score reflects how much evidence supports your analysis
- Return ONLY valid JSON. No markdown. No explanation text.
"""


async def analyze_logs(raw_logs: str, filename: str) -> dict:
    relevant = filter_relevant_lines(raw_logs)
    truncated = relevant[:12000] if len(relevant) > 12000 else relevant

    prompt = f"Filename: {filename}\n\nLog Content:\n{truncated}"

    response = await client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_tokens=1500,
    )

    raw_json = response.choices[0].message.content.strip()

    try:
        result = json.loads(raw_json)
    except json.JSONDecodeError:
        import re
        match = re.search(r"\{.*\}", raw_json, re.DOTALL)
        if match:
            result = json.loads(match.group(0))
        else:
            raise ValueError(f"OpenAI returned non-JSON response: {raw_json[:300]}")

    result["severity"] = SeverityLevel(result.get("severity", "MEDIUM"))
    result["confidence_score"] = float(result.get("confidence_score", 0.5))
    result["recommendations"] = result.get("recommendations", [])
    result["affected_services"] = result.get("affected_services", extract_affected_services(raw_logs))

    timeline = parse_timeline(raw_logs)
    result["timeline"] = [t.model_dump() for t in timeline]

    return result


async def chat_with_logs(
    messages: list[dict],
    incident_context: str | None = None,
) -> str:
    system_content = (
        "You are an expert DevOps assistant specializing in log analysis and incident management. "
        "Answer questions clearly and concisely. "
        "If incident context is provided, use it to give specific answers."
    )

    if incident_context:
        system_content += f"\n\nIncident Context:\n{incident_context}"

    response = await client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[{"role": "system", "content": system_content}] + messages,
        temperature=0.4,
        max_tokens=1000,
    )

    return response.choices[0].message.content.strip()
