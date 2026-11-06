"""Portable, versioned document retrieval with optional provider embeddings."""
from __future__ import annotations

import hashlib
import math
import os
import re
from typing import Any

import httpx
from sqlalchemy import select, func, and_, text
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


def pgvector_extension_schema(session: Session) -> str | None:
    """Return the installed pgvector schema when the optional sidecar exists."""
    if session.get_bind().dialect.name != "postgresql":
        return None
    return session.execute(text(
        "SELECT n.nspname FROM pg_extension e "
        "JOIN pg_namespace n ON n.oid = e.extnamespace "
        "WHERE e.extname = 'vector' "
        "AND to_regclass('public.knowledge_vector_embeddings') IS NOT NULL"
    )).scalar_one_or_none()


def _vector_literal(vector: list[float]) -> str:
    if not vector or len(vector) > 8192:
        raise ValueError("Invalid embedding dimensions")
    if any(not isinstance(value, (int, float)) or not math.isfinite(value) for value in vector):
        raise ValueError("Embedding contains a non-finite value")
    return "[" + ",".join(format(float(value), ".9g") for value in vector) + "]"


def store_pgvector_embeddings(session: Session, items: list[tuple[int, str, list[float]]]) -> bool:
    """Mirror JSON embeddings into pgvector when the migration installed it.

    Returns False when the portable database has no pgvector sidecar. The JSON
    values remain the source of truth and the offline fallback.
    """
    if not items:
        return False
    schema = pgvector_extension_schema(session)
    if not schema:
        return False
    quoted_schema = session.get_bind().dialect.identifier_preparer.quote(schema)
    statement = text(
        "INSERT INTO public.knowledge_vector_embeddings (chunk_id, model, dimensions, embedding) "
        f"VALUES (:chunk_id, :model, :dimensions, CAST(:embedding AS {quoted_schema}.vector)) "
        "ON CONFLICT (chunk_id) DO UPDATE SET model = EXCLUDED.model, "
        "dimensions = EXCLUDED.dimensions, embedding = EXCLUDED.embedding"
    )
    for chunk_id, model, vector in items:
        session.execute(statement, {
            "chunk_id": chunk_id,
            "model": model,
            "dimensions": len(vector),
            "embedding": _vector_literal(vector),
        })
    return True


def pgvector_candidate_scores(session: Session, model: str, vector: list[float], *, limit: int) -> dict[int, float] | None:
    """Fetch exact pgvector nearest candidates; None means use portable cosine."""
    schema = pgvector_extension_schema(session)
    if not schema:
        return None
    dimensions = len(vector)
    if not 1 <= dimensions <= 8192:
        return None
    quoted_schema = session.get_bind().dialect.identifier_preparer.quote(schema)
    vector_type = f"{quoted_schema}.vector({dimensions})"
    distance = f"embedding::{vector_type} OPERATOR({quoted_schema}.<=>) CAST(:query_vector AS {vector_type})"
    rows = session.execute(text(
        "SELECT chunk_id, 1 - (" + distance + ") AS similarity "
        "FROM public.knowledge_vector_embeddings "
        "WHERE model = :model AND dimensions = :dimensions "
        "ORDER BY " + distance + " LIMIT :candidate_limit"
    ), {
        "query_vector": _vector_literal(vector),
        "model": model,
        "dimensions": dimensions,
        "candidate_limit": max(1, min(limit, 128)),
    }).all()
    return {int(row[0]): max(0.0, min(1.0, float(row[1]))) for row in rows}


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
    pgvector_scores = pgvector_candidate_scores(session, query_model, query_vector, limit=max(limit * 8, 32)) if query_vector and query_model else None
    scored = []
    for chunk, source in rows:
        chunk_terms = terms(chunk.content)
        lexical = len(query_terms & chunk_terms) / len(query_terms)
        if query_vector and chunk.embedding and chunk.embedding_model and chunk.embedding_model == query_model:
            if pgvector_scores:
                # Only database-ranked pgvector candidates receive the semantic
                # weight; lexical matches outside the candidate window still rank.
                score = 0.65 * pgvector_scores[chunk.id] + 0.35 * lexical if chunk.id in pgvector_scores else 0.35 * lexical
            else:
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
