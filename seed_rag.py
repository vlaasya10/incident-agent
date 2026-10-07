import os
import json
from dotenv import load_dotenv
import psycopg
from psycopg.types.json import Jsonb
from langchain_google_genai import GoogleGenerativeAIEmbeddings

load_dotenv()

SAMPLE_RUNBOOKS = [
    {
        "service": "auth",
        "title": "Auth Service 504 Timeouts & JWT Verification Failures",
        "content": (
            "Runbook: Auth Service 504 Gateway Timeouts\n\n"
            "Symptoms:\n"
            "- Clients receive 504 Gateway Timeout on /auth/login and /auth/verify.\n"
            "- Latency spikes in auth microservice.\n\n"
            "Diagnostic Steps:\n"
            "1. Check Redis cache connection for token revocation lists.\n"
            "2. Inspect DB connection pool metrics for auth DB.\n"
            "3. Verify upstream OAuth provider latency.\n\n"
            "Remediation Steps:\n"
            "1. If Redis is down/throttled, flush stale cache keys or restart Redis node.\n"
            "2. Scale auth service deployment replicas from 2 to 5.\n"
            "3. If auth DB pool is exhausted, clear idle connections or increase max_connections.\n"
            "4. If unresolvable, escalate to Security & Auth On-Call Team."
        ),
    },
    {
        "service": "database",
        "title": "Database High Latency & Connection Pool Exhaustion",
        "content": (
            "Runbook: Postgres Database Latency & Connection Failures\n\n"
            "Symptoms:\n"
            "- API requests failing with '500 Internal Server Error' due to DB connection timeout.\n"
            "- High CPU usage (>90%) on Primary Postgres instance.\n\n"
            "Diagnostic Steps:\n"
            "1. Run `pg_stat_activity` to find long-running queries (>10s).\n"
            "2. Check PgBouncer pooler status and active client connections.\n"
            "3. Inspect table bloat and missing indexes on high-traffic tables.\n\n"
            "Remediation Steps:\n"
            "1. Terminate long-running blocking queries using `SELECT pg_cancel_backend(pid)`.\n"
            "2. Restart PgBouncer service or increase max pool size.\n"
            "3. Enable read-replica routing for heavy GET/analytics queries.\n"
            "4. If Primary DB disk IOPS are saturated, escalate to Database Reliability Engineering (DBRE)."
        ),
    },
    {
        "service": "payments",
        "title": "Payment Gateway Timeout & Transaction Rejection",
        "content": (
            "Runbook: Payment Gateway Integration Failures\n\n"
            "Symptoms:\n"
            "- Checkout API returning 502/504 errors on Stripe/PayPal webhook endpoints.\n"
            "- High rate of rejected card authorizations.\n\n"
            "Diagnostic Steps:\n"
            "1. Check status page of third-party payment provider (Stripe/PayPal/Adyen).\n"
            "2. Inspect outbound gateway HTTP response times and SSL certificate validity.\n"
            "3. Check dead-letter queue (DLQ) for failed payment webhook notifications.\n\n"
            "Remediation Steps:\n"
            "1. If primary payment gateway is experiencing an outage, toggle feature flag to switch to secondary payment provider.\n"
            "2. Re-queue failed webhook messages from DLQ after provider recovers.\n"
            "3. If API keys or webhooks are misconfigured, re-sync credentials in secret manager.\n"
            "4. Escalate to Payments On-Call if error rate exceeds 5% for >5 minutes."
        ),
    },
]

def get_embeddings_client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is missing")
    return GoogleGenerativeAIEmbeddings(
        model="models/gemini-embedding-001",
        task_type="retrieval_document",
        output_dimensionality=768,
        google_api_key=api_key,
    )

def seed_runbooks(db_url: str = None, embeddings_client=None):
    if db_url is None:
        db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL environment variable is missing")

    if embeddings_client is None:
        embeddings_client = get_embeddings_client()

    print("Generating embeddings for sample runbooks...")
    texts = [rb["content"] for rb in SAMPLE_RUNBOOKS]
    embeddings = embeddings_client.embed_documents(texts)

    print("Connecting to database...")
    # prepare_threshold=None ensures compatibility with PgBouncer transaction mode (port 6543)
    with psycopg.connect(db_url, prepare_threshold=None) as conn:
        with conn.cursor() as cur:
            for rb, emb in zip(SAMPLE_RUNBOOKS, embeddings):
                service = rb["service"]
                metadata = {"service": service, "title": rb["title"]}
                
                # Idempotent operation: remove existing entries for this service before inserting
                cur.execute(
                    "DELETE FROM incident_docs WHERE metadata->>'service' = %s",
                    (service,)
                )
                
                # Insert the new document with its 768-dim vector embedding
                cur.execute(
                    """
                    INSERT INTO incident_docs (content, metadata, embedding)
                    VALUES (%s, %s, %s::vector)
                    """,
                    (rb["content"], Jsonb(metadata), str(emb))
                )
            conn.commit()
    print("Runbook seeding completed successfully.")

if __name__ == "__main__":
    seed_runbooks()
