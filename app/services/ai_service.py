"""
AI service — Groq SDK integration for log analysis and multi-turn chat.

Key improvements over v1:
- Richer analysis prompt with structured reasoning steps
- Better chat system prompt with incident-awareness
- Cleaner retry logic with typed exceptions
- Async-safe: all blocking Groq calls wrapped in asyncio.to_thread
- Smarter JSON extraction with multiple fallback strategies
"""
import asyncio
import json
import logging
import re
import time

from groq import (
    APIConnectionError,
    APIStatusError,
    AuthenticationError,
    Groq,
    RateLimitError,
)

from app.config.settings import settings
from app.models.incident import SeverityLevel
from app.utils.log_parser import (
    extract_affected_services,
    filter_relevant_lines,
    parse_timeline,
)

logger = logging.getLogger(__name__)

# Single reusable Groq client — thread-safe for concurrent to_thread calls
_client = Groq(api_key=settings.GROQ_API_KEY)

GROQ_MODEL = "llama-3.1-8b-instant"
MAX_LOG_CHARS = 14_000  # Larger context window for richer analysis

# ── Prompts ───────────────────────────────────────────────────────────────────

ANALYSIS_SYSTEM = (
    "You are an elite SRE/DevOps AI specialising in log analysis, incident triage, "
    "and root cause analysis for production systems. "
    "You ALWAYS respond with a single valid JSON object — no markdown fences, "
    "no explanation text, no preamble. Your output begins with '{' and ends with '}'."
)

ANALYSIS_PROMPT = """\
Perform a thorough root cause analysis on the log file below.

Return EXACTLY this JSON structure (no other text):
{{
  "severity": "LOW|MEDIUM|HIGH|CRITICAL",
  "summary": "2-3 sentence plain-English summary of what happened and its impact",
  "root_cause": "Detailed technical root cause — explain WHY it happened, not just WHAT happened",
  "recommendations": [
    "Specific, actionable step 1 with technical detail",
    "Specific, actionable step 2 with technical detail",
    "Specific, actionable step 3 with technical detail"
  ],
  "confidence_score": 0.85,
  "affected_services": ["service-a", "service-b"]
}}

Severity rules (be precise):
- CRITICAL: data loss, complete outage, security breach, cascading system failures
- HIGH: major feature broken, >5% error rate, significant service degradation
- MEDIUM: degraded performance, intermittent failures, non-critical component errors
- LOW: warnings only, minor anomalies, informational events

Reasoning guidelines:
1. Identify the first error/anomaly in the timeline — this is likely the root cause
2. Trace cascading effects from that root cause
3. Consider service dependencies implied by the log context
4. Recommendations must be concrete and implementable

Filename: {filename}

Log content:
{log_content}
"""

CHAT_SYSTEM = """\
You are an expert DevOps AI assistant for RootLensAI — an AI-powered observability platform.

Your role:
- Help engineers understand log analysis results, incidents, and system health
- Provide specific, technical, actionable guidance
- Reference incident context when available
- Be concise but thorough — engineers are time-pressured

Tone: Professional, technical, direct. No fluff.
Format: Use bullet points or numbered lists for multi-step answers.
"""


# ── JSON extraction ───────────────────────────────────────────────────────────

def _extract_json(raw: str) -> dict:
    """
    Robustly extract a JSON object from a model response.
    Handles: clean JSON, markdown fences, prose-wrapped JSON.
    """
    # Strip markdown fences
    cleaned = re.sub(r"```(?:json)?\s*|```", "", raw).strip()

    # Direct parse
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Find first {...} block
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    # Try to find JSON after common prefixes like "Here is the analysis:"
    for line in cleaned.split("\n"):
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                pass

    raise ValueError(f"No valid JSON found in model response (first 300 chars): {raw[:300]}")


def _safe_severity(value: str) -> SeverityLevel:
    val = str(value).upper().strip()
    if val not in ("LOW", "MEDIUM", "HIGH", "CRITICAL"):
        logger.warning("Unexpected severity '%s' — defaulting to MEDIUM", val)
        val = "MEDIUM"
    return SeverityLevel(val)


# ── Groq call with retry ──────────────────────────────────────────────────────

def _call_groq_sync(
    messages: list[dict],
    temperature: float = 0.2,
    max_tokens: int = 1800,
    max_retries: int = 3,
) -> str:
    """
    Synchronous Groq call with exponential backoff.
    Must be wrapped in asyncio.to_thread for async contexts.
    """
    last_exc = None

    for attempt in range(max_retries):
        try:
            response = _client.chat.completions.create(
                model=GROQ_MODEL,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            content = response.choices[0].message.content
            if not content:
                raise ValueError("Groq returned an empty response.")
            return content.strip()

        except AuthenticationError as e:
            raise RuntimeError(
                "Invalid Groq API key. Set GROQ_API_KEY in your .env file."
            ) from e

        except RateLimitError as e:
            wait = 2**attempt
            logger.warning("Rate limit hit (attempt %d/%d), retrying in %ds", attempt + 1, max_retries, wait)
            last_exc = e
            if attempt < max_retries - 1:
                time.sleep(wait)

        except APIConnectionError as e:
            wait = 2**attempt
            logger.warning("Connection error (attempt %d/%d), retrying in %ds", attempt + 1, max_retries, wait)
            last_exc = e
            if attempt < max_retries - 1:
                time.sleep(wait)

        except APIStatusError as e:
            if e.status_code == 400:
                raise RuntimeError(f"Groq rejected the request: {e.message}") from e
            if e.status_code in (503, 529):
                wait = 2**attempt
                logger.warning("Groq unavailable (attempt %d/%d), retrying in %ds", attempt + 1, max_retries, wait)
                last_exc = e
                if attempt < max_retries - 1:
                    time.sleep(wait)
            else:
                raise RuntimeError(f"Groq API error {e.status_code}: {e.message}") from e

        except ValueError:
            raise

        except Exception as e:
            raise RuntimeError(f"Unexpected Groq error: {e}") from e

    if isinstance(last_exc, RateLimitError):
        raise RuntimeError("Groq rate limit exceeded — please wait a moment.") from last_exc
    raise RuntimeError("Groq service unavailable — please try again.") from last_exc


# ── Public API ────────────────────────────────────────────────────────────────

async def analyze_logs(raw_logs: str, filename: str) -> dict:
    """
    Analyze log content with Groq and return structured analysis.
    """
    relevant = filter_relevant_lines(raw_logs)
    truncated = relevant[:MAX_LOG_CHARS]

    prompt = ANALYSIS_PROMPT.format(filename=filename, log_content=truncated)
    messages = [
        {"role": "system", "content": ANALYSIS_SYSTEM},
        {"role": "user", "content": prompt},
    ]

    try:
        raw_json = await asyncio.to_thread(_call_groq_sync, messages, 0.2, 1800)
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"Unexpected error during log analysis: {e}") from e

    result = _extract_json(raw_json)

    # Normalise with safe defaults
    result["severity"] = _safe_severity(result.get("severity", "MEDIUM"))
    result["confidence_score"] = max(0.0, min(1.0, float(result.get("confidence_score", 0.5))))
    result["recommendations"] = result.get("recommendations") or ["Review the logs manually for additional context."]
    result["affected_services"] = result.get("affected_services") or extract_affected_services(raw_logs)
    result["summary"] = result.get("summary") or "No summary available."
    result["root_cause"] = result.get("root_cause") or "Root cause could not be determined from the provided logs."

    timeline = parse_timeline(raw_logs)
    result["timeline"] = [t.model_dump() for t in timeline]

    return result


async def chat_with_logs(
    messages: list[dict],
    incident_context: str | None = None,
) -> str:
    """
    Multi-turn AI chat with optional incident context injection.
    """
    if not messages:
        return "No message provided."

    system = CHAT_SYSTEM
    if incident_context:
        system += f"\n\n--- INCIDENT CONTEXT ---\n{incident_context}\n--- END CONTEXT ---"

    groq_messages = [{"role": "system", "content": system}]
    for m in messages:
        role = "user" if m["role"] == "user" else "assistant"
        groq_messages.append({"role": role, "content": m["content"]})

    try:
        return await asyncio.to_thread(_call_groq_sync, groq_messages, 0.4, 1200)
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"Unexpected chat error: {e}") from e
