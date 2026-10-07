# Proposal

## Why

The incident triage system requires an intelligent agent capable of automatically diagnosing reported service issues by inspecting service health status and searching relevant remediation runbooks. Building the core LangGraph state machine with safe, read-only tools and persistence via PostgreSQL checkpointing establishes the foundational triage loop before introducing destructive or high-impact actions.

## What Changes

- Implement core `agent.py` using LangGraph to handle safe diagnostic workflows.
- Create PostgreSQL connection pooling using `psycopg_pool.ConnectionPool` with transaction pooler settings (`max_size=10`, `autocommit=True`, `connect_timeout=15`, `prepare_threshold=None`).
- Define safe read-only tools:
  - `query_service_health`: Queries service health from a mocked service table.
  - `search_remediation_runbooks`: Performs pgvector cosine similarity search over `incident_docs` using Gemini embeddings (`task_type="retrieval_query"`, top 2 results).
- Implement `AgentState` schema using `add_messages` annotation.
- Implement system prompt guiding the model to check service health first before searching remediation runbooks.
- Create `extract_text` helper function to normalize list-structured or complex LLM message content into a standard string representation.
- Construct LangGraph workflow: `agent` node -> `safe_tools` node -> conditional check (loop to `safe_tools` or route to `END` when no tool calls are present).
- Integrate `PostgresSaver` checkpointer with `setup()` initialization for thread state persistence.
- Provide `get_agent_app()` function returning compiled LangGraph runnable.
- Exclude `escalate_ticket` tool or destructive actions at this stage.
- Add unit and integration tests in `tests/test_agent.py` mocking the LLM response to verify tool execution, graph routing, and thread-based state persistence.

## Capabilities

### New Capabilities
- `triage-agent`: Core safe incident triage workflow using LangGraph state machine, Postgres checkpointer, and read-only diagnostic tools.

### Modified Capabilities

## Impact

- **Affected Code**: `agent.py`, `tests/test_agent.py`.
- **Dependencies**: `langgraph`, `langgraph-checkpoint-postgres`, `psycopg_pool`, `langchain-google-genai`.
- **Database**: Uses Supabase Postgres via connection pooler and creates checkpointer tables via `PostgresSaver.setup()`.
- **Rollback Note**: Revert `agent.py` and `tests/test_agent.py`. Checkpoint tables in Postgres (`checkpoints`, `checkpoint_blobs`, `checkpoint_writes`) can be dropped if clean environment reset is required.
