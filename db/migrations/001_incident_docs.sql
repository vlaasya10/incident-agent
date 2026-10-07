-- Enable the pgvector extension to work with embedding vectors
CREATE EXTENSION IF NOT EXISTS vector;

-- Create table to store incident runbook documents and their 768-dim embeddings
CREATE TABLE IF NOT EXISTS incident_docs (
    id BIGSERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    embedding VECTOR(768) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create HNSW index for fast cosine similarity vector search
CREATE INDEX IF NOT EXISTS incident_docs_embedding_hnsw_idx 
ON incident_docs USING hnsw (embedding vector_cosine_ops);

-- Stored procedure (RPC function) for similarity search matching
CREATE OR REPLACE FUNCTION match_incident_docs (
    query_embedding VECTOR(768),
    match_threshold FLOAT DEFAULT 0.0,
    match_count INT DEFAULT 5,
    filter JSONB DEFAULT '{}'::jsonb
)
RETURNS TABLE (
    id BIGINT,
    content TEXT,
    metadata JSONB,
    similarity FLOAT
)
LANGUAGE sql STABLE
AS $$
    SELECT
        incident_docs.id,
        incident_docs.content,
        incident_docs.metadata,
        1 - (incident_docs.embedding <=> query_embedding) AS similarity
    FROM incident_docs
    WHERE 
        (1 - (incident_docs.embedding <=> query_embedding)) >= match_threshold
        AND (filter = '{}'::jsonb OR incident_docs.metadata @> filter)
    ORDER BY incident_docs.embedding <=> query_embedding ASC
    LIMIT match_count;
$$;
