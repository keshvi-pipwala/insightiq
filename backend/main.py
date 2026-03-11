"""
InsightIQ Backend - FastAPI + RAG Pipeline
LLM-Powered Product Analytics Assistant
v2: Streaming responses + Auto-dashboard endpoint
"""

import os
import re
import io
import json
import sqlite3
import logging
from datetime import datetime
from typing import Optional, AsyncGenerator
from contextlib import asynccontextmanager

import pandas as pd
import numpy as np
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import anthropic
import chromadb
from sentence_transformers import SentenceTransformer

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── Config ───────────────────────────────────────────────────────────────────
# DATA_DIR can be overridden by env var — useful for Railway persistent volumes
_DATA_DIR = os.environ.get("DATA_DIR", "/app/data")
DB_PATH = os.path.join(_DATA_DIR, "insightiq.db")
CHROMA_PATH = os.path.join(_DATA_DIR, "chroma")
EMBED_MODEL = "all-MiniLM-L6-v2"
CLAUDE_MODEL = "claude-sonnet-4-20250514"
TOP_K_CHUNKS = 8

# Dashboard: 5 pre-built insight questions run automatically on upload
DASHBOARD_QUESTIONS = [
    {
        "id": "churn_by_plan",
        "question": "What is the churn rate for each subscription plan? Show me a comparison.",
        "title": "Churn Rate by Plan"
    },
    {
        "id": "clv_by_category",
        "question": "What is the average customer lifetime value broken down by product category?",
        "title": "Avg CLV by Category"
    },
    {
        "id": "spend_by_plan",
        "question": "Show me the average monthly spend for each subscription plan.",
        "title": "Monthly Spend by Plan"
    },
    {
        "id": "users_by_country",
        "question": "What is the distribution of users across different countries? Show as a pie chart.",
        "title": "Users by Country"
    },
    {
        "id": "nps_by_plan",
        "question": "How does average NPS score compare across different subscription plans?",
        "title": "NPS Score by Plan"
    },
]

# ── Lifespan ─────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(_DATA_DIR, exist_ok=True)
    init_db()
    logger.info(f"InsightIQ backend v2 started — data dir: {_DATA_DIR}")
    yield

app = FastAPI(title="InsightIQ API", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Singletons ────────────────────────────────────────────────────────────────
embed_model: Optional[SentenceTransformer] = None
chroma_client = None
chroma_collection = None
anthropic_client: Optional[anthropic.Anthropic] = None

def get_embed_model():
    global embed_model
    if embed_model is None:
        logger.info("Loading sentence-transformer model...")
        embed_model = SentenceTransformer(EMBED_MODEL)
    return embed_model

def get_chroma():
    global chroma_client, chroma_collection
    if chroma_client is None:
        os.makedirs(CHROMA_PATH, exist_ok=True)
        chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
        chroma_collection = chroma_client.get_or_create_collection(
            name="insightiq_chunks",
            metadata={"hnsw:space": "cosine"}
        )
    return chroma_collection

def get_anthropic():
    global anthropic_client
    if anthropic_client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        anthropic_client = anthropic.Anthropic(api_key=api_key)
    return anthropic_client

# ── Database ──────────────────────────────────────────────────────────────────
def init_db():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.executescript("""
        CREATE TABLE IF NOT EXISTS uploaded_datasets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            row_count INTEGER,
            columns TEXT,
            uploaded_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS query_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dataset_id INTEGER,
            question TEXT NOT NULL,
            answer TEXT,
            chart_data TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (dataset_id) REFERENCES uploaded_datasets(id)
        );
        CREATE TABLE IF NOT EXISTS chart_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query_hash TEXT UNIQUE,
            chart_data TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS dashboard_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dataset_id INTEGER UNIQUE,
            panels TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (dataset_id) REFERENCES uploaded_datasets(id)
        );
    """)
    con.commit()
    con.close()

def get_db():
    return sqlite3.connect(DB_PATH)

# ── Data chunking ─────────────────────────────────────────────────────────────
def chunk_dataframe(df: pd.DataFrame, dataset_id: int) -> list[dict]:
    chunks = []

    for idx, row in df.iterrows():
        text = f"User {row.get('user_id', idx)}: "
        text += f"Age {row.get('age', 'N/A')}, {row.get('gender', 'N/A')}, from {row.get('country', 'N/A')}. "
        text += f"Plan: {row.get('subscription_plan', 'N/A')}, "
        text += f"Monthly spend: ${row.get('monthly_spend', 0):.2f}, "
        text += f"Total orders: {row.get('total_orders', 0)}, "
        text += f"Category: {row.get('product_category', 'N/A')}, "
        text += f"CLV: ${row.get('customer_lifetime_value', 0):.2f}, "
        text += f"NPS: {row.get('NPS_score', 'N/A')}, "
        text += f"Churned: {'Yes' if row.get('churn_label', 0) == 1 else 'No'}. "
        text += f"Signed up: {row.get('signup_date', 'N/A')}, Last active: {row.get('last_active_date', 'N/A')}."
        chunks.append({
            "id": f"row_{dataset_id}_{idx}",
            "text": text,
            "metadata": {"dataset_id": dataset_id, "type": "row", "row_index": idx}
        })

    if "subscription_plan" in df.columns:
        plan_stats = df.groupby("subscription_plan").agg(
            count=("user_id", "count"),
            avg_spend=("monthly_spend", "mean"),
            avg_clv=("customer_lifetime_value", "mean"),
            churn_rate=("churn_label", "mean"),
            avg_orders=("total_orders", "mean")
        ).reset_index()
        for _, row in plan_stats.iterrows():
            text = (f"Subscription plan '{row['subscription_plan']}' summary: "
                    f"{row['count']} users, avg monthly spend ${row['avg_spend']:.2f}, "
                    f"avg CLV ${row['avg_clv']:.2f}, churn rate {row['churn_rate']*100:.1f}%, "
                    f"avg orders {row['avg_orders']:.1f}.")
            chunks.append({
                "id": f"plan_{dataset_id}_{row['subscription_plan']}",
                "text": text,
                "metadata": {"dataset_id": dataset_id, "type": "aggregate_plan"}
            })

    if "country" in df.columns:
        country_stats = df.groupby("country").agg(
            count=("user_id", "count"),
            avg_clv=("customer_lifetime_value", "mean"),
            churn_rate=("churn_label", "mean"),
            avg_spend=("monthly_spend", "mean")
        ).reset_index()
        for _, row in country_stats.iterrows():
            text = (f"Country '{row['country']}' summary: "
                    f"{row['count']} users, avg CLV ${row['avg_clv']:.2f}, "
                    f"churn rate {row['churn_rate']*100:.1f}%, avg spend ${row['avg_spend']:.2f}.")
            chunks.append({
                "id": f"country_{dataset_id}_{row['country']}",
                "text": text,
                "metadata": {"dataset_id": dataset_id, "type": "aggregate_country"}
            })

    if "product_category" in df.columns:
        cat_stats = df.groupby("product_category").agg(
            count=("user_id", "count"),
            avg_spend=("monthly_spend", "mean"),
            avg_clv=("customer_lifetime_value", "mean"),
            churn_rate=("churn_label", "mean")
        ).reset_index().sort_values("avg_clv", ascending=False)
        for _, row in cat_stats.iterrows():
            text = (f"Product category '{row['product_category']}' summary: "
                    f"{row['count']} users, avg spend ${row['avg_spend']:.2f}, "
                    f"avg CLV ${row['avg_clv']:.2f}, churn rate {row['churn_rate']*100:.1f}%.")
            chunks.append({
                "id": f"cat_{dataset_id}_{row['product_category']}",
                "text": text,
                "metadata": {"dataset_id": dataset_id, "type": "aggregate_category"}
            })

    total = len(df)
    churned = int(df["churn_label"].sum()) if "churn_label" in df.columns else 0
    avg_clv = df["customer_lifetime_value"].mean() if "customer_lifetime_value" in df.columns else 0
    avg_spend = df["monthly_spend"].mean() if "monthly_spend" in df.columns else 0
    avg_nps = df["NPS_score"].mean() if "NPS_score" in df.columns else 0
    text = (f"Overall dataset summary: {total} total users, "
            f"{churned} churned ({churned/total*100:.1f}% churn rate), "
            f"avg CLV ${avg_clv:.2f}, avg monthly spend ${avg_spend:.2f}, "
            f"avg NPS score {avg_nps:.1f}.")
    chunks.append({
        "id": f"overall_{dataset_id}",
        "text": text,
        "metadata": {"dataset_id": dataset_id, "type": "overall_summary"}
    })

    return chunks

def embed_and_store(chunks: list[dict]):
    model = get_embed_model()
    collection = get_chroma()
    texts = [c["text"] for c in chunks]
    ids = [c["id"] for c in chunks]
    metadatas = [c["metadata"] for c in chunks]
    for i in range(0, len(texts), 64):
        embeddings = model.encode(texts[i:i+64], show_progress_bar=False).tolist()
        collection.upsert(
            ids=ids[i:i+64],
            embeddings=embeddings,
            documents=texts[i:i+64],
            metadatas=metadatas[i:i+64]
        )
    logger.info(f"Stored {len(chunks)} chunks in ChromaDB")

def retrieve_context(question: str, dataset_id: int) -> list[str]:
    model = get_embed_model()
    collection = get_chroma()
    q_embedding = model.encode([question]).tolist()[0]
    results = collection.query(
        query_embeddings=[q_embedding],
        n_results=TOP_K_CHUNKS,
        where={"dataset_id": dataset_id}
    )
    return results["documents"][0] if results["documents"] else []

# ── Prompts ───────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are InsightIQ, an elite product analytics AI assistant embedded inside a business intelligence platform.
Your role is to answer data questions with precision, insight, and business context.

You will be given:
1. A user's natural language question about their product/ecommerce data
2. Relevant data context retrieved from their dataset

STRICT RULES:
- Answer ONLY based on the provided context. Do not make up statistics.
- Be concise but insightful. Lead with the key finding, then explain.
- Always end your response with a JSON block for chart rendering.

REQUIRED OUTPUT FORMAT:
Write your natural language answer first (2-4 paragraphs max), then on a new line output:
```json
{
  "chart_type": "bar" | "line" | "pie" | "none",
  "chart_title": "descriptive title",
  "chart_labels": ["label1", "label2", ...],
  "chart_values": [number1, number2, ...],
  "chart_color": "blue" | "green" | "red" | "purple" | "orange"
}
```

Choose chart_type based on the question:
- "bar" for comparisons across categories
- "line" for trends over time
- "pie" for proportions/distributions
- "none" if no chart makes sense

If you cannot answer from the context, say so clearly and set chart_type to "none"."""

def build_user_message(question: str, context_chunks: list[str]) -> str:
    context_text = "\n\n".join([f"[Data Context {i+1}]: {c}" for i, c in enumerate(context_chunks)])
    return f"""Question: {question}

---
DATA CONTEXT:
{context_text}
---

Please provide a comprehensive answer with business insights, followed by the required JSON chart block."""

def parse_chart_from_text(full_text: str) -> tuple[str, dict]:
    chart_data = {"chart_type": "none", "chart_title": "", "chart_labels": [], "chart_values": [], "chart_color": "blue"}
    try:
        json_match = re.search(r"```json\s*([\s\S]*?)```", full_text)
        if json_match:
            chart_data = json.loads(json_match.group(1))
            answer_text = full_text[:json_match.start()].strip()
        else:
            answer_text = full_text.strip()
    except Exception as e:
        logger.warning(f"Chart JSON parse error: {e}")
        answer_text = full_text.strip()
    return answer_text, chart_data

# ── Streaming generator ───────────────────────────────────────────────────────
async def stream_claude_response(question: str, dataset_id: int) -> AsyncGenerator[str, None]:
    """
    Yields Server-Sent Events:
      {"type": "token",  "text": "..."}       — streamed answer tokens
      {"type": "chart",  "data": {...}}        — chart JSON after completion
      {"type": "done",   "context_used": N}   — signals end
      {"type": "error",  "message": "..."}    — on failure
    """
    try:
        context_chunks = retrieve_context(question, dataset_id)
        if not context_chunks:
            yield f"data: {json.dumps({'type': 'error', 'message': 'No data found. Upload a dataset first.'})}\n\n"
            return

        client = get_anthropic()
        full_text = ""
        streaming_suppressed = False  # True once we hit the ```json fence

        with client.messages.stream(
            model=CLAUDE_MODEL,
            max_tokens=1500,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": build_user_message(question, context_chunks)}]
        ) as stream:
            for chunk in stream.text_stream:
                full_text += chunk

                if not streaming_suppressed:
                    # Check if the JSON fence has appeared in the accumulated text
                    fence_pos = full_text.find("```json")
                    if fence_pos != -1:
                        # Stream the text up to the fence, then suppress
                        streaming_suppressed = True
                        # The visible portion is everything before the fence
                        # We may have already streamed part of it — send only the new slice
                        already_streamed = full_text[:fence_pos - len(chunk) if len(full_text) - len(chunk) <= fence_pos else fence_pos]
                        remainder = full_text[:fence_pos][len(already_streamed):]
                        if remainder:
                            yield f"data: {json.dumps({'type': 'token', 'text': remainder})}\n\n"
                    else:
                        yield f"data: {json.dumps({'type': 'token', 'text': chunk})}\n\n"

        answer_text, chart_data = parse_chart_from_text(full_text)

        yield f"data: {json.dumps({'type': 'chart', 'data': chart_data})}\n\n"

        # Save to history
        try:
            con = get_db()
            con.execute(
                "INSERT INTO query_history (dataset_id, question, answer, chart_data) VALUES (?, ?, ?, ?)",
                (dataset_id, question, answer_text, json.dumps(chart_data))
            )
            con.commit()
            con.close()
        except Exception as e:
            logger.warning(f"History save failed: {e}")

        yield f"data: {json.dumps({'type': 'done', 'context_used': len(context_chunks)})}\n\n"

    except Exception as e:
        logger.error(f"Streaming error: {e}")
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

def call_claude_sync(question: str, context_chunks: list[str]) -> tuple[str, dict]:
    """Blocking Claude call used by dashboard batch generation."""
    client = get_anthropic()
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=800,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_user_message(question, context_chunks)}]
    )
    return parse_chart_from_text(response.content[0].text)

# ── Pydantic models ───────────────────────────────────────────────────────────
class QueryRequest(BaseModel):
    question: str
    dataset_id: int = 1

# ── Routes ────────────────────────────────────────────────────────────────────
@app.post("/upload")
async def upload_csv(file: UploadFile = File(...)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(400, "Only CSV files are supported.")
    try:
        contents = await file.read()
        df = pd.read_csv(io.BytesIO(contents))
        if df.empty:
            raise HTTPException(400, "CSV file is empty.")

        for col in df.select_dtypes(include=[np.number]).columns:
            df[col] = df[col].fillna(0)

        con = get_db()
        cur = con.cursor()
        cur.execute(
            "INSERT INTO uploaded_datasets (filename, row_count, columns) VALUES (?, ?, ?)",
            (file.filename, len(df), json.dumps(df.columns.tolist()))
        )
        dataset_id = cur.lastrowid
        con.commit()
        con.close()

        chunks = chunk_dataframe(df, dataset_id)
        embed_and_store(chunks)

        return {
            "success": True,
            "dataset_id": dataset_id,
            "filename": file.filename,
            "row_count": len(df),
            "columns": df.columns.tolist(),
            "chunks_created": len(chunks)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload error: {e}")
        raise HTTPException(500, f"Upload failed: {str(e)}")

@app.post("/query/stream")
async def query_stream(req: QueryRequest):
    """
    Streaming SSE endpoint. Frontend reads this with EventSource / fetch + ReadableStream.
    Each event is a JSON object with a 'type' field.
    """
    if not req.question.strip():
        raise HTTPException(400, "Question cannot be empty.")
    return StreamingResponse(
        stream_claude_response(req.question, req.dataset_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

@app.post("/query")
async def query(req: QueryRequest):
    """Non-streaming fallback."""
    if not req.question.strip():
        raise HTTPException(400, "Question cannot be empty.")
    try:
        context_chunks = retrieve_context(req.question, req.dataset_id)
        if not context_chunks:
            raise HTTPException(404, "No data context found.")
        answer, chart_data = call_claude_sync(req.question, context_chunks)
        con = get_db()
        con.execute(
            "INSERT INTO query_history (dataset_id, question, answer, chart_data) VALUES (?, ?, ?, ?)",
            (req.dataset_id, req.question, answer, json.dumps(chart_data))
        )
        con.commit()
        con.close()
        return {"question": req.question, "answer": answer, "chart_data": chart_data, "context_used": len(context_chunks)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Query error: {e}")
        raise HTTPException(500, f"Query failed: {str(e)}")

@app.get("/dashboard/{dataset_id}")
async def get_dashboard(dataset_id: int, refresh: bool = False):
    """
    Auto-dashboard: runs 5 pre-built insight questions and caches results.
    Cached per dataset — pass ?refresh=true to regenerate.
    """
    if not refresh:
        con = get_db()
        row = con.execute(
            "SELECT panels FROM dashboard_cache WHERE dataset_id=?", (dataset_id,)
        ).fetchone()
        con.close()
        if row:
            return {"dataset_id": dataset_id, "panels": json.loads(row[0]), "cached": True}

    con = get_db()
    ds = con.execute("SELECT id FROM uploaded_datasets WHERE id=?", (dataset_id,)).fetchone()
    con.close()
    if not ds:
        raise HTTPException(404, "Dataset not found.")

    panels = []
    for q in DASHBOARD_QUESTIONS:
        try:
            context_chunks = retrieve_context(q["question"], dataset_id)
            if not context_chunks:
                continue
            answer, chart_data = call_claude_sync(q["question"], context_chunks)
            panels.append({
                "id": q["id"],
                "title": q["title"],
                "question": q["question"],
                "answer": answer,
                "chart_data": chart_data,
            })
        except Exception as e:
            logger.warning(f"Dashboard panel '{q['id']}' failed: {e}")

    con = get_db()
    con.execute(
        "INSERT OR REPLACE INTO dashboard_cache (dataset_id, panels) VALUES (?, ?)",
        (dataset_id, json.dumps(panels))
    )
    con.commit()
    con.close()

    return {"dataset_id": dataset_id, "panels": panels, "cached": False}

@app.get("/schema")
async def get_schema(dataset_id: int = 1):
    con = get_db()
    row = con.execute(
        "SELECT filename, row_count, columns FROM uploaded_datasets WHERE id=?", (dataset_id,)
    ).fetchone()
    con.close()
    if not row:
        raise HTTPException(404, "Dataset not found.")
    return {"dataset_id": dataset_id, "filename": row[0], "row_count": row[1], "columns": json.loads(row[2])}

@app.get("/datasets")
async def list_datasets():
    con = get_db()
    rows = con.execute(
        "SELECT id, filename, row_count, uploaded_at FROM uploaded_datasets ORDER BY id DESC"
    ).fetchall()
    con.close()
    return [{"id": r[0], "filename": r[1], "row_count": r[2], "uploaded_at": r[3]} for r in rows]

@app.get("/history")
async def get_history(dataset_id: int = 1, limit: int = 20):
    con = get_db()
    rows = con.execute(
        "SELECT id, question, answer, chart_data, created_at FROM query_history "
        "WHERE dataset_id=? ORDER BY id DESC LIMIT ?",
        (dataset_id, limit)
    ).fetchall()
    con.close()
    history = []
    for r in rows:
        try:
            chart_data = json.loads(r[3]) if r[3] else None
        except Exception:
            chart_data = None
        history.append({"id": r[0], "question": r[1], "answer": r[2], "chart_data": chart_data, "created_at": r[4]})
    return history

@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.0.0", "timestamp": datetime.utcnow().isoformat()}
