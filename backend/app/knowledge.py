"""Portable, versioned document retrieval with optional provider embeddings."""
from __future__ import annotations

import hashlib
import math
import os
import re
from typing import Any

import httpx
from sqlalchemy import select, func, and_
from sqlalchemy.orm import Session

STOPWORDS = {"a", "an", "and", "are", "as", "at", "be", "by", "can", "do", "does", "for", "from", "how", "i", "in", "is", "it", "me", "my", "of", "on", "or", "the", "to", "what", "when", "where", "which", "with", "you", "your"}


def terms(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]{2,}", text.casefold()) if token not in STOPWORDS}


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def chunk_document(text: str, *, max_words: int = 180, overlap: int = 30) -> list[str]:
    words = text.split()
    if not words:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(words):
        end = min(start + max_words, len(words))
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start = end - overlap
    return chunks


def request_embeddings(texts: list[str]) -> tuple[list[list[float]] | None, str | None]:
    base = os.getenv("AI_BASE_URL", "").rstrip("/")
    key = os.getenv("AI_API_KEY", "")
    model = os.getenv("EMBEDDING_MODEL", "")
    if not base or not key or not model or not texts:
        return None, None
    try:
        with httpx.Client(timeout=30) as client:
            response = client.post(base + "/embeddings", headers={"Authorization": f"Bearer {key}"}, json={"model": model, "input": texts})
            response.raise_for_status()
            data = response.json()["data"]
        if sorted(row["index"] for row in data) != list(range(len(texts))):
            raise ValueError("Embedding response indices are invalid")
        data.sort(key=lambda row: row["index"])
        vectors = [row["embedding"] for row in data]
        if len(vectors) != len(texts) or any(not isinstance(v, list) or not v or len(v) > 8192 or any(not isinstance(n, (int, float)) or not math.isfinite(n) for n in v) for v in vectors):
            raise ValueError("Invalid embedding response")
        if len({len(v) for v in vectors}) != 1:
            raise ValueError("Embedding dimensions do not match")
        return [[float(n) for n in v] for v in vectors], model
    except Exception as exc:
        raise RuntimeError("Embedding provider failed; no knowledge documents were ingested") from exc


def cosine(left: list[float], right: list[float]) -> float:
    if not left or len(left) != len(right):
        return 0.0
    denom = math.sqrt(sum(v * v for v in left)) * math.sqrt(sum(v * v for v in right))
    return 0.0 if denom == 0 else sum(a * b for a, b in zip(left, right)) / denom


def retrieve(session: Session, query: str, *, limit: int = 4) -> list[dict[str, Any]]:
    from .main import KnowledgeChunk, KnowledgeSource

    query_terms = terms(query)
    if not query_terms:
        return []
    latest = select(KnowledgeSource.source_key.label("source_key"), func.max(KnowledgeSource.version).label("version")).group_by(KnowledgeSource.source_key).subquery()
    rows = session.execute(
        select(KnowledgeChunk, KnowledgeSource)
        .join(KnowledgeSource, KnowledgeChunk.source_id == KnowledgeSource.id)
        .join(latest, and_(KnowledgeSource.source_key == latest.c.source_key, KnowledgeSource.version == latest.c.version))
        .order_by(KnowledgeSource.source_key, KnowledgeChunk.chunk_index)
        .limit(3000)
    ).all()
    query_vector = None
    embedded = [chunk for chunk, _source in rows if chunk.embedding and chunk.embedding_model]
    if embedded:
        try:
            vectors, query_model = request_embeddings([query])
            query_vector = vectors[0] if vectors else None
        except RuntimeError:
            query_vector = None
            query_model = None
    scored = []
    for chunk, source in rows:
        chunk_terms = terms(chunk.content)
        lexical = len(query_terms & chunk_terms) / len(query_terms)
        if query_vector and chunk.embedding and chunk.embedding_model and chunk.embedding_model == query_model:
            vector_score = max(0.0, cosine(query_vector, chunk.embedding))
            score = 0.65 * vector_score + 0.35 * lexical
        else:
            score = lexical
        if score >= 0.16:
            scored.append((score, chunk, source))
    # Prefer the newest version of a source when scores tie; older versions remain auditable.
    scored.sort(key=lambda row: (row[0], row[2].version), reverse=True)
    result = []
    seen_sources = set()
    for score, chunk, source in scored:
        if source.source_key in seen_sources:
            continue
        seen_sources.add(source.source_key)
        result.append({"ref": f"K{len(result) + 1}", "text": chunk.content, "source": {"title": source.title, "organization": source.organization, "url": source.url, "version": source.version}})
        if len(result) == limit:
            break
    return result
