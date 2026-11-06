import pytest
from sqlalchemy.dialects.postgresql import dialect as postgres_dialect

from backend.app import main
from backend.app.knowledge import _vector_literal, pgvector_candidate_scores, pgvector_extension_schema, store_pgvector_embeddings


class Result:
    def __init__(self, rows=(), scalar=None):
        self.rows = rows
        self.scalar = scalar

    def scalar_one_or_none(self):
        return self.scalar

    def all(self):
        return self.rows


class FakeSession:
    def __init__(self, extension_schema="extensions", rows=((7, 0.85),)):
        self.bind = type("Bind", (), {"dialect": postgres_dialect()})()
        self.extension_schema = extension_schema
        self.rows = rows
        self.statements = []

    def get_bind(self):
        return self.bind

    def execute(self, statement, params=None):
        self.statements.append((str(statement), params))
        if "pg_extension" in str(statement):
            return Result(scalar=self.extension_schema)
        return Result(rows=self.rows)


def test_vector_literal_is_bounded_and_finite():
    assert _vector_literal([1, -0.25, 3.5]) == "[1,-0.25,3.5]"
    with pytest.raises(ValueError, match="dimensions"):
        _vector_literal([])
    with pytest.raises(ValueError, match="non-finite"):
        _vector_literal([float("nan")])


def test_pgvector_query_uses_extension_schema_and_model_dimension_filter():
    session = FakeSession(rows=((7, 0.85), (9, -0.2)))

    scores = pgvector_candidate_scores(session, "model-v1", [1, 0, 0], limit=16)

    assert scores == {7: 0.85, 9: 0.0}
    sql, params = session.statements[-1]
    assert "extensions.vector(3)" in sql
    assert "OPERATOR(extensions.<=>)" in sql
    assert "WHERE model = :model AND dimensions = :dimensions" in sql
    assert params == {
        "query_vector": "[1,0,0]",
        "model": "model-v1",
        "dimensions": 3,
        "candidate_limit": 16,
    }


def test_pgvector_query_falls_back_when_extension_is_not_installed():
    session = FakeSession(extension_schema=None)

    assert pgvector_candidate_scores(session, "model-v1", [1, 0], limit=8) is None
    assert len(session.statements) == 1


def test_pgvector_database_round_trip_when_extension_is_available():
    from uuid import uuid4

    with main.SessionLocal() as session:
        if not pgvector_extension_schema(session):
            pytest.skip("pgvector is not installed in this PostgreSQL instance")

        source = main.KnowledgeSource(
            source_key=f"pgvector-test-{uuid4().hex}", version=1,
            title="pgvector integration fixture", organization="LossFit CI",
            url="https://example.test/pgvector-fixture", content_hash="a" * 64,
        )
        session.add(source)
        session.flush()
        chunk = main.KnowledgeChunk(
            source_id=source.id, chunk_index=0, content="cosine retrieval fixture",
            embedding=[1.0, 0.0, 0.0], embedding_model="pgvector-test-model",
        )
        session.add(chunk)
        session.flush()

        assert store_pgvector_embeddings(session, [(chunk.id, "pgvector-test-model", [1.0, 0.0, 0.0])])
        scores = pgvector_candidate_scores(session, "pgvector-test-model", [1.0, 0.0, 0.0], limit=8)
        assert scores is not None
        assert scores[chunk.id] == pytest.approx(1.0)

        session.rollback()
