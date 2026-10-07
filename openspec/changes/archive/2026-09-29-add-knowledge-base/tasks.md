# Tasks

## 1. Project Dependencies & Database Migration

- [x] 1.1 Create `requirements.txt` with required project dependencies (gradio, fastapi, uvicorn, langgraph, langgraph-checkpoint-postgres, langchain-google-genai, langchain-core, psycopg[binary,pool], python-dotenv, pydantic, pytest) and verify package installation syntax.
- [x] 1.2 Create `db/migrations/001_incident_docs.sql` containing pgvector extension enablement, `incident_docs` table definition (id, content, metadata JSONB, vector(768) embedding, created_at), and the `match_incident_docs` RPC function for cosine similarity search.

## 2. RAG Seeding Script Implementation

- [x] 2.1 Implement `seed_rag.py` to embed 3 sample runbooks (auth 504 timeouts, database high latency, payment gateway failures) using Gemini embeddings (`task_type="retrieval_document"`, 768 dimensions) and insert them into Supabase Postgres via the connection pooler.
- [x] 2.2 Ensure seeding idempotency in `seed_rag.py` (e.g. checking existing entries before inserting or using upsert/delete-before-insert per service key) so running the script multiple times does not produce duplicate records.

## 3. Unit Testing & Verification

- [x] 3.1 Create `tests/test_seed_rag.py` with pytest unit tests that mock both the Gemini AI embeddings client and the Postgres database connection pool, verifying embedding generation and idempotent db insertion logic without live network calls.
- [x] 3.2 Run `pytest tests/test_seed_rag.py` using PowerShell and verify all unit tests pass with clean test results.
