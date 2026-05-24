import re
from typing import List
from app.models.incident import TimelineEvent

LOG_LEVEL_PATTERN = re.compile(
    r"(ERROR|WARNING|WARN|CRITICAL|FAILED|TIMEOUT|FATAL|EXCEPTION)",
    re.IGNORECASE,
)

TIMESTAMP_PATTERNS = [
    re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?"),
    re.compile(r"\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2}"),
    re.compile(r"\w{3} \d{2} \d{2}:\d{2}:\d{2}"),
]

SERVICE_PATTERN = re.compile(
    r"\b([A-Za-z][A-Za-z0-9_-]*(?:Service|Server|Worker|Handler|Client|DB|Cache|Queue|API|Gateway|Auth|Proxy))\b"
)


def extract_timestamp(line: str) -> str | None:
    for pattern in TIMESTAMP_PATTERNS:
        match = pattern.search(line)
        if match:
            return match.group(0)
    return None


def extract_log_level(line: str) -> str | None:
    match = LOG_LEVEL_PATTERN.search(line)
    if match:
        level = match.group(1).upper()
        if level == "WARN":
            return "WARNING"
        if level in ("FATAL", "EXCEPTION"):
            return "CRITICAL"
        return level
    return None


def parse_timeline(raw_logs: str) -> List[TimelineEvent]:
    events: List[TimelineEvent] = []
    seen: set[str] = set()

    for line in raw_logs.splitlines():
        level = extract_log_level(line)
        if not level:
            continue

        timestamp = extract_timestamp(line)
        cleaned = line.strip()

        if cleaned in seen:
            continue
        seen.add(cleaned)

        events.append(
            TimelineEvent(
                timestamp=timestamp,
                event=cleaned[:500],
                level=level,
            )
        )

    events.sort(key=lambda e: e.timestamp or "")
    return events


def extract_affected_services(raw_logs: str) -> List[str]:
    matches = SERVICE_PATTERN.findall(raw_logs)
    unique = list(dict.fromkeys(matches))
    return unique[:20]


def filter_relevant_lines(raw_logs: str) -> str:
    relevant = []
    for line in raw_logs.splitlines():
        if LOG_LEVEL_PATTERN.search(line):
            relevant.append(line.strip())
    return "\n".join(relevant)


def count_by_level(raw_logs: str) -> dict:
    counts = {"ERROR": 0, "WARNING": 0, "CRITICAL": 0, "FAILED": 0, "TIMEOUT": 0}
    for line in raw_logs.splitlines():
        level = extract_log_level(line)
        if level and level in counts:
            counts[level] += 1
    return counts
