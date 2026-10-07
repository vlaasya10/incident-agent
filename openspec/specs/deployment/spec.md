# Deployment Specification

## Purpose
Define the configuration and runtime requirements for deploying the incident triage agent on Render.

## Requirements

### Requirement: Render deployment configuration
The service SHALL be deployable as a free Render web service using the repository deployment configuration.

#### Scenario: Deploy service
- GIVEN the repository contains the Render deployment configuration
- WHEN Render deploys the service
- THEN the Python application starts using the configured web service command.

### Requirement: Environment-based secrets
The deployment SHALL obtain `GEMINI_API_KEY` and `DATABASE_URL` from environment variables and SHALL NOT require secrets in tracked files.

#### Scenario: Configure secrets
- GIVEN the required environment variables are configured in Render
- WHEN the service starts
- THEN the application can initialize without committed credentials.

### Requirement: Health check
The deployment SHALL expose `/healthz` for service health verification.

#### Scenario: Healthy service
- GIVEN the deployed application is running
- WHEN a client requests `/healthz`
- THEN the service returns HTTP 200 with a healthy status.

### Requirement: Persistent paused approvals
The deployment SHALL preserve paused approval state using the configured Postgres-backed checkpointer.

#### Scenario: Resume after restart
- GIVEN a thread is awaiting human approval
- WHEN the service restarts
- THEN the pending thread state remains available for approval and resumption.
