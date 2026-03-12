"""
InsightIQ Backend - FastAPI + RAG Pipeline
v3: SQLite FTS5 for retrieval — no local ML models, fits in 512MB free tier RAM
"""

import os, re, io, json, sqlite3, logging
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_DATA_DIR = os.environ.get("DATA_DIR", "/app/data")
DB_PATH = os.path.join(_DATA_DIR, "insightiq.db")
CLAUDE_MODEL = "claude-sonnet-4-20250514"
TOP_K_CHUNKS = 8

DASHBOARD_QUESTIONS = [
    {"id": "churn_by_plan",    "question": "What is the churn rate for each subscription plan?",              "title": "Churn Rate by Plan"},
    {"id": "clv_by_category",  "question": "What is the average customer lifetime value by product category?", "title": "Avg CLV by Category"},
    {"id": "spend_by_plan",    "question": "Show me the average monthly spend for each subscription plan.",    "title": "Monthly Spend by Plan"},
    {"id": "users_by_country", "question": "What is the distribution of users across countries?",              "title": "Users by Country"},
    {"id": "nps_by_plan",      "question": "How does average NPS score compare across subscription plans?",    "title": "NPS Score by Plan"},
]

@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(_DATA_DIR, exist_ok=True)
    init_db()
    logger.info(f"InsightIQ backend v3 started — data dir: {_DATA_DIR}")
    yield

app = FastAPI(title="InsightIQ API", version="3.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

_anthropic_client: Optional[anthropic.Anthropic] = None
def get_anthropic():
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    return _anthropic_client

def init_db():
    con = sqlite3.connect(DB_PATH)
    con.executescript("""
        CREATE TABLE IF NOT EXISTS uploaded_datasets (
            id INTEGER PRIMARY KEY AUTOINCREMENT, filename TEXT NOT NULL,
            row_count INTEGER, columns TEXT, uploaded_at TEXT DEFAULT (datetime('now')));
        CREATE TABLE IF NOT EXISTS query_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT, dataset_id INTEGER,
            question TEXT NOT NULL, answer TEXT, chart_data TEXT,
            created_at TEXT DEFAULT (datetime('now')));
        CREATE TABLE IF NOT EXISTS dashboard_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT, dataset_id INTEGER UNIQUE,
            panels TEXT, created_at TEXT DEFAULT (datetime('now')));
        CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
            chunk_id, dataset_id UNINDEXED, chunk_text, chunk_type UNINDEXED,
            tokenize = 'porter ascii');
    """)
    con.commit(); con.close()

def get_db(): return sqlite3.connect(DB_PATH)

def chunk_dataframe(df: pd.DataFrame, dataset_id: int) -> list[dict]:
    chunks = []
    for idx, row in df.iterrows():
        parts = [f"User {row.get('user_id', idx)}:"]
        for col, label in [("age","age"),("gender","gender"),("country","country"),
                           ("subscription_plan","plan"),("product_category","category")]:
            if col in row: parts.append(f"{label} {row[col]}")
        for col, label, fmt in [("monthly_spend","monthly spend","${:.2f}"),
                                  ("customer_lifetime_value","CLV","${:.2f}"),
                                  ("total_orders","orders","{:.0f}"),
                                  ("NPS_score","NPS","{:.0f}")]:
            if col in row:
                try: parts.append(f"{label} {fmt.format(float(row[col]))}")
                except: pass
        if "churn_label" in row:
            parts.append(f"churned {'yes' if row['churn_label']==1 else 'no'}")
        chunks.append({"id": f"row_{dataset_id}_{idx}", "text": " ".join(parts), "type": "row"})

    if "subscription_plan" in df.columns:
        for plan, g in df.groupby("subscription_plan"):
            chunks.append({"id": f"plan_{dataset_id}_{plan}", "type": "aggregate", "text":
                f"Plan {plan}: {len(g)} users, avg spend ${g['monthly_spend'].mean():.2f}, "
                f"avg CLV ${g['customer_lifetime_value'].mean():.2f}, "
                f"churn rate {g['churn_label'].mean()*100:.1f}%, avg NPS {g['NPS_score'].mean():.1f}."})

    if "country" in df.columns:
        for country, g in df.groupby("country"):
            chunks.append({"id": f"country_{dataset_id}_{country}", "type": "aggregate", "text":
                f"Country {country}: {len(g)} users, avg CLV ${g['customer_lifetime_value'].mean():.2f}, "
                f"churn rate {g['churn_label'].mean()*100:.1f}%, avg spend ${g['monthly_spend'].mean():.2f}."})

    if "product_category" in df.columns:
        for cat, g in df.groupby("product_category"):
            chunks.append({"id": f"cat_{dataset_id}_{cat}", "type": "aggregate", "text":
                f"Category {cat}: {len(g)} users, avg spend ${g['monthly_spend'].mean():.2f}, "
                f"avg CLV ${g['customer_lifetime_value'].mean():.2f}, churn {g['churn_label'].mean()*100:.1f}%."})

    total = len(df)
    churned = int(df["churn_label"].sum()) if "churn_label" in df.columns else 0
    chunks.append({"id": f"overall_{dataset_id}", "type": "summary", "text":
        f"Overall: {total} users, {churned} churned ({churned/total*100:.1f}%), "
        f"avg CLV ${df['customer_lifetime_value'].mean():.2f}, "
        f"avg spend ${df['monthly_spend'].mean():.2f}, avg NPS {df['NPS_score'].mean():.1f}."})
    return chunks

def store_chunks(chunks, dataset_id):
    con = get_db()
    con.execute("DELETE FROM chunks_fts WHERE dataset_id=?", (dataset_id,))
    con.executemany("INSERT INTO chunks_fts (chunk_id,dataset_id,chunk_text,chunk_type) VALUES (?,?,?,?)",
        [(c["id"], dataset_id, c["text"], c["type"]) for c in chunks])
    con.commit(); con.close()
    logger.info(f"Stored {len(chunks)} chunks for dataset {dataset_id}")

def retrieve_context(question: str, dataset_id: int) -> list[str]:
    con = get_db()
    agg = [r[0] for r in con.execute(
        "SELECT chunk_text FROM chunks_fts WHERE dataset_id=? AND chunk_type!='row' LIMIT 20",
        (dataset_id,)).fetchall()]
    safe_q = re.sub(r"[^\w\s]", " ", question).strip()
    fts = []
    if safe_q:
        try:
            fts = [r[0] for r in con.execute(
                "SELECT chunk_text FROM chunks_fts WHERE chunks_fts MATCH ? AND dataset_id=? LIMIT ?",
                (safe_q, dataset_id, TOP_K_CHUNKS)).fetchall()]
        except Exception: pass
    con.close()
    seen, results = set(), []
    for t in agg + fts:
        if t not in seen:
            seen.add(t); results.append(t)
    return results[:TOP_K_CHUNKS + len(agg)]

SYSTEM_PROMPT = """You are InsightIQ, an elite product analytics AI assistant.
Answer questions about business data with precision and insight.

RULES:
- Answer ONLY from the provided data context. Never invent statistics.
- Be concise but insightful. Lead with the key finding.
- Always end with a JSON chart block.

REQUIRED OUTPUT FORMAT — write your answer first, then:
```json
{
  "chart_type": "bar" | "line" | "pie" | "none",
  "chart_title": "descriptive title",
  "chart_labels": ["label1", "label2"],
  "chart_values": [number1, number2],
  "chart_color": "blue" | "green" | "red" | "purple" | "orange"
}
```

Choose chart_type: bar=comparisons, line=trends, pie=proportions, none=no chart fits.
If you cannot answer from context, say so and use chart_type none."""

def build_msg(question, chunks):
    ctx = "\n\n".join([f"[Context {i+1}]: {c}" for i,c in enumerate(chunks)])
    return f"Question: {question}\n\nDATA CONTEXT:\n{ctx}\n\nAnswer with insight then JSON chart block."

def parse_chart(text):
    chart = {"chart_type":"none","chart_title":"","chart_labels":[],"chart_values":[],"chart_color":"blue"}
    try:
        m = re.search(r"```json\s*([\s\S]*?)```", text)
        if m:
            return text[:m.start()].strip(), json.loads(m.group(1))
    except Exception as e:
        logger.warning(f"Chart parse: {e}")
    return text.strip(), chart

async def stream_claude(question: str, dataset_id: int) -> AsyncGenerator[str, None]:
    try:
        chunks = retrieve_context(question, dataset_id)
        if not chunks:
            yield f"data: {json.dumps({'type':'error','message':'No data found. Upload a dataset first.'})}\n\n"
            return
        client = get_anthropic()
        full_text = ""; fence_hit = False
        with client.messages.stream(model=CLAUDE_MODEL, max_tokens=1500, system=SYSTEM_PROMPT,
                messages=[{"role":"user","content":build_msg(question,chunks)}]) as stream:
            for token in stream.text_stream:
                full_text += token
                if not fence_hit:
                    pos = full_text.find("```json")
                    if pos != -1:
                        fence_hit = True
                        prev_len = len(full_text) - len(token)
                        if pos > prev_len:
                            yield f"data: {json.dumps({'type':'token','text':full_text[prev_len:pos]})}\n\n"
                    else:
                        yield f"data: {json.dumps({'type':'token','text':token})}\n\n"
        answer, chart = parse_chart(full_text)
        yield f"data: {json.dumps({'type':'chart','data':chart})}\n\n"
        try:
            con = get_db()
            con.execute("INSERT INTO query_history (dataset_id,question,answer,chart_data) VALUES (?,?,?,?)",
                (dataset_id, question, answer, json.dumps(chart)))
            con.commit(); con.close()
        except Exception as e: logger.warning(f"History: {e}")
        yield f"data: {json.dumps({'type':'done','context_used':len(chunks)})}\n\n"
    except Exception as e:
        logger.error(f"Stream error: {e}")
        yield f"data: {json.dumps({'type':'error','message':str(e)})}\n\n"

def claude_sync(question, chunks):
    r = get_anthropic().messages.create(model=CLAUDE_MODEL, max_tokens=800, system=SYSTEM_PROMPT,
        messages=[{"role":"user","content":build_msg(question,chunks)}])
    return parse_chart(r.content[0].text)

class QueryRequest(BaseModel):
    question: str
    dataset_id: int = 1

@app.post("/upload")
async def upload_csv(file: UploadFile = File(...)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(400, "Only CSV files supported.")
    try:
        df = pd.read_csv(io.BytesIO(await file.read()))
        if df.empty: raise HTTPException(400, "CSV is empty.")
        for col in df.select_dtypes(include=[np.number]).columns:
            df[col] = df[col].fillna(0)
        con = get_db(); cur = con.cursor()
        cur.execute("INSERT INTO uploaded_datasets (filename,row_count,columns) VALUES (?,?,?)",
            (file.filename, len(df), json.dumps(df.columns.tolist())))
        dataset_id = cur.lastrowid; con.commit(); con.close()
        chunks = chunk_dataframe(df, dataset_id)
        store_chunks(chunks, dataset_id)
        return {"success":True,"dataset_id":dataset_id,"filename":file.filename,
                "row_count":len(df),"columns":df.columns.tolist(),"chunks_created":len(chunks)}
    except HTTPException: raise
    except Exception as e:
        logger.error(f"Upload: {e}"); raise HTTPException(500, f"Upload failed: {e}")

@app.post("/query/stream")
async def query_stream(req: QueryRequest):
    if not req.question.strip(): raise HTTPException(400, "Question cannot be empty.")
    return StreamingResponse(stream_claude(req.question, req.dataset_id),
        media_type="text/event-stream", headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})

@app.post("/query")
async def query(req: QueryRequest):
    if not req.question.strip(): raise HTTPException(400, "Empty question.")
    chunks = retrieve_context(req.question, req.dataset_id)
    if not chunks: raise HTTPException(404, "No data. Upload first.")
    answer, chart = claude_sync(req.question, chunks)
    con = get_db()
    con.execute("INSERT INTO query_history (dataset_id,question,answer,chart_data) VALUES (?,?,?,?)",
        (req.dataset_id, req.question, answer, json.dumps(chart)))
    con.commit(); con.close()
    return {"question":req.question,"answer":answer,"chart_data":chart,"context_used":len(chunks)}

@app.get("/dashboard/{dataset_id}")
async def get_dashboard(dataset_id: int, refresh: bool = False):
    if not refresh:
        con = get_db()
        row = con.execute("SELECT panels FROM dashboard_cache WHERE dataset_id=?", (dataset_id,)).fetchone()
        con.close()
        if row: return {"dataset_id":dataset_id,"panels":json.loads(row[0]),"cached":True}
    con = get_db()
    if not con.execute("SELECT id FROM uploaded_datasets WHERE id=?", (dataset_id,)).fetchone():
        con.close(); raise HTTPException(404, "Dataset not found.")
    con.close()
    panels = []
    for q in DASHBOARD_QUESTIONS:
        try:
            chunks = retrieve_context(q["question"], dataset_id)
            if not chunks: continue
            answer, chart = claude_sync(q["question"], chunks)
            panels.append({"id":q["id"],"title":q["title"],"question":q["question"],"answer":answer,"chart_data":chart})
        except Exception as e: logger.warning(f"Panel {q['id']}: {e}")
    con = get_db()
    con.execute("INSERT OR REPLACE INTO dashboard_cache (dataset_id,panels) VALUES (?,?)",
        (dataset_id, json.dumps(panels)))
    con.commit(); con.close()
    return {"dataset_id":dataset_id,"panels":panels,"cached":False}

@app.get("/schema")
async def get_schema(dataset_id: int = 1):
    con = get_db()
    row = con.execute("SELECT filename,row_count,columns FROM uploaded_datasets WHERE id=?", (dataset_id,)).fetchone()
    con.close()
    if not row: raise HTTPException(404, "Dataset not found.")
    return {"dataset_id":dataset_id,"filename":row[0],"row_count":row[1],"columns":json.loads(row[2])}

@app.get("/datasets")
async def list_datasets():
    con = get_db()
    rows = con.execute("SELECT id,filename,row_count,uploaded_at FROM uploaded_datasets ORDER BY id DESC").fetchall()
    con.close()
    return [{"id":r[0],"filename":r[1],"row_count":r[2],"uploaded_at":r[3]} for r in rows]

@app.get("/history")
async def get_history(dataset_id: int = 1, limit: int = 20):
    con = get_db()
    rows = con.execute("SELECT id,question,answer,chart_data,created_at FROM query_history "
        "WHERE dataset_id=? ORDER BY id DESC LIMIT ?", (dataset_id, limit)).fetchall()
    con.close()
    return [{"id":r[0],"question":r[1],"answer":r[2],
             "chart_data":json.loads(r[3]) if r[3] else None,"created_at":r[4]} for r in rows]

@app.get("/health")
async def health():
    return {"status":"ok","version":"3.0.0","timestamp":datetime.utcnow().isoformat()}
