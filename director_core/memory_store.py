# director_core/memory_store.py

from typing import List, Dict, Any
from datetime import datetime, timezone
from google.cloud import firestore
import os

# 서비스 계정 파일 지정
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.join(
    os.path.dirname(__file__),
    "credentials",
    "service-account.json"
)

db = firestore.Client()


def save_memory_events(user_id: str, events: List[Dict[str, Any]]):
    if not events:
        return
    
    memories = db.collection("users").document(user_id).collection("memories")
    now = datetime.now(timezone.utc).isoformat()

    batch = db.batch()
    for ev in events:
        doc_ref = memories.document()
        data = {
            "id": doc_ref.id,
            "user_id": user_id,
            "type": ev.get("type", "observation"),
            "summary": ev.get("summary", ""),
            "source": ev.get("source", "telegram"),
            "importance": float(ev.get("importance", 0.5)),
            "tags": ev.get("tags", []),
            "created_at": now,
            "raw": ev.get("raw", {}),
            "media_refs": ev.get("media_refs", []),
        }
        batch.set(doc_ref, data)

    batch.commit()


def load_recent_memories(user_id: str, limit: int = 20):
    memories = (
        db.collection("users")
        .document(user_id)
        .collection("memories")
        .order_by("created_at", direction=firestore.Query.DESCENDING)
        .limit(limit)
        .stream()
    )

    out = []
    for doc in memories:
        d = doc.to_dict()
        out.append(
            {
                "id": d.get("id", doc.id),
                "type": d.get("type"),
                "summary": d.get("summary"),
                "created_at": d.get("created_at"),
                "tags": d.get("tags", []),
            }
        )
    return out