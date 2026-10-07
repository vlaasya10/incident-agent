# Spec Delta

## Purpose

Provides autonomous incident triage using LangGraph state machine, Postgres checkpointer state persistence, safe read-only diagnostic tools, and message content normalization.

## ADDED Requirements

### Requirement: LangGraph Core Safe Workflow Execution
The system SHALL provide a LangGraph agent workflow (`agent.py`) configured with safe read-only tools and system prompt ordering to inspect service health first before searching remediation runbooks.

#### Scenario: Agent executes safe diagnostic tools and terminates when finished
- **GIVEN** an initialized triage agent graph and an incoming incident query
- **WHEN** the agent processes the user message
- **THEN** it executes `query_service_health` first, followed by `search_remediation_runbooks` if needed
- **AND** loops between agent and safe_tools until no further tool calls are emitted
- **AND** returns the final text response normalized via `extract_text` helper

#### Scenario: Safe tool search_remediation_runbooks executes vector query
- **GIVEN** a query string for incident symptoms
- **WHEN** `search_remediation_runbooks` is invoked
- **THEN** it generates a 768-dimensional query embedding with `task_type="retrieval_query"`
- **AND** queries the `incident_docs` table via pgvector match RPC returning the top 2 matching runbooks

### Requirement: Postgres Connection Pooling and Checkpoint Persistence
The system SHALL maintain thread state using `PostgresSaver` checkpointer connected via a `psycopg_pool.ConnectionPool` with transaction pooler compatible settings (`max_size=10`, `autocommit=True`, `connect_timeout=15`, `prepare_threshold=None`).

#### Scenario: Checkpointer setup and graph compiled app
- **GIVEN** a valid database URL
- **WHEN** `get_agent_app()` is called
- **THEN** the PostgreSQL connection pool is initialized with `prepare_threshold=None` and `max_size=10`
- **AND** `PostgresSaver` schema setup is executed
- **AND** a compiled LangGraph application with the checkpointer is returned

### Requirement: Test Suite Mocking for Triage Agent
The system test suite SHALL verify the triage agent routing, tool call handling, text extraction, and thread state persistence using mock LLM models and mock PostgreSQL connection pools without requiring live network or external API access.

#### Scenario: Agent routing test executes with mock LLM tool calls
- **GIVEN** a mock LLM model configured to emit `query_service_health` tool call followed by a final text answer
- **WHEN** running `pytest tests/test_agent.py`
- **THEN** the test verifies that the graph routes to safe_tools, executes the tool, returns to agent, updates state by thread_id, and completes cleanly
