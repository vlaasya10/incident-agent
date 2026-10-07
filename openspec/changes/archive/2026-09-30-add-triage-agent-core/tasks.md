# Tasks

## 1. Core Agent Module Implementation

- [x] 1.1 Implement database connection pooler and text extractor helper in `agent.py` using `psycopg_pool.ConnectionPool` (`max_size=10`, `autocommit=True`, `connect_timeout=15`, `prepare_threshold=None`) and test text normalization for list/dict content types.
- [x] 1.2 Define safe read-only tools `query_service_health` and `search_remediation_runbooks` in `agent.py` using Gemini embeddings (`task_type="retrieval_query"`, top 2 results).
- [x] 1.3 Construct system prompt, `AgentState` with `add_messages`, and state machine graph topology (`agent` -> `safe_tools` loop -> `END`) with `PostgresSaver` checkpointer setup and `get_agent_app()` builder in `agent.py`.

## 2. Unit and Integration Tests

- [x] 2.1 Implement `tests/test_agent.py` to test text extraction helper and safe tool mock invocations.
- [x] 2.2 Implement mock LLM state routing and `PostgresSaver` thread state persistence tests in `tests/test_agent.py` and verify test suite passes via `pytest tests/test_agent.py`.
