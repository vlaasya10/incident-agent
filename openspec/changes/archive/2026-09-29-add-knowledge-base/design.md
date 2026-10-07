# Design: Runbook Knowledge Base

## Context

See `proposal.md` for motivation and background.

This design specifies the schema, embedding configuration, dependency declaration, and seeding implementation for the vector-based runbook knowledge base using Supabase Postgres (pgvector) and Gemini Embeddings.

## Goals / Non-Goals

**Goals:**
- Provide a SQL migration creating `incident_docs` with 768-dim `vector` column and a cosine similarity RPC search function `match_incident_docs`.
- Define all project dependencies in `requirements.txt`.
- Implement `seed_rag.py` to embed 3 sample runbooks (auth 504, database latency, payment gateway failure) using Gemini `text-embedding-004` (768 dimensions) idempotently.
- Implement comprehensive unit tests (`tests/test_seed_rag.py`) with mocked embeddings and mocked DB pool.

**Non-Goals:**
- Defining the LangGraph agent state machine (deferred to `02-triage-agent`).
- Creating FastAPI REST endpoints or Gradio UI (deferred to `04-triage-api-ui`).

## Decisions

### Decision 1: 768-Dimensional Gemini Embeddings
- **Rationale**: Gemini AI Studio `text-embedding-004` with `output_dimensionality=768` fits within free-tier limits without requiring a credit card, while providing strong semantic retrieval performance.
- **Alternatives Considered**: OpenAI `text-embedding-3-small` (requires paid API key), 1536-dim embeddings (higher memory overhead on Supabase pgvector free tier).

### Decision 2: Supabase Transaction Pooler (Port 6543) Compatibility
- **Rationale**: Supabase free tier enforces connection limits. Connecting via the transaction pooler on port 6543 allows multiple operations without exhausting pool limits. To avoid PgBouncer errors, `psycopg` connection settings must set `prepare_threshold=None` to disable prepared statements.
- **Alternatives Considered**: Direct connection / Session Pooler on port 5432 (exceeds connection quota quickly under concurrent traffic).

### Decision 3: Idempotent Seeding Strategy
- **Rationale**: `seed_rag.py` checks for existing runbooks by service key (`metadata->>'service'`) or upserts using `ON CONFLICT` / `DELETE ... WHERE metadata->>'service' = ...` before insertion. This allows developers to run `python seed_rag.py` repeatedly without duplicating entries.
- **Alternatives Considered**: Naive `INSERT` (creates duplicate runbooks on re-execution).

## Risks / Trade-offs

- **[Risk] Supabase PgBouncer Prepared Statement Error** → **Mitigation**: Configure `psycopg` with `prepare_threshold=None` in database helper functions.
- **[Risk] Gemini AI Studio Free-Tier Rate Limits (15 RPM)** → **Mitigation**: Batch runbook embedding calls during seeding; mock embeddings completely in `pytest` suite.
- **[Risk] Render Cold Starts / Inactive DB Pausing** → **Mitigation**: Keep table schema lean and vector dimensions at 768 to maintain fast cold query performance.

## Migration Plan

1. Developer executes `db/migrations/001_incident_docs.sql` in the Supabase SQL Editor.
2. Developer installs dependencies: `pip install -r requirements.txt`.
3. Developer configures `.env` with `GEMINI_API_KEY` and `DATABASE_URL`.
4. Developer runs `python seed_rag.py` to seed sample runbooks.
