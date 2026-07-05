# expense-tracker

Capstone code lab for Kaggle / Google's **5-Day Gen AI Intensive**. It's an
ambient expense-approval agent built on Google ADK 2.0, paired with a small
dashboard for the human-in-the-loop (HITL) step.

## What it does

An employee submits an expense (amount, submitter, category, description,
date). The agent graph decides what happens next:

- **Under $100** → auto-approved instantly, no LLM call.
- **$100 or more** → an LLM review node (`gemini-2.5-flash`) flags risk
  factors (vague description, suspiciously round number, high value, etc.),
  then the workflow pauses and waits for a manager to approve or reject it
  through the dashboard.

```
START ─► parse_expense ─► route_by_amount ─┬─ (<$100) ──────────► auto_approve
                                            └─ (≥$100) ─► review_agent ─► request_approval (HITL) ─► process_decision
```

## Structure

```
expense-agent/         ADK agent: graph workflow, review LLM node, deployment (Cloud Run + Terraform)
submission_frontend/   FastAPI dashboard: lists pending expenses, sends approve/reject back to the agent
```

See [expense-agent/README.md](expense-agent/README.md) for the agent's own
setup/deploy instructions (`agents-cli`, `uv`, Terraform).

## Running the frontend

```bash
cd submission_frontend
uv sync
export GOOGLE_CLOUD_PROJECT=<your-project-id>
export AGENT_RUNTIME_ID=<deployed reasoning engine id>
uv run uvicorn main:app --reload
```

It polls the agent's session service for expenses paused on `manager_approval`
and posts the manager's decision back via the Agent Runtime `streamQuery` API.

## Context

Built as a lab exercise, not production software — the $100 threshold, the
dashboard's dark-glass UI, and the auto-approve path are all deliberately
simple to keep the ADK concepts (graph workflows, structured I/O, HITL
interrupts) front and center.
