# InsightIQ — LLM-Powered Product Analytics Assistant

![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?style=flat-square&logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react&logoColor=black)
![Claude](https://img.shields.io/badge/Claude-Sonnet-D97757?style=flat-square)
![ChromaDB](https://img.shields.io/badge/ChromaDB-Vector_DB-FF6B35?style=flat-square)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat-square&logo=docker&logoColor=white)
![Railway](https://img.shields.io/badge/Deployed_on-Railway-7B2FF7?style=flat-square&logo=railway&logoColor=white)

> Ask natural language questions about your product data. Get AI-powered answers **streamed in real-time** — grounded in your actual data via RAG, with auto-generated charts.

**🚀 [Live Demo](https://your-frontend-url.railway.app)** &nbsp;·&nbsp; **[Deploy your own →](./DEPLOY.md)**

---

## 🖼️ Screenshots

*[Screenshot: Main chat interface with an analytics question answered and a bar chart rendered]*
*[Screenshot: Sidebar showing dataset schema and query history]*
*[Screenshot: Pie chart showing subscription plan distribution]*

---

## 🚀 What is InsightIQ?

InsightIQ is a full-stack business intelligence application that combines **Retrieval-Augmented Generation (RAG)** with the Claude LLM to answer complex product analytics questions grounded in actual CSV data.

Instead of hallucinating statistics, InsightIQ:
1. Chunks and embeds your dataset using `sentence-transformers`
2. Stores vector embeddings in ChromaDB
3. On each query, retrieves the most semantically relevant data chunks
4. Passes those chunks as grounding context to Claude
5. Returns a natural language insight **plus** structured JSON for auto-rendered charts

---

## 💬 Example Questions to Ask

```
"What is driving churn this quarter?"
"Which user segment has the highest lifetime value?"
"Show me the average monthly spend by subscription plan"
"Which countries have the highest churn rates?"
"How does NPS score correlate with subscription plan?"
"What's the revenue breakdown by product category?"
"Compare CLV across different age groups"
"Which customer cohort is most at risk of churning?"
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND (React)                         │
│  Sidebar: Schema, History    │    Chat: Questions + Answers     │
│  CSV Upload Button           │    Recharts: Bar/Line/Pie        │
└──────────────────────────────┬──────────────────────────────────┘
                               │ HTTP (REST)
┌──────────────────────────────▼──────────────────────────────────┐
│                       BACKEND (FastAPI)                         │
│                                                                 │
│  POST /upload ──► CSV Parser ──► SQLite + Chunker              │
│                                         │                       │
│                                    Sentence-Transformers        │
│                                    (all-MiniLM-L6-v2)          │
│                                         │                       │
│                                    ChromaDB (Embeddings)        │
│                                                                 │
│  POST /query ──► Embed Question ──► ChromaDB Semantic Search   │
│                        │                                        │
│               Top-K Relevant Chunks                             │
│                        │                                        │
│               Claude Prompt + Context                           │
│                        │                                        │
│               Claude API (claude-sonnet)                        │
│                        │                                        │
│               Answer + Chart JSON ──► SQLite History           │
└─────────────────────────────────────────────────────────────────┘
         │                    │                    │
      SQLite             ChromaDB             Anthropic API
   (metadata,          (vector              (LLM reasoning)
   history)            embeddings)
```

---

## 🛠️ Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Frontend | React 18 + Vite | UI framework |
| Styling | Tailwind CSS | Utility-first CSS |
| Charts | Recharts | Auto-rendered data visualizations |
| Backend | FastAPI (Python 3.11) | REST API + RAG orchestration |
| LLM | Claude Sonnet (Anthropic) | Natural language answers |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) | Semantic vector encoding |
| Vector DB | ChromaDB | Embedding storage + similarity search |
| Structured DB | SQLite | Dataset metadata, query history |
| Deployment | Docker Compose | One-command setup |

---

## ⚡ Quick Start (Docker)

### Prerequisites
- Docker & Docker Compose installed
- Anthropic API key ([get one here](https://console.anthropic.com))

```bash
# 1. Clone the repository
git clone https://github.com/yourname/insightiq.git
cd insightiq

# 2. Set your API key
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY

# 3. Launch everything
docker-compose up --build

# 4. Open the app
open http://localhost:3000
```

That's it. The backend starts on `:8000`, the frontend on `:3000`.

---

## 🔧 Manual Setup (Development)

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

export ANTHROPIC_API_KEY=sk-ant-your-key-here
mkdir -p /app/data

uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm install
# For development, update vite.config.js proxy to point to localhost:8000
npm run dev
# Opens at http://localhost:3000
```

---

## 📊 Sample Dataset

The repo includes `ecommerce_data.csv` — 500 rows of realistic synthetic e-commerce user data:

| Column | Type | Description |
|--------|------|-------------|
| `user_id` | string | Unique user identifier |
| `age` | int | User age (18–65) |
| `gender` | string | Male / Female / Non-binary |
| `country` | string | 10 countries (USA, UK, etc.) |
| `signup_date` | date | Account creation date |
| `last_active_date` | date | Most recent activity |
| `subscription_plan` | string | Free / Basic / Pro / Enterprise |
| `monthly_spend` | float | Average monthly spend ($) |
| `total_orders` | int | Lifetime order count |
| `product_category` | string | Primary shopping category |
| `churn_label` | int | 1 = churned, 0 = active |
| `customer_lifetime_value` | float | Total predicted value ($) |
| `NPS_score` | int | Net Promoter Score (0–10) |

---

## 🔌 API Reference

| Method | Endpoint | Description |
|--------|---------|-------------|
| `POST` | `/upload` | Upload CSV → embed → index |
| `POST` | `/query` | Ask a question → RAG → Claude → chart |
| `GET` | `/schema?dataset_id=1` | Column names + metadata |
| `GET` | `/history?dataset_id=1` | Past Q&A history |
| `GET` | `/datasets` | List uploaded datasets |
| `GET` | `/health` | Health check |

---

## 🧩 RAG Pipeline Deep Dive

```
CSV Upload
    │
    ▼
DataFrame Parser (pandas)
    │
    ▼
Chunker ──────────────────────────────────────────────┐
  • Per-row text summaries                             │
  • Aggregate chunks by plan, country, category        │
  • Overall dataset summary chunk                      │
    │                                                  │
    ▼                                                  │
SentenceTransformer.encode()                           │
(all-MiniLM-L6-v2, 384-dim vectors)                   │
    │                                                  │
    ▼                                                  │
ChromaDB.upsert() with cosine similarity index         │
                                                       │
Query ─────────────────────────────────────────────────┘
    │
    ▼
Embed question → ChromaDB.query(top_k=8)
    │
    ▼
Build Claude prompt:
  system: "Answer ONLY from context, return JSON chart block"
  user: question + 8 context chunks
    │
    ▼
Claude API → parse answer + chart JSON
    │
    ▼
Log to SQLite → Return to frontend → Render chart
```

---

## 🏆 Built For Portfolio

This project demonstrates proficiency in:

**Data Engineering**
- ETL pipeline: CSV → SQLite + vector database
- Data chunking strategies for RAG
- Aggregate analytics with pandas

**AI/ML Engineering**
- RAG architecture (Retrieval-Augmented Generation)
- Semantic embedding with sentence-transformers
- Prompt engineering for structured LLM outputs
- Vector similarity search with ChromaDB

**Backend Development**
- FastAPI with async endpoints
- Clean REST API design with proper error handling
- SQLite schema design with relationship modeling

**Frontend Development**
- React 18 with hooks (useState, useEffect, useCallback, useRef)
- Real-time chat UI with streaming-ready architecture
- Dynamic chart rendering with Recharts
- Professional dark UI with Tailwind CSS

**DevOps**
- Docker multi-stage builds (frontend + backend)
- Docker Compose for local orchestration
- Environment-based configuration

---

## 📁 Project Structure

```
insightiq/
├── docker-compose.yml
├── .env.example
├── ecommerce_data.csv         # Sample dataset
├── backend/
│   ├── main.py                # FastAPI app + RAG pipeline
│   ├── requirements.txt
│   └── Dockerfile
└── frontend/
    ├── src/
    │   ├── App.jsx             # Root component + state
    │   ├── api.js              # API client
    │   ├── index.css           # Global styles
    │   └── components/
    │       ├── Sidebar.jsx     # Dataset info + history
    │       ├── Message.jsx     # Chat message bubbles
    │       ├── ChartRenderer.jsx  # Auto chart selection
    │       └── SuggestedQuestions.jsx
    ├── index.html
    ├── vite.config.js
    ├── tailwind.config.js
    ├── package.json
    └── Dockerfile
```

---

## 📄 License

MIT — free to use, fork, and build on.

---

*Built with ❤️ to demonstrate RAG, LLM integration, and full-stack data product development.*
