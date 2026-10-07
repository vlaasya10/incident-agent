from unittest.mock import MagicMock, patch
import json
import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver

from agent import (
    extract_text,
    query_service_health,
    search_remediation_runbooks,
    escalate_ticket,
    get_db_pool,
    get_agent_app,
    build_graph,
    approve_escalation,
    reject_escalation,
    should_continue,
    AgentState,
    MOCK_SERVICE_HEALTH,
)

def test_extract_text_normalization():
    assert extract_text("hello") == "hello"
    assert extract_text(["foo", "bar"]) == "foobar"
    assert extract_text([{"type": "text", "text": "hello "}, {"type": "text", "text": "world"}]) == "hello world"
    assert extract_text({"text": "single dict"}) == "single dict"
    assert extract_text(None) == ""

def test_query_service_health_known():
    res = query_service_health.invoke({"service_name": "auth"})
    data = json.loads(res)
    assert data["service"] == "auth"
    assert data["health"]["status"] == "degraded"

def test_query_service_health_unknown():
    res = query_service_health.invoke({"service_name": "nonexistent"})
    data = json.loads(res)
    assert data["status"] == "unknown"

def test_escalate_ticket_tool():
    res = escalate_ticket.invoke({"service_name": "database", "priority": "P1", "summary": "DB CPU > 95%"})
    data = json.loads(res)
    assert data["status"] == "escalated"
    assert data["service"] == "database"
    assert data["priority"] == "P1"
    assert data["on_call_paged"] is True

@patch("agent.GoogleGenerativeAIEmbeddings")
@patch("agent.psycopg.connect")
def test_search_remediation_runbooks(mock_connect, mock_embeddings_cls, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake_key")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")

    mock_embeddings = MagicMock()
    mock_embeddings.embed_query.return_value = [0.1] * 768
    mock_embeddings_cls.return_value = mock_embeddings

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_connect.return_value.__enter__.return_value = mock_conn

    mock_cursor.fetchall.return_value = [
        (1, "Runbook content", {"title": "Auth 504"}, 0.95)
    ]

    res = search_remediation_runbooks.invoke({"query": "auth timeout"})
    data = json.loads(res)
    assert len(data) == 1
    assert data[0]["content"] == "Runbook content"
    assert data[0]["similarity"] == 0.95

def test_get_db_pool_configuration(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:6543/db")
    with patch("agent.ConnectionPool") as mock_pool_cls:
        get_db_pool()
        mock_pool_cls.assert_called_once_with(
            conninfo="postgresql://user:pass@localhost:6543/db",
            max_size=10,
            kwargs={
                "autocommit": True,
                "connect_timeout": 15,
                "prepare_threshold": None,
            },
        )

def test_agent_graph_routing_safe_tools():
    mock_llm = MagicMock()
    mock_model_with_tools = MagicMock()
    mock_llm.bind_tools.return_value = mock_model_with_tools

    tool_call_msg = AIMessage(
        content="",
        tool_calls=[{
            "name": "query_service_health",
            "args": {"service_name": "auth"},
            "id": "call_123"
        }]
    )
    final_msg = AIMessage(content="Auth service is degraded with 504 timeouts.")

    mock_model_with_tools.invoke.side_effect = [tool_call_msg, final_msg]

    checkpointer = MemorySaver()
    app = get_agent_app(checkpointer=checkpointer, llm=mock_llm)

    config = {"configurable": {"thread_id": "thread-safe"}}
    input_state = {"messages": [HumanMessage(content="Check auth service health")]}

    result = app.invoke(input_state, config=config)

    messages = result["messages"]
    assert len(messages) >= 4
    assert any(isinstance(m, AIMessage) and m.content == "Auth service is degraded with 504 timeouts." for m in messages)

def test_hitl_escalation_interrupt_and_approval():
    mock_llm = MagicMock()
    mock_model_with_tools = MagicMock()
    mock_llm.bind_tools.return_value = mock_model_with_tools

    esc_call = AIMessage(
        content="",
        tool_calls=[{
            "name": "escalate_ticket",
            "args": {"service_name": "database", "priority": "P1", "summary": "DB Connection exhaustion"},
            "id": "call_esc_1"
        }]
    )
    final_post_approval = AIMessage(content="Ticket INC-1234 opened and on-call team paged.")

    mock_model_with_tools.invoke.side_effect = [esc_call, final_post_approval]

    checkpointer = MemorySaver()
    app = get_agent_app(checkpointer=checkpointer, llm=mock_llm)

    config = {"configurable": {"thread_id": "thread-hitl-approve"}}
    app.invoke({"messages": [HumanMessage(content="Escalate database issue")]}, config=config)

    # Verify state is paused before sensitive_tools
    state = app.get_state(config)
    assert state.next == ("sensitive_tools",)

    # Approve escalation
    res = approve_escalation(app, config)
    messages = res["messages"]
    assert any(isinstance(m, AIMessage) and "Ticket INC-1234" in m.content for m in messages)

def test_hitl_escalation_rejection():
    mock_llm = MagicMock()
    mock_model_with_tools = MagicMock()
    mock_llm.bind_tools.return_value = mock_model_with_tools

    esc_call = AIMessage(
        content="",
        tool_calls=[{
            "name": "escalate_ticket",
            "args": {"service_name": "payments", "priority": "P2", "summary": "Gateway timeouts"},
            "id": "call_esc_2"
        }]
    )
    final_post_rejection = AIMessage(content="Escalation request was rejected by operator. Continuing monitoring.")

    mock_model_with_tools.invoke.side_effect = [esc_call, final_post_rejection]

    checkpointer = MemorySaver()
    app = get_agent_app(checkpointer=checkpointer, llm=mock_llm)

    config = {"configurable": {"thread_id": "thread-hitl-reject"}}
    app.invoke({"messages": [HumanMessage(content="Escalate payment gateway errors")]}, config=config)

    # Verify state is paused before sensitive_tools
    state = app.get_state(config)
    assert state.next == ("sensitive_tools",)

    # Reject escalation
    res = reject_escalation(app, config, reason="Issue being handled manually.")
    messages = res["messages"]
    assert any("rejected" in str(m.content) for m in messages)

def test_mixed_safe_and_sensitive_tools_require_hitl():
    message = AIMessage(
        content="",
        tool_calls=[
            {
                "name": "query_service_health",
                "args": {"service_name": "database"},
                "id": "call_safe_1",
            },
            {
                "name": "escalate_ticket",
                "args": {
                    "service_name": "database",
                    "priority": "P1",
                    "summary": "Critical database issue",
                },
                "id": "call_sensitive_1",
            },
        ],
    )

    state = {"messages": [message]}

    assert should_continue(state) == "sensitive_tools"