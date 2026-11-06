"""Ingest reviewed, versioned knowledge JSON into the configured LossFit DB."""
import json
from pathlib import Path
import sys
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from backend.app.knowledge import chunk_document, content_hash, request_embeddings, store_pgvector_embeddings
from backend.app.main import KnowledgeChunk, KnowledgeSource, SessionLocal


def main() -> int:
    source_path = Path(__file__).resolve().parent.parent / "backend" / "knowledge" / "sources.json"
    documents = json.loads(source_path.read_text(encoding="utf-8"))
    added_sources = added_chunks = 0
    embedding_models = set()
    pgvector_used = False
    with SessionLocal() as session:
        try:
            for document in documents:
                key = document["source_key"]
                text = document["text"].strip()
                url = document["url"]
                if not key or len(key) > 100 or not text or len(text) > 20000 or urlparse(url).scheme != "https":
                    raise ValueError(f"Invalid reviewed knowledge source: {key!r}")
                digest = content_hash(text)
                existing = session.scalar(select(KnowledgeSource).where(KnowledgeSource.source_key == key, KnowledgeSource.version == document["version"]))
                if existing:
                    if existing.content_hash != digest:
                        raise ValueError(f"Source {key} version {document['version']} changed; increase its version instead of replacing history")
                    continue
                parts = chunk_document(text)
                vectors, model = request_embeddings(parts)
                if model:
                    embedding_models.add(model)
                source = KnowledgeSource(source_key=key, version=document["version"], title=document["title"], organization=document["organization"], url=url, content_hash=digest)
                session.add(source)
                session.flush()
                chunks = []
                for index, part in enumerate(parts):
                    chunk = KnowledgeChunk(source_id=source.id, chunk_index=index, content=part, embedding=vectors[index] if vectors else None, embedding_model=model)
                    session.add(chunk)
                    chunks.append(chunk)
                session.flush()
                if vectors and model:
                    pgvector_used = store_pgvector_embeddings(
                        session,
                        [(chunk.id, model, vectors[index]) for index, chunk in enumerate(chunks)],
                    ) or pgvector_used
                added_sources += 1
                added_chunks += len(parts)
            session.commit()
        except Exception:
            session.rollback()
            raise
    provider_status = 'used (' + ', '.join(sorted(embedding_models)) + ')' if embedding_models else 'unavailable, lexical adapter active'
    vector_status = 'pgvector storage active' if pgvector_used else 'portable JSON/cosine storage active'
    print(f"Ingested {added_sources} new reviewed sources and {added_chunks} chunks; provider embeddings {provider_status}; {vector_status}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
