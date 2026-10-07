# Design

## Context

See [proposal.md](file:///c:/Users/divya/incident-agent/openspec/changes/add-hitl-escalation/proposal.md) for motivation.

The core triage agent (`agent.py`) executes safe read-only diagnostic tools. Escalation actions (`escalate_ticket`) are sensitive and require human authorization before execution. LangGraph provides `interrupt_before` configuration during graph compilation (`workflow.compile(checkpointer=checkpointer, interrupt_before=["sensitive_tools"])`) to halt state machine execution prior to executing specified nodes.

## Goals / Non-Goals

**Goals:**
- Implement `escalate_ticket` tool in `agent.py`.
- Split graph nodes into `safe_tools` (auto-executed) and `sensitive_tools` (`escalate_ticket`, requiring human approval).
- Configure graph compilation with `interrupt_before=["sensitive_tools"]`.
- Provide resume functions for approving (`app.invoke(None, config)`) or rejecting (`app.update_state(config, ...)` / passing rejection feedback).
- Ensure interrupt state persistence across process restarts using `PostgresSaver`.
- Update `tests/test_agent.py` to test approval, rejection, and state recovery.

**Non-Goals:**
- Web UI or FastAPI REST API route endpoints for HITL interaction (handled in subsequent triage-api and triage-ui changes).

## Decisions

### Decision 1: Node Separation (`safe_tools` vs `sensitive_tools`) with `interrupt_before`
- **Rationale**: Separating `escalate_ticket` into `sensitive_tools` node allows `workflow.compile(checkpointer=checkpointer, interrupt_before=["sensitive_tools"])` to pause graph execution cleanly whenever `escalate_ticket` is called, while allowing `safe_tools` to run automatically.
- **Alternatives Considered**: In-line tool level `interrupt()` calls inside tool functions (adds complexity and couples tool definitions to LangGraph runtime state).

### Decision 2: Rejection Handling via State Update or Tool Message Injection
- **Rationale**: When an engineer rejects an escalation, updating thread state with a `ToolMessage` or system cancellation response ensures the model understands the escalation was declined by the operator and can continue diagnosis.
- **Alternatives Considered**: Raising an exception or terminating thread state immediately (prevents model from acknowledging rejection and continuing chat).

## Risks / Trade-offs

- **[Risk]** Paused threads remaining in checkpointer state indefinitely if ignored by engineers. → **Mitigation**: `PostgresSaver` retains thread state reliably; state can be inspected or garbage collected via thread cleanup utilities if needed.

## Migration Plan

1. Update `agent.py` with `escalate_ticket`, separate tool nodes (`safe_tools` and `sensitive_tools`), and `interrupt_before=["sensitive_tools"]`.
2. Add approval/rejection handler functions in `agent.py`.
3. Add unit/integration tests in `tests/test_agent.py`.
4. **Rollback Strategy**: Revert `agent.py` and `tests/test_agent.py` to restore pure safe-path execution.
