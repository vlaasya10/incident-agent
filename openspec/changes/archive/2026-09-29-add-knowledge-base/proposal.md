# Proposal: Add Runbook Knowledge Base

## Why

The autonomous incident triage agent needs domain-specific knowledge to suggest accurate remediation steps when services fail. Building a pgvector-backed runbook vector store populated with Gemini embeddings provides the agent with semantic search capabilities over runbooks for auth, database, and payment services.

## What Changes

- Add database migration `db/migrations/001_incident_docs.sql` to enable `pgvector`, create the `incident_docs` table (with 768-dimensional vector embedding column), and define a `match_incident_docs` cosine similarity RPC function.
- Create `requirements.txt` declaring all project dependencies (Gradio, FastAPI, Uvicorn, LangGraph, LangGraph Postgres checkpointer, LangChain Google GenAI, Psycopg pool, Pydantic, Pytest).
- Create `seed_rag.py` to embed 3 sample runbooks (auth timeouts, database latency, payment gateway failures) using Gemini `text-embedding-004` (768 dimensions) and insert them idempotently into Supabase Postgres.
- Add unit tests (`tests/test_seed_rag.py`) mocking Gemini embeddings and Supabase database connection pool.

## Capabilities

### New Capabilities
- `knowledge-base`: Provides vector storage, Gemini embedding generation, idempotent runbook seeding, and cosine similarity runbook retrieval.

### Modified Capabilities
- None.

## Impact

- **Database**: Requires running `db/migrations/001_incident_docs.sql` in Supabase Postgres.
- **Dependencies**: Adds `requirements.txt` with python dependencies.
- **Environment**: Requires `GEMINI_API_KEY` and `DATABASE_URL` environment variables.

## Rollback Note

To roll back this change:
1. Delete `seed_rag.py`, `requirements.txt`, `db/migrations/001_incident_docs.sql`, and `tests/test_seed_rag.py`.
2. In Supabase SQL Editor, drop the table and RPC function: `DROP FUNCTION IF EXISTS match_incident_docs; DROP TABLE IF EXISTS incident_docs;`.
