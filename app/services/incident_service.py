import logging
from datetime import datetime
from typing import List, Optional
from bson import ObjectId

from app.database.connection import get_collection
from app.models.incident import IncidentCreate, IncidentResponse, IncidentListItem, SimilarIncident
from app.utils.serializers import serialize_doc, to_object_id

logger = logging.getLogger(__name__)

COLLECTION = "incidents"


async def save_incident(data: dict, filename: str, raw_logs: str) -> str:
    collection = get_collection(COLLECTION)

    doc = {
        "filename": filename,
        "uploaded_at": datetime.utcnow(),
        "severity": data["severity"].value if hasattr(data["severity"], "value") else data["severity"],
        "summary": data["summary"],
        "root_cause": data["root_cause"],
        "recommendations": data["recommendations"],
        "confidence_score": data["confidence_score"],
        "affected_services": data["affected_services"],
        "timeline": data["timeline"],
        "raw_logs": raw_logs,
        "similar_incidents": [],
    }

    result = await collection.insert_one(doc)
    incident_id = str(result.inserted_id)

    similar = await find_similar_incidents(incident_id, data["summary"], data["affected_services"])
    similar_docs = [s.model_dump() for s in similar]

    await collection.update_one(
        {"_id": result.inserted_id},
        {"$set": {"similar_incidents": similar_docs}},
    )

    return incident_id


async def get_incident_by_id(incident_id: str) -> Optional[dict]:
    collection = get_collection(COLLECTION)
    try:
        oid = to_object_id(incident_id)
    except ValueError:
        return None

    doc = await collection.find_one({"_id": oid})
    if doc:
        return serialize_doc(doc)
    return None


async def list_incidents(skip: int = 0, limit: int = 50) -> List[dict]:
    collection = get_collection(COLLECTION)
    cursor = collection.find(
        {},
        {
            "filename": 1,
            "uploaded_at": 1,
            "severity": 1,
            "summary": 1,
            "confidence_score": 1,
            "affected_services": 1,
        },
    ).sort("uploaded_at", -1).skip(skip).limit(limit)

    results = []
    async for doc in cursor:
        results.append(serialize_doc(doc))
    return results


async def find_similar_incidents(
    current_id: str,
    summary: str,
    affected_services: List[str],
    limit: int = 3,
) -> List[SimilarIncident]:
    collection = get_collection(COLLECTION)

    pipeline = [
        {"$match": {"_id": {"$ne": ObjectId(current_id)}}},
        {
            "$addFields": {
                "service_overlap": {
                    "$size": {
                        "$setIntersection": ["$affected_services", affected_services or []]
                    }
                }
            }
        },
        {"$sort": {"service_overlap": -1, "uploaded_at": -1}},
        {"$limit": limit},
        {
            "$project": {
                "filename": 1,
                "summary": 1,
                "service_overlap": 1,
            }
        },
    ]

    similar: List[SimilarIncident] = []
    async for doc in collection.aggregate(pipeline):
        overlap = doc.get("service_overlap", 0)
        max_possible = max(len(affected_services), 1)
        score = round(min(overlap / max_possible, 1.0), 2)
        similar.append(
            SimilarIncident(
                incident_id=str(doc["_id"]),
                filename=doc["filename"],
                similarity_score=score,
                summary=doc.get("summary", ""),
            )
        )

    return similar


async def count_incidents() -> int:
    collection = get_collection(COLLECTION)
    return await collection.count_documents({})
