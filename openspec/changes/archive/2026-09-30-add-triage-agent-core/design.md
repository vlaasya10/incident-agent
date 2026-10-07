# Design

## Context

See [proposal.md](file:///c:/Users/divya/incident-agent/openspec/changes/add-triage-agent-core/proposal.md) for motivation and problem statement.

The triage agent is built using standard Python 3.11 with `langgraph`, `langchain-google-genai`, `psycopg_pool`, and `langgraph-checkpoint-postgres`. Connecting to Supabase Postgres over transaction pooler (port 6543) requires disabling server-side prepared statements (`prepare_threshold=None`).

## Goals / Non-Goals

**Goals:**
- Construct a safe, read-only LangGraph state machine with system prompt enforcing service health checks prior to runbook searches.
- Configure `psycopg_pool.ConnectionPool` with `max_size=10`, `autocommit=True`, `connect_timeout=15`, `prepare_threshold=None`.
- Define `query_service_health` and `search_remediation_runbooks` read-only tools.
- Implement robust text normalization helper `extract_text` for handling list or dictionary structured LLM message outputs.
- Set up `PostgresSaver` checkpointer and export `get_agent_app()` to compile the runnable graph.
- Provide comprehensive test coverage in `tests/test_agent.py` using mocked LLM models and mocked Postgres pools.

**Non-Goals:**
- Implementation of destructive actions or `escalate_ticket` tool (deferred to subsequent HITL change).
- Web application route registration or Gradio UI embedding (handled in API/UI changes).

## Decisions

### Decision 1: `psycopg_pool.ConnectionPool` with `prepare_threshold=None`
- **Rationale**: Supabase transaction pooler (PgBouncer port 6543) does not support prepared statements across pooled connections. Setting `prepare_threshold=None` disables prepared statements, preventing SQL execution errors during checkpointing.
- **Alternatives Considered**: Using standard `psycopg.connect` per invocation (high overhead, risk of connection exhaustion under concurrent requests) or direct connection port 5432 (bypasses pooler and risks hitting Supabase free-tier connection caps).

### Decision 2: Read-Only Tool Execution with LangGraph `ToolNode`
- **Rationale**: Wrapping `query_service_health` and `search_remediation_runbooks` into a `ToolNode("safe_tools")` decouples tool logic from state transition logic and enables native LangGraph conditional routing via tool call presence.
- **Alternatives Considered**: Direct Python tool execution inside the LLM model node (reduces graph clarity and breaks standard LangGraph tool call history conventions).

### Decision 3: Text Normalization Helper `extract_text`
- **Rationale**: Gemini and LangChain models sometimes return content as strings, lists of content dicts, or nested structures. `extract_text` normalizes all content formats into a single, clean string for downstream processing.
- **Alternatives Considered**: Assuming string content directly (susceptible to runtime type errors when LLM returns block-structured content).

### Decision 4: Gemini Embedding Task Type `RETRIEVAL_QUERY`
- **Rationale**: Matching runbooks during triage requires query-side embeddings (`task_type="retrieval_query"`) to align with the document embeddings indexed with `retrieval_document` during seeding.
- **Alternatives Considered**: Using default or document task type for search queries (yields lower retrieval accuracy).

## Risks / Trade-offs

- **[Risk]** Supabase free-tier connection limits under load. → **Mitigation**: Limit pool size to `max_size=10` and use short connection timeout (`connect_timeout=15`).
- **[Risk]** Gemini API free-tier rate limits. → **Mitigation**: Restrict runbook search results to top 2 (`top_k=2`) and fully mock LLM invocations in unit tests.

## Migration Plan

1. Create `agent.py` with `psycopg_pool`, `PostgresSaver`, safe tools, graph topology, and `get_agent_app()`.
2. `PostgresSaver.setup()` will automatically create checkpointer tables on initial execution.
3. Add `tests/test_agent.py` to validate graph routing and state persistence.
4. **Rollback Strategy**: Revert code files (`agent.py`, `tests/test_agent.py`). Checkpointer tables can be dropped if state reset is required.
