# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Ambient expense agent — ADK 2.0 graph-based workflow.

Graph summary
─────────────
START ──► parse_expense ──► route_by_amount ──┬── AUTO_APPROVE ──► auto_approve
                                               │
                                               └── NEEDS_REVIEW ──► review_agent
                                                                        │
                                                                   request_approval  (HITL / RequestInput)
                                                                        │
                                                                   process_decision

Rules
─────
• Amount < $100  → auto_approve node logs and returns immediately.
• Amount ≥ $100  → review_agent (LLM) analyses the expense, then
                   request_approval pauses the workflow for a human
                   manager, and process_decision logs the outcome.
"""

import json
import os

import google.auth
from google.adk.agents import LlmAgent
from google.adk.agents.context import Context
from google.adk.apps import App
from google.adk.events.event import Event
from google.adk.events.request_input import RequestInput
from google.adk.workflow import Workflow
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Authentication — use Vertex AI via Application Default Credentials
# ---------------------------------------------------------------------------

_, _project_id = google.auth.default()
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", _project_id or "")
os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "global")
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "True")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MODEL = "gemini-2.5-flash"
REVIEW_THRESHOLD = 100.0  # USD — expenses at or above this require human review

# ---------------------------------------------------------------------------
# Pydantic schemas for structured data flow between nodes
# ---------------------------------------------------------------------------


class ExpenseData(BaseModel):
    """Structured expense report submitted by an employee."""

    amount: float = Field(description="Expense amount in USD")
    submitter: str = Field(description="Email of the person who submitted")
    category: str = Field(description="Expense category, e.g. travel, meals")
    description: str = Field(description="What the expense is for")
    date: str = Field(description="Date of the expense (YYYY-MM-DD)")


class ReviewResult(BaseModel):
    """Output schema for the review_agent LLM node."""

    risk_level: str = Field(description="low, medium, or high")
    risk_factors: str = Field(description="Comma-separated list of flags found")
    recommendation: str = Field(
        description="approve, request-more-info, or escalate"
    )
    summary: str = Field(description="Short human-readable review summary")


# ---------------------------------------------------------------------------
# Helper: structured log to stdout (Cloud Run captures as JSON logs)
# ---------------------------------------------------------------------------


def _log(severity: str, message: str, **extra: object) -> None:
    print(json.dumps({"severity": severity, "message": message, **extra}), flush=True)


# ---------------------------------------------------------------------------
# Node 1 — parse_expense
#
# Accepts free-text or JSON describing the expense.  Returns an Event whose
# output is a plain dict matching ExpenseData fields so the router can read it.
# ---------------------------------------------------------------------------


def parse_expense(node_input: str) -> Event:
    """Parse raw user input into an ExpenseData-compatible dict.

    For the local prototype the input is plain text such as:
        "Process this expense: $250 flight to NYC for client meeting"

    For a Pub/Sub-driven deployment the input would be a JSON envelope —
    this function handles both so the prototype is drop-in compatible.
    """
    try:
        payload = json.loads(node_input)
        data = payload.get("data", payload)  # unwrap Pub/Sub envelope if present
        return Event(
            output={
                "amount": float(data.get("amount", 0)),
                "submitter": data.get("submitter", "unknown@example.com"),
                "category": data.get("category", "other"),
                "description": data.get("description", ""),
                "date": data.get("date", ""),
            }
        )
    except (json.JSONDecodeError, ValueError):
        # Treat the raw string as the description and ask the LLM downstream
        # to interpret it; inject a sentinel so routing still works.
        return Event(
            output={
                "amount": -1.0,  # sentinel → will be parsed by review_agent
                "submitter": "unknown@example.com",
                "category": "other",
                "description": str(node_input),
                "date": "",
                "_raw": True,
            }
        )


# ---------------------------------------------------------------------------
# Node 2 — route_by_amount
#
# Inspects the amount and returns a routing Event so the workflow picks the
# correct branch.  Also persists the expense dict in ctx.state so HITL nodes
# can retrieve it without relying on node_input propagation through the LLM.
# ---------------------------------------------------------------------------


def route_by_amount(node_input: dict, ctx: Context) -> Event:
    """Route to AUTO_APPROVE or NEEDS_REVIEW based on the $100 threshold."""
    ctx.state["expense_data"] = node_input
    amount = float(node_input.get("amount", 0))
    if amount >= REVIEW_THRESHOLD:
        return Event(route="NEEDS_REVIEW", output=node_input)
    return Event(route="AUTO_APPROVE", output=node_input)


# ---------------------------------------------------------------------------
# Node 3a — auto_approve
#
# For expenses under $100: log the approval and return a final status dict.
# ---------------------------------------------------------------------------


def auto_approve(node_input: dict) -> Event:
    """Instantly approve low-value expenses and log the decision."""
    _log(
        "INFO",
        f"Expense auto-approved: ${node_input.get('amount', 0):.2f}"
        f" from {node_input.get('submitter', 'unknown')}",
        decision="approved",
        amount=node_input.get("amount"),
        submitter=node_input.get("submitter"),
        category=node_input.get("category"),
    )
    result = {"status": "approved", **node_input}
    # Emit a content event so the ADK web UI shows the outcome
    from google.genai import types

    summary = (
        f"✅ Auto-approved: ${node_input.get('amount', 0):.2f} expense"
        f" from {node_input.get('submitter', 'unknown')}."
        f" Category: {node_input.get('category', 'other')}."
    )
    return Event(
        output=result,
        content=types.Content(
            role="model", parts=[types.Part.from_text(text=summary)]
        ),
    )


# ---------------------------------------------------------------------------
# Tool used by review_agent to emit a structured alert log
# ---------------------------------------------------------------------------


def emit_expense_alert(
    submitter: str,
    amount: float,
    category: str,
    risk_summary: str,
) -> dict:
    """Emit a structured WARNING log alerting finance to review a high-value expense.

    Args:
        submitter: Who submitted the expense.
        amount: The expense amount in USD.
        category: The expense category.
        risk_summary: Why this expense needs review.

    Returns:
        Confirmation that the alert was emitted.
    """
    _log(
        "WARNING",
        f"Expense review alert: ${amount:.2f} from {submitter} — {risk_summary}",
        alert_type="expense_review",
        submitter=submitter,
        amount=amount,
        category=category,
        risk_summary=risk_summary,
    )
    return {"status": "alert_emitted", "submitter": submitter, "amount": amount}


# ---------------------------------------------------------------------------
# Node 3b — review_agent (LLM, only reached for expenses ≥ $100)
#
# Analyses the expense, emits a structured alert log, and returns a
# ReviewResult so the downstream HITL node can surface it to the manager.
# ---------------------------------------------------------------------------

review_agent = LlmAgent(
    name="review_agent",
    model=MODEL,
    mode="single_turn",
    instruction="""You are an expense review agent. You receive expense reports
of $100 or more that need review before a manager approves them.

Analyse the expense and:
1. Identify risk factors: unusual category for the amount, vague description,
   suspiciously round numbers, very high value (>$1000), or potential policy
   violations.
2. Call the `emit_expense_alert` tool with submitter, amount, category, and a
   brief risk_summary explaining why this expense needs human review.
3. Return a structured ReviewResult.

Your output MUST conform to the ReviewResult schema:
- risk_level: "low", "medium", or "high"
- risk_factors: comma-separated flags found (or "none")
- recommendation: "approve", "request-more-info", or "escalate"
- summary: one sentence for the manager approval UI""",
    input_schema=ExpenseData,
    output_schema=ReviewResult,
    output_key="review_result",
    tools=[emit_expense_alert],
)

# ---------------------------------------------------------------------------
# Node 4 — request_approval  (HITL pause)
#
# Yields a RequestInput to pause the session and surface an approval prompt
# to the manager.  When the manager responds, their reply becomes node_input
# for process_decision (rerun_on_resume=False is the FunctionNode default).
# ---------------------------------------------------------------------------


def request_approval(node_input: object, ctx: Context):  # type: ignore[no-untyped-def]
    """Pause the workflow and request manager approval via HITL."""
    expense = ctx.state.get("expense_data", {})
    review = ctx.state.get("review_result", {})
    yield RequestInput(
        interrupt_id="manager_approval",
        message=(
            "An expense requires your approval.\n\n"
            f"• Submitter: {expense.get('submitter', 'unknown')}\n"
            f"• Amount: ${expense.get('amount', 0):.2f}\n"
            f"• Category: {expense.get('category', 'other')}\n"
            f"• Description: {expense.get('description', '')}\n"
            f"• Date: {expense.get('date', '')}\n\n"
            f"AI Review — Risk level: {review.get('risk_level', 'unknown')}\n"
            f"Recommendation: {review.get('recommendation', 'unknown')}\n"
            f"Summary: {review.get('summary', '')}\n\n"
            "Reply 'approve' to approve or 'reject' to reject."
        ),
        payload={"expense": expense, "review": review},
    )


# ---------------------------------------------------------------------------
# Node 5 — process_decision
#
# Reads the manager's response and logs the final outcome.
# ---------------------------------------------------------------------------


def process_decision(node_input: object, ctx: Context) -> Event:  # type: ignore[no-untyped-def]
    """Process the manager's approval or rejection and log the outcome."""
    decision = "unknown"
    if isinstance(node_input, dict):
        decision = node_input.get("decision", node_input.get("response", "unknown"))
    elif isinstance(node_input, str):
        decision = "approve" if "approve" in node_input.lower() else "reject"

    approved = decision.lower() in ("approve", "approved", "yes")
    status = "approved" if approved else "rejected"
    expense = ctx.state.get("expense_data", {})

    _log(
        "INFO" if approved else "WARNING",
        f"Expense {status} by manager",
        decision=status,
        submitter=expense.get("submitter"),
        amount=expense.get("amount"),
    )

    amount = expense.get("amount", 0)
    submitter = expense.get("submitter", "unknown")
    description = expense.get("description", "")
    category = expense.get("category", "")
    date = expense.get("date", "")

    icon = "✅" if approved else "❌"
    parts = [f"{icon} ${amount:.2f} expense from {submitter} has been {status}."]
    if description:
        parts.append(f'"{description}" ({category}) on {date}.')
    if approved:
        parts.append("It will be processed for reimbursement.")
    else:
        parts.append(
            "The submitter will be notified and may resubmit with additional documentation."
        )

    message = " ".join(parts)

    from google.genai import types

    return Event(
        output={"status": status, "message": message, **expense},
        content=types.Content(
            role="model", parts=[types.Part.from_text(text=message)]
        ),
    )


# ---------------------------------------------------------------------------
# Root agent — ADK 2.0 graph-based Workflow
#
# Edge layout:
#   START ──► (parse_expense, route_by_amount)   sequential shorthand
#   route_by_amount ──(AUTO_APPROVE)──► auto_approve
#   route_by_amount ──(NEEDS_REVIEW)──► review_agent
#   review_agent ──► (request_approval, process_decision)  sequential shorthand
# ---------------------------------------------------------------------------

root_agent = Workflow(
    name="expense_processor",
    description=(
        "Ambient expense agent — auto-approves expenses under $100 and "
        "triggers a human-in-the-loop review for expenses of $100 or more."
    ),
    edges=[
        # Step 1 & 2: parse then route (sequential shorthand)
        ("START", parse_expense, route_by_amount),
        # Step 3: conditional branch via dict-target routing
        (
            route_by_amount,
            {
                "AUTO_APPROVE": auto_approve,
                "NEEDS_REVIEW": review_agent,
            },
        ),
        # Step 4–5: high-value path — HITL pause then decision
        (review_agent, request_approval, process_decision),
    ],
)

# ---------------------------------------------------------------------------
# ADK App (required by agents-cli run / playground)
# ---------------------------------------------------------------------------

app = App(
    root_agent=root_agent,
    name="app",
)
