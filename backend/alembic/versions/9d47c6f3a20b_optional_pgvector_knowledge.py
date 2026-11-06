"""Add an optional pgvector sidecar for reviewed knowledge embeddings.

Local PostgreSQL installations without the vector extension keep using the
portable JSON/cosine adapter. Hosted PostgreSQL can store and rank embeddings
with pgvector without changing the portable source records.
"""
from alembic import op
import sqlalchemy as sa

revision = "9d47c6f3a20b"
down_revision = "b8c4f97a61d2"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    available = bind.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'vector')"
    )).scalar_one()
    if not available:
        return

    # Supabase commonly keeps extensions in `extensions`; standard PostgreSQL
    # installs use `public`. Use a savepoint so restricted migration roles can
    # retain the portable fallback if CREATE EXTENSION is unavailable to them.
    extension_schema_exists = bind.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'extensions')"
    )).scalar_one()
    try:
        with bind.begin_nested():
            if extension_schema_exists:
                bind.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA extensions")
            else:
                bind.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector")
    except Exception:
        return

    extension = bind.execute(sa.text(
        "SELECT n.nspname FROM pg_extension e "
        "JOIN pg_namespace n ON n.oid = e.extnamespace WHERE e.extname = 'vector'"
    )).scalar_one_or_none()
    if not extension:
        return

    quote = bind.dialect.identifier_preparer.quote
    vector_schema = quote(extension)
    runtime_role_exists = bind.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'lossfit_app')"
    )).scalar_one()
    if runtime_role_exists:
        bind.exec_driver_sql(f"GRANT USAGE ON SCHEMA {vector_schema} TO lossfit_app")
    bind.exec_driver_sql(
        "CREATE TABLE public.knowledge_vector_embeddings ("
        "chunk_id integer PRIMARY KEY REFERENCES public.knowledge_chunks(id) ON DELETE CASCADE, "
        "model varchar(160) NOT NULL, "
        "dimensions integer NOT NULL CHECK (dimensions BETWEEN 1 AND 8192), "
        f"embedding {vector_schema}.vector NOT NULL)"
    )
    bind.exec_driver_sql("ALTER TABLE public.knowledge_vector_embeddings ENABLE ROW LEVEL SECURITY")
    bind.exec_driver_sql("REVOKE ALL ON public.knowledge_vector_embeddings FROM PUBLIC")
    bind.exec_driver_sql("""
        DO $$ BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
            EXECUTE 'REVOKE ALL ON public.knowledge_vector_embeddings FROM anon';
          END IF;
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
            EXECUTE 'REVOKE ALL ON public.knowledge_vector_embeddings FROM authenticated';
          END IF;
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
            EXECUTE 'REVOKE ALL ON public.knowledge_vector_embeddings FROM service_role';
          END IF;
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'lossfit_app') THEN
            EXECUTE 'GRANT SELECT, INSERT, UPDATE, DELETE ON public.knowledge_vector_embeddings TO lossfit_app';
            EXECUTE 'CREATE POLICY lossfit_app_knowledge_vectors ON public.knowledge_vector_embeddings '
                    'TO lossfit_app USING (true) WITH CHECK (true)';
          END IF;
        END $$
    """)

    # Preserve vectors already ingested before this migration. JSON vectors are
    # still retained for portable fallback and dimension/model provenance.
    bind.exec_driver_sql(
        "INSERT INTO public.knowledge_vector_embeddings (chunk_id, model, dimensions, embedding) "
        "SELECT id, embedding_model, json_array_length(embedding), "
        f"embedding::text::{vector_schema}.vector "
        "FROM public.knowledge_chunks "
        "WHERE embedding IS NOT NULL AND embedding_model IS NOT NULL "
        "AND json_typeof(embedding) = 'array' "
        "AND json_array_length(embedding) BETWEEN 1 AND 8192 "
        "ON CONFLICT (chunk_id) DO NOTHING"
    )


def downgrade():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        bind.exec_driver_sql("DROP TABLE IF EXISTS public.knowledge_vector_embeddings")
