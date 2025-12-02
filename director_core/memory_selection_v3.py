# director_core/memory_selection_v2.py

import numpy as np
from sentence_transformers import SentenceTransformer, util
import datetime

# 임베딩 모델 (가벼운 버전)
model = SentenceTransformer("all-MiniLM-L6-v2")

def compute_similarity(a, b):
    if not a or not b:
        return 0.0
    emb1 = model.encode(a, convert_to_tensor=True)
    emb2 = model.encode(b, convert_to_tensor=True)
    sim = util.cos_sim(emb1, emb2).item()
    return float(sim)


def score_memory(event, user_text, now):
    # 1) Recency
    try:
        ts = datetime.datetime.fromisoformat(event.get("timestamp"))
        delta_minutes = (now - ts).total_seconds() / 60
        recency_score = max(0.0, 1.0 - (delta_minutes / 2000))
    except:
        recency_score = 0.2

    # 2) Emotional weight
    emo_words = ["감정", "무섭", "울었", "눈물", "슬펐", "좋았", "강렬"]
    emotional_score = 0.2
    if any(w in event.get("raw", "") for w in emo_words):
        emotional_score = 0.8

    # 3) Directive weight
    directive_words = ["정리해", "설정", "역할", "톤", "말투", "기억", "수정"]
    directive_score = 0.2
    if any(w in event.get("summary", "") for w in directive_words):
        directive_score = 1.0

    # 4) User text similarity
    reference_score = compute_similarity(user_text, event.get("summary", ""))

    # 5) Identity relevance
    identity_keys = ["말투", "정체성", "관계", "부감독", "soul"]
    identity_score = 0.2
    if any(k in event.get("tags", []) for k in identity_keys):
        identity_score = 0.9

    total = (
        recency_score * 0.4 +
        emotional_score * 0.2 +
        directive_score * 0.2 +
        reference_score * 0.15 +
        identity_score * 0.05
    )

    return total


def select_top_memories(memories, user_text, now, k=6):
    if not memories:
        return []

    scored = []
    for ev in memories:
        s = score_memory(ev, user_text, now)
        scored.append((s, ev))

    scored.sort(key=lambda x:x[0], reverse=True)
    top = [ev for _, ev in scored[:k]]
    return top