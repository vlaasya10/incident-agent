import os
import json

import gradio as gr
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from langchain_core.messages import HumanMessage

from agent import (
    get_agent_app,
    approve_escalation,
    reject_escalation,
)


# ---------------------------------------------------------
# Service layer
# ---------------------------------------------------------

class IncidentService:
    def __init__(self, agent=None):
        self.agent = agent or get_agent_app()

    def _config(self, thread_id: str):
        return {"configurable": {"thread_id": thread_id}}

    def _extract_text(self, message):
        content = getattr(message, "content", "")

        if isinstance(content, str):
            return content

        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and "text" in item:
                    parts.append(item["text"])
                else:
                    parts.append(str(item))
            return "\n".join(parts)

        return str(content)

    def _pending_action(self, state):
        messages = state.values.get("messages", [])

        if not messages:
            return None

        last_message = messages[-1]

        for tool_call in getattr(last_message, "tool_calls", []):
            if tool_call.get("name") == "escalate_ticket":
                return {
                    "name": "escalate_ticket",
                    "parameters": tool_call.get("args", {}),
                }

        return None

    def chat(self, thread_id: str, message: str):
        config = self._config(thread_id)

        result = self.agent.invoke(
            {"messages": [HumanMessage(content=message)]},
            config=config,
        )

        state = self.agent.get_state(config)

        if "sensitive_tools" in state.next:
            return {
                "status": "AWAITING_APPROVAL",
                "pending_action": self._pending_action(state),
                "message": self._extract_text(result["messages"][-1]),
            }

        return {
            "status": "COMPLETED",
            "message": self._extract_text(result["messages"][-1]),
        }

    def approve(self, thread_id: str):
        config = self._config(thread_id)
        state = self.agent.get_state(config)

        if "sensitive_tools" not in state.next:
            raise ValueError("Nothing is pending for this thread")

        result = approve_escalation(self.agent, config)

        return {
            "status": "RESOLVED",
            "message": self._extract_text(result["messages"][-1]),
        }

    def reject(self, thread_id: str, reason: str):
        config = self._config(thread_id)
        state = self.agent.get_state(config)

        if "sensitive_tools" not in state.next:
            raise ValueError("Nothing is pending for this thread")

        result = reject_escalation(
            self.agent,
            config,
            reason or "Escalation rejected by engineer.",
        )

        return {
            "status": "REJECTED_AND_RESUMED",
            "message": self._extract_text(result["messages"][-1]),
        }


# ---------------------------------------------------------
# FastAPI
# ---------------------------------------------------------

app = FastAPI(
    title="Autonomous Incident Triage Agent",
    version="1.0.0",
)

service = IncidentService()


class ChatRequest(BaseModel):
    thread_id: str
    message: str


class ApproveRequest(BaseModel):
    thread_id: str
    approved: bool
    rejection_reason: str | None = None


@app.post("/chat")
def chat(request: ChatRequest):
    try:
        return service.chat(
            request.thread_id,
            request.message,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/approve")
def approve(request: ApproveRequest):
    try:
        if request.approved:
            return service.approve(request.thread_id)

        return service.reject(
            request.thread_id,
            request.rejection_reason or "",
        )

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------
# Gradio UI
# ---------------------------------------------------------

def trigger_triage(thread_id, incident_description):
    if not thread_id.strip():
        return "ERROR: Thread ID is required.", ""

    if not incident_description.strip():
        return "ERROR: Incident description is required.", ""

    try:
        result = service.chat(
            thread_id,
            incident_description,
        )

        state = result["status"]
        log = json.dumps(result, indent=2)

        return state, log

    except Exception as exc:
        return "ERROR", str(exc)


def approve_action(thread_id):
    if not thread_id.strip():
        return "ERROR: Thread ID is required.", ""

    try:
        result = service.approve(thread_id)
        return result["status"], json.dumps(result, indent=2)

    except Exception as exc:
        return "ERROR", str(exc)


def reject_action(thread_id, reason):
    if not thread_id.strip():
        return "ERROR: Thread ID is required.", ""

    try:
        result = service.reject(thread_id, reason)
        return result["status"], json.dumps(result, indent=2)

    except Exception as exc:
        return "ERROR", str(exc)


with gr.Blocks(title="Incident Triage Agent") as demo:
    gr.Markdown("# 🚨 Autonomous Incident Triage Agent")

    thread_id = gr.Textbox(
        label="Thread ID",
        value="incident-1",
    )

    incident = gr.Textbox(
        label="Incident Description",
        placeholder="Auth service is timing out...",
        lines=4,
    )

    with gr.Row():
        trigger = gr.Button("Trigger Triage")
        approve = gr.Button("Approve Escalation")
        reject = gr.Button("Reject Action")

    rejection_reason = gr.Textbox(
        label="Rejection Reason",
        placeholder="Explain why the escalation should not proceed.",
    )

    workflow_state = gr.Label(
        label="Workflow State",
        value="READY",
    )

    agent_log = gr.Markdown(
        label="Agent Log",
    )

    trigger.click(
        trigger_triage,
        inputs=[thread_id, incident],
        outputs=[workflow_state, agent_log],
    )

    approve.click(
        approve_action,
        inputs=[thread_id],
        outputs=[workflow_state, agent_log],
    )

    reject.click(
        reject_action,
        inputs=[thread_id, rejection_reason],
        outputs=[workflow_state, agent_log],
    )

@app.get("/healthz")
def healthz():
    return {"status": "ok"}


app = gr.mount_gradio_app(
    app,
    demo,
    path="/",
)


# ---------------------------------------------------------
# Local run
# ---------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "7860"))

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
    )