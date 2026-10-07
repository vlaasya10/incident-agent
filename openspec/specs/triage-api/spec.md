# Triage API Specification

## Purpose
Define the REST API used to submit incidents and approve or reject pending escalation actions.

## Requirements

### Requirement: Incident triage endpoint
The API SHALL provide a POST `/chat` endpoint that accepts a thread ID and incident message and returns the current workflow status.

#### Scenario: Submit incident
- GIVEN a valid thread ID and incident description
- WHEN the client sends POST `/chat`
- THEN the API returns the workflow result and current state.

### Requirement: Human approval endpoint
The API SHALL provide a POST `/approve` endpoint for approving or rejecting a pending escalation.

#### Scenario: Approve or reject pending escalation
- GIVEN a thread with a pending escalation
- WHEN the client sends an approval or rejection
- THEN the API resumes the workflow and returns the resulting state.
- AND when no approval is pending, the API returns HTTP 400.
