# Tasks

## 1. Human-in-the-Loop Escalation Tool & Graph Interrupts

- [x] 1.1 Implement `escalate_ticket` tool in `agent.py` to handle incident ticket creation and on-call paging details.
- [x] 1.2 Update graph topology in `agent.py` to separate `safe_tools` and `sensitive_tools`, and configure `interrupt_before=["sensitive_tools"]` during compilation in `get_agent_app()`.
- [x] 1.3 Add approval and rejection resume execution helpers in `agent.py` to handle human authorization decisions.

## 2. HITL Approval & Rejection Test Coverage

- [x] 2.1 Add unit tests in `tests/test_agent.py` verifying that invoking `escalate_ticket` triggers a graph interrupt before the `sensitive_tools` node.
- [x] 2.2 Add integration tests in `tests/test_agent.py` validating approval resume execution and rejection decision handling, and verify all tests pass via `$env:PYTHONPATH="."; .venv\Scripts\pytest.exe tests/`.
