# knowledge-base Specification

## Purpose
Provides vector storage, Gemini embedding generation, idempotent runbook seeding, and cosine similarity runbook retrieval for incident triage.

## Requirements

### Requirement: Database Migration for Runbook Store
The system SHALL provide a SQL migration script `db/migrations/001_incident_docs.sql` that enables the `pgvector` extension, creates an `incident_docs` table with a 768-dimensional vector column and JSONB metadata, and creates a `match_incident_docs` stored procedure (RPC) for cosine similarity vector search.

#### Scenario: Migration creates required table and function
- **GIVEN** a Supabase Postgres database with pgvector extension enabled
- **WHEN** `db/migrations/001_incident_docs.sql` is executed
- **THEN** the `incident_docs` table exists with `id`, `content`, `metadata`, `embedding` (vector(768)), and `created_at` columns
- **AND** the `match_incident_docs` RPC function exists taking query embedding vector, match threshold float, match count int, and metadata filter jsonb

### Requirement: Idempotent Runbook Seeding
The system SHALL provide a seeding script `seed_rag.py` that computes 768-dimensional Gemini embeddings (`task_type="retrieval_document"`) for three sample runbooks (auth 504 timeouts, database high latency, and payment gateway failures) and inserts them idempotently into Supabase Postgres via the connection pooler.

#### Scenario: Initial seeding populates runbooks
- **GIVEN** an empty `incident_docs` table
- **WHEN** `seed_rag.py` is executed with valid database credentials and Gemini API key
- **THEN** exactly three runbook documents are embedded and stored in `incident_docs`

#### Scenario: Repeated seeding is idempotent
- **GIVEN** an `incident_docs` table already populated with the three sample runbooks
- **WHEN** `seed_rag.py` is executed again
- **THEN** no duplicate runbooks are inserted into `incident_docs` and total count remains three

### Requirement: Test Suite Mocking
The test suite for `knowledge-base` SHALL verify seeding and retrieval logic with unit tests using mocks for both the Gemini API client and the Supabase Postgres connection.

#### Scenario: Seeding unit tests execute without external network calls
- **GIVEN** unit test mocks for `langchain_google_genai.GoogleGenerativeAIEmbeddings` and `psycopg_pool.ConnectionPool`
- **WHEN** `pytest tests/test_seed_rag.py` is executed
- **THEN** all tests pass cleanly without invoking live Gemini API endpoints or connecting to a live Supabase database
