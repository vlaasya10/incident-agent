# Triage UI Specification

## Purpose
Define the Gradio interface used by engineers to submit incidents and review human-in-the-loop escalation actions.

## Requirements

### Requirement: Incident submission interface
The UI SHALL provide controls for entering a thread ID and incident description and triggering triage.

#### Scenario: Submit incident from UI
- GIVEN an engineer enters a thread ID and incident description
- WHEN the engineer triggers triage
- THEN the UI displays the workflow state and agent output.

### Requirement: Human approval controls
The UI SHALL provide Approve and Reject controls for pending escalation actions.

#### Scenario: Review pending escalation
- GIVEN a triage workflow is awaiting approval
- WHEN the engineer selects Approve or Reject
- THEN the UI sends the corresponding action and displays the resulting workflow state.
