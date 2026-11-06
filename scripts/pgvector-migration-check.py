"""Seed and verify the optional pgvector Alembic migration in CI."""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app import main
from backend.app.knowledge import pgvector_candidate_scores, pgvector_extension_schema

SOURCE_KEY = "pgvector-migration-ci-fixture"
MODEL = "lossfit-ci-fixture-v1"
VECTOR = [1.0, 0.0, 0.0]


def seed() -> None:
    with main.SessionLocal() as session:
        source = main.KnowledgeSource(
            source_key=SOURCE_KEY,
            version=1,
            title="pgvector migration fixture",
            organization="LossFit CI",
            url="https://example.test/pgvector-migration-fixture",
            content_hash=hashlib.sha256(SOURCE_KEY.encode()).hexdigest(),
        )
        session.add(source)
        session.flush()
        session.add(main.KnowledgeChunk(
            source_id=source.id,
            chunk_index=0,
            content="Pre-migration vector backfill fixture.",
            embedding=VECTOR,
            embedding_model=MODEL,
        ))
        session.commit()


def verify() -> None:
    with main.SessionLocal() as session:
        schema = pgvector_extension_schema(session)
        if not schema:
            raise RuntimeError("The pgvector migration did not install the vector sidecar")

        row = session.execute(text(
            "SELECT c.id, v.model, v.dimensions "
            "FROM public.knowledge_chunks c "
            "JOIN public.knowledge_sources s ON s.id = c.source_id "
            "JOIN public.knowledge_vector_embeddings v ON v.chunk_id = c.id "
            "WHERE s.source_key = :source_key"
        ), {"source_key": SOURCE_KEY}).one_or_none()
        if row is None or row.model != MODEL or row.dimensions != len(VECTOR):
            raise RuntimeError("The migration did not backfill the seeded knowledge vector")

        scores = pgvector_candidate_scores(session, MODEL, VECTOR, limit=4)
        if scores is None or scores.get(row.id, 0.0) < 0.999:
            raise RuntimeError("pgvector cosine retrieval did not rank the backfilled vector")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("seed", "verify"))
    action = parser.parse_args().action
    (seed if action == "seed" else verify)()
