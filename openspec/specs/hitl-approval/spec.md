# hitl-approval Specification

## Purpose
Provides human-in-the-loop (HITL) approval workflows and interrupt controls for sensitive incident triage escalation tools.

## Requirements

### Requirement: Human-in-the-Loop Interrupt for Escalation Tools

The system SHALL pause execution prior to running sensitive tools and require human authorization before proceeding. If a model message contains multiple tool calls, the system SHALL route the entire message to the sensitive-tools approval interrupt when ANY tool call is sensitive.

#### Scenario: Sensitive tool call triggers human approval interrupt
- **GIVEN** an active triage agent graph processing an incident query requiring escalation
- **WHEN** the agent proposes calling escalate_ticket
- **THEN** the state machine interrupts execution before sensitive_tools node
- **AND** persists the graph state with pending interrupt in checkpointer state

#### Scenario: Approved escalation tool execution resumes graph
- **GIVEN** a paused triage agent state waiting for escalate_ticket approval
- **WHEN** an engineer submits an approval signal
- **THEN** execution resumes and invokes escalate_ticket
- **AND** returns confirmation of ticket creation and on-call paging

#### Scenario: Rejected escalation tool cancels sensitive action
- **GIVEN** a paused triage agent state waiting for escalate_ticket approval
- **WHEN** an engineer submits a rejection signal
- **THEN** the escalate_ticket tool call is skipped or cancelled without execution
- **AND** the agent updates thread state recording the human rejection decision

#### Scenario: Mixed safe and sensitive calls
- **GIVEN** the model returns both query_service_health and escalate_ticket in one message
- **WHEN** the agent processes the message
- **THEN** execution pauses before the sensitive_tools node
- **AND** the pending sensitive action includes escalate_ticket

#### Scenario: Rejection answers every pending call
- **GIVEN** a paused model message containing multiple tool calls including a sensitive tool
- **WHEN** an engineer rejects the escalation
- **THEN** every pending tool call receives a rejection ToolMessage
- **AND** no sensitive tool executes

### Requirement: Restart-Resilient Approval State Persistence
The system SHALL persist paused interrupt states in Postgres checkpointer so approval or rejection can be processed across service restarts or after long delays.

#### Scenario: Paused escalation state survives restart
- **GIVEN** an incident thread paused on sensitive tool interrupt
- **WHEN** the agent application process restarts
- **THEN** loading the thread state from checkpointer retrieves the pending interrupt
- **AND** allows approval or rejection to proceed seamlessly
