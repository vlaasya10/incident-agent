# Proposal

## Why

High-severity incident triage often requires opening tickets and paging on-call engineers (`escalate_ticket`). To prevent runaway automation or unwarranted emergency alerts, any ticket escalation action must be paused and require human approval before execution, maintaining state persistence across system restarts.

## What Changes

- Introduce `escalate_ticket` tool in `agent.py` to handle ticket creation and on-call notifications.
- Separate tools into `safe_tools` (`query_service_health`, `search_remediation_runbooks`) and `sensitive_tools` (`escalate_ticket`).
- Implement human-in-the-loop (HITL) interrupt mechanism in LangGraph using `interrupt_before=["sensitive_tools"]`.
- Update state graph topology: `agent` -> conditional check (`safe_tools`, `sensitive_tools`, or `END`) -> loop back to `agent`.
- Provide approval resume execution logic allowing human engineers to approve or reject pending escalations.
- If approved, `escalate_ticket` executes and returns confirmation; if rejected, the tool call is cancelled and a rejection note is recorded.
- Update tests in `tests/test_agent.py` to mock both approval and rejection workflows and verify checkpointer state persistence across pauses.

## Capabilities

### New Capabilities
- `hitl-approval`: Human-in-the-loop approval workflow for ticket escalations using LangGraph interrupts and state persistence.

### Modified Capabilities

## Impact

- **Affected Code**: `agent.py`, `tests/test_agent.py`.
- **Dependencies**: `langgraph`, `langgraph-checkpoint-postgres`, `psycopg_pool`.
- **Rollback Note**: Revert `agent.py` and `tests/test_agent.py`. Active checkpoint states with pending interrupts can be cleared or resumed.
