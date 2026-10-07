import os
import json
from typing import Any, List, Dict, Sequence, Union, Annotated, Optional
from typing_extensions import TypedDict

from dotenv import load_dotenv
import psycopg
from psycopg_pool import ConnectionPool

from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.postgres import PostgresSaver

load_dotenv()

MOCK_SERVICE_HEALTH = {
    "auth": {
        "status": "degraded",
        "latency_ms": 1450,
        "error_rate": "12%",
        "active_incidents": ["AUTH-504-TIMEOUT"],
    },
    "database": {
        "status": "unhealthy",
        "cpu_utilization": "94%",
        "active_connections": 98,
        "max_connections": 100,
    },
    "payments": {
        "status": "degraded",
        "gateway_response": "504 Gateway Timeout",
        "dlq_count": 42,
    },
    "frontend": {
        "status": "healthy",
        "latency_ms": 45,
        "error_rate": "0.1%",
    },
}

def get_db_pool(db_url: Optional[str] = None) -> ConnectionPool:
    """Create and return a psycopg_pool ConnectionPool configured for Supabase PgBouncer pooler."""
    if db_url is None:
        db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL environment variable is missing")
    return ConnectionPool(
        conninfo=db_url,
        max_size=10,
        kwargs={
            "autocommit": True,
            "connect_timeout": 15,
            "prepare_threshold": None,
        },
    )

def extract_text(content: Any) -> str:
    """Normalizes string, list, or dictionary structured model content to a clean string."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                if "text" in item and isinstance(item["text"], str):
                    parts.append(item["text"])
                elif "content" in item and isinstance(item["content"], str):
                    parts.append(item["content"])
                else:
                    parts.append(str(item))
            else:
                parts.append(str(item))
        return "".join(parts)
    if isinstance(content, dict):
        if "text" in content and isinstance(content["text"], str):
            return content["text"]
        elif "content" in content and isinstance(content["content"], str):
            return content["content"]
        return str(content)
    return str(content)

@tool
def query_service_health(service_name: str) -> str:
    """Query the health status, metrics, and active issues for a given microservice."""
    name_clean = service_name.lower().strip()
    if name_clean in MOCK_SERVICE_HEALTH:
        return json.dumps({"service": name_clean, "health": MOCK_SERVICE_HEALTH[name_clean]})
    return json.dumps({"service": name_clean, "status": "unknown", "message": f"Service '{service_name}' not found in health registry."})

@tool
def search_remediation_runbooks(query: str) -> str:
    """Search remediation runbooks in pgvector database for relevant incident troubleshooting steps."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "Error: GEMINI_API_KEY environment variable is missing"
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        return "Error: DATABASE_URL environment variable is missing"

    embeddings_client = GoogleGenerativeAIEmbeddings(
        model="models/gemini-embedding-001",
        task_type="retrieval_query",
        output_dimensionality=768,
        google_api_key=api_key,
    )
    query_vector = embeddings_client.embed_query(query)

    with psycopg.connect(db_url, prepare_threshold=None) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, content, metadata, 1 - (embedding <=> %s::vector) AS similarity
                FROM incident_docs
                ORDER BY embedding <=> %s::vector ASC
                LIMIT 2
                """,
                (str(query_vector), str(query_vector)),
            )
            rows = cur.fetchall()
            if not rows:
                return "No matching remediation runbooks found."
            results = []
            for row in rows:
                results.append({
                    "id": row[0],
                    "content": row[1],
                    "metadata": row[2],
                    "similarity": float(row[3]) if row[3] is not None else 0.0,
                })
            return json.dumps(results)

@tool
def escalate_ticket(service_name: str, priority: str, summary: str) -> str:
    """Escalate an incident by creating a high-priority incident ticket and paging the on-call engineering team."""
    ticket_id = f"INC-{abs(hash(service_name + summary)) % 10000:04d}"
    return json.dumps({
        "status": "escalated",
        "ticket_id": ticket_id,
        "service": service_name,
        "priority": priority,
        "summary": summary,
        "on_call_paged": True,
        "message": f"Incident ticket {ticket_id} created for '{service_name}' ({priority}). On-call team paged successfully."
    })

SAFE_TOOLS = [query_service_health, search_remediation_runbooks]
SENSITIVE_TOOLS = [escalate_ticket]
ALL_TOOLS = SAFE_TOOLS + SENSITIVE_TOOLS

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]

SYSTEM_PROMPT = (
    "You are an autonomous Incident Triage Agent.\n"
    "Your goal is to investigate, diagnose, and triage service incidents.\n"
    "Workflow Instructions:\n"
    "1. Inspect service health first using the `query_service_health` tool.\n"
    "2. If service health is degraded/unhealthy or error symptoms exist, search remediation runbooks using `search_remediation_runbooks`.\n"
    "3. Synthesize diagnostic observations and provide actionable remediation guidance based on runbook content.\n"
    "4. If an incident requires manual intervention or remains severely degraded, use `escalate_ticket` to open an incident ticket and page the on-call team."
)

def should_continue(state: AgentState) -> str:
    messages = state["messages"]
    last_message = messages[-1]

    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        sensitive_tool_names = {
            tool.name for tool in SENSITIVE_TOOLS
        }

        if any(
            tc.get("name") in sensitive_tool_names
            for tc in last_message.tool_calls
        ):
            return "sensitive_tools"

        return "safe_tools"

    return END

def build_graph(llm=None):
    if llm is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is missing")
        llm = ChatGoogleGenerativeAI(
            model="gemini-3.8-flash",
            google_api_key=api_key,
            temperature=0,
        )

    model_with_tools = llm.bind_tools(ALL_TOOLS)

    def call_agent(state: AgentState):
        messages = list(state["messages"])
        if not any(isinstance(m, SystemMessage) for m in messages):
            messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages
        response = model_with_tools.invoke(messages)
        return {"messages": [response]}

    safe_tool_node = ToolNode(SAFE_TOOLS)
    sensitive_tool_node = ToolNode(SENSITIVE_TOOLS)

    workflow = StateGraph(AgentState)
    workflow.add_node("agent", call_agent)
    workflow.add_node("safe_tools", safe_tool_node)
    workflow.add_node("sensitive_tools", sensitive_tool_node)

    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "safe_tools": "safe_tools",
            "sensitive_tools": "sensitive_tools",
            END: END,
        }
    )
    workflow.add_edge("safe_tools", "agent")
    workflow.add_edge("sensitive_tools", "agent")

    return workflow

def get_agent_app(db_url: Optional[str] = None, pool: Optional[ConnectionPool] = None, checkpointer = None, llm = None):
    """Compiles the LangGraph workflow with PostgresSaver checkpointer persistence and HITL interrupts."""
    workflow = build_graph(llm=llm)

    if checkpointer is None:
        if pool is None:
            pool = get_db_pool(db_url=db_url)
        checkpointer = PostgresSaver(conn=pool)
        checkpointer.setup()

    app = workflow.compile(
        checkpointer=checkpointer,
        interrupt_before=["sensitive_tools"]
    )
    return app

def approve_escalation(app, config: dict) -> dict:
    """Approves a pending escalation interrupt by resuming graph execution through sensitive_tools."""
    return app.invoke(None, config=config)

def reject_escalation(app, config: dict, reason: str = "Escalation rejected by engineer.") -> dict:
    """Rejects a pending escalation interrupt by injecting a ToolMessage cancellation and resuming the agent."""
    current_state = app.get_state(config)
    messages = current_state.values.get("messages", [])
    if not messages:
        raise ValueError("No state found for specified thread_id")

    last_msg = messages[-1]
    if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
        for tc in last_msg.tool_calls:
            if tc.get("name") == "escalate_ticket":
                tool_call_id = tc.get("id")
                rejection_msg = ToolMessage(
                    content=json.dumps({
                        "status": "rejected",
                        "reason": reason,
                        "message": f"Escalation rejected by operator. Reason: {reason}"
                    }),
                    tool_call_id=tool_call_id,
                )
                app.update_state(config, {"messages": [rejection_msg]}, as_node="sensitive_tools")
                return app.invoke(None, config=config)
    raise ValueError("No pending escalation tool call found in thread state")
