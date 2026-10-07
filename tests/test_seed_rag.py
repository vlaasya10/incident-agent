import pytest
from unittest.mock import MagicMock, patch, call
from seed_rag import seed_runbooks, SAMPLE_RUNBOOKS, get_embeddings_client

def test_sample_runbooks_count_and_structure():
    assert len(SAMPLE_RUNBOOKS) == 3
    services = [rb["service"] for rb in SAMPLE_RUNBOOKS]
    assert "auth" in services
    assert "database" in services
    assert "payments" in services

def test_seed_runbooks_missing_db_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValueError, match="DATABASE_URL environment variable is missing"):
        seed_runbooks(db_url=None)

def test_get_embeddings_client_missing_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="GEMINI_API_KEY environment variable is missing"):
        get_embeddings_client()

@patch("seed_rag.psycopg.connect")
def test_seed_runbooks_execution_and_idempotency(mock_connect):
    # Mock Gemini Embeddings Client
    mock_embeddings_client = MagicMock()
    # Return 768-dimensional dummy embeddings for each of the 3 sample runbooks
    dummy_embeddings = [[0.1] * 768 for _ in range(len(SAMPLE_RUNBOOKS))]
    mock_embeddings_client.embed_documents.return_value = dummy_embeddings

    # Mock psycopg Connection and Cursor
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_connect.return_value.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    test_db_url = "postgresql://user:pass@localhost:6543/postgres"
    seed_runbooks(db_url=test_db_url, embeddings_client=mock_embeddings_client)

    # 1. Verify embeddings client was called with runbook texts
    mock_embeddings_client.embed_documents.assert_called_once()
    texts_passed = mock_embeddings_client.embed_documents.call_args[0][0]
    assert len(texts_passed) == 3

    # 2. Verify psycopg connect was called with prepare_threshold=None for PgBouncer pooler compatibility
    mock_connect.assert_called_once_with(test_db_url, prepare_threshold=None)

    # 3. Verify DELETE (for idempotency) and INSERT were called 3 times
    assert mock_cursor.execute.call_count == 6  # 3 DELETEs + 3 INSERTs
    assert mock_conn.commit.call_count == 1
