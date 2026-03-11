# Deploying InsightIQ to Railway

This guide gets InsightIQ live on the internet in ~15 minutes.
Railway is the recommended platform — it supports Docker, handles HTTPS automatically,
and has a free tier sufficient for portfolio demos.

---

## Prerequisites

- A [Railway account](https://railway.app) (free)
- Your code pushed to a GitHub repository
- Your `ANTHROPIC_API_KEY`

---

## Architecture on Railway

You'll create **two Railway services** from the same GitHub repo:

```
GitHub Repo (monorepo)
    │
    ├── backend/   →  Railway Service: "insightiq-backend"
    │                 URL: https://insightiq-backend-xxxx.railway.app
    │
    └── frontend/  →  Railway Service: "insightiq-frontend"
                      URL: https://insightiq-frontend-xxxx.railway.app
```

The frontend's `VITE_API_URL` build argument points to the backend's Railway URL,
so all API calls go directly from browser → backend (no nginx proxy hop in production).

---

## Step 1 — Push to GitHub

```bash
cd insightiq
git init
git add .
git commit -m "feat: InsightIQ v2 - RAG analytics assistant"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/insightiq.git
git push -u origin main
```

---

## Step 2 — Deploy the Backend

1. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo**
2. Select your `insightiq` repo
3. Railway will detect the repo. Click **Add Service** → **GitHub Repo** again  
   *(you'll add a second service for the frontend in Step 4)*
4. In the service settings:
   - **Name**: `insightiq-backend`
   - **Root Directory**: `backend`
   - **Builder**: Dockerfile (auto-detected)
5. Go to **Variables** tab and add:
   ```
   ANTHROPIC_API_KEY = sk-ant-your-key-here
   DATA_DIR          = /app/data
   ```
6. (Optional but recommended) Add a **Volume**:
   - Click **Add Volume** → mount path: `/app/data`
   - This persists your SQLite DB and ChromaDB across deploys
7. Click **Deploy** — wait ~3–5 minutes for the first build
8. Once deployed, copy the backend's public URL from the **Settings** tab:
   ```
   https://insightiq-backend-xxxx.railway.app
   ```

---

## Step 3 — Verify the Backend

Open in your browser:
```
https://insightiq-backend-xxxx.railway.app/health
```
You should see:
```json
{"status": "ok", "version": "2.0.0", "timestamp": "..."}
```

Also check the API docs:
```
https://insightiq-backend-xxxx.railway.app/docs
```

---

## Step 4 — Deploy the Frontend

1. In your Railway project, click **New** → **GitHub Repo** → same repo
2. In service settings:
   - **Name**: `insightiq-frontend`
   - **Root Directory**: `frontend`
   - **Builder**: Dockerfile
3. Go to **Variables** tab and add:
   ```
   VITE_API_URL = https://insightiq-backend-xxxx.railway.app
   ```
   *(Use your actual backend URL from Step 2)*
4. Click **Deploy**
5. Once done, copy the frontend URL:
   ```
   https://insightiq-frontend-xxxx.railway.app
   ```

---

## Step 5 — Test the Live App

1. Open `https://insightiq-frontend-xxxx.railway.app`
2. Click **Upload CSV Dataset** → upload `ecommerce_data.csv`
3. Wait ~30 seconds for embedding (500 rows + aggregate chunks)
4. Ask: *"What is driving churn this quarter?"*
5. Watch the answer stream in word-by-word
6. Click the **Dashboard** tab to see the 5 auto-generated insights

---

## Step 6 — Custom Domain (Optional)

1. Buy a domain (Namecheap, Google Domains, etc.)
2. In Railway frontend service → **Settings** → **Custom Domain**
3. Add your domain and follow the DNS instructions
4. Railway provisions HTTPS automatically via Let's Encrypt

---

## Environment Variables Reference

### Backend
| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | ✅ | Your Anthropic API key |
| `DATA_DIR` | Optional | Path for SQLite + ChromaDB (default: `/app/data`) |
| `PORT` | Auto | Injected by Railway |

### Frontend
| Variable | Required | Description |
|----------|----------|-------------|
| `VITE_API_URL` | ✅ | Full URL of backend service (no trailing slash) |
| `PORT` | Auto | Injected by Railway |

---

## Local Development (with live backend)

If you want to run the frontend locally pointing at the deployed backend:

```bash
cd frontend
VITE_API_URL=https://insightiq-backend-xxxx.railway.app npm run dev
```

---

## Troubleshooting

**Build fails on `sentence-transformers`**  
→ The model download happens during Docker build. Railway has a 10-minute build timeout.
If it times out, re-trigger the deploy — it'll use Docker layer cache on retry.

**"No data context found" error**  
→ The volume isn't mounted or ChromaDB data was lost. Re-upload your CSV after deploy.

**SSE streaming not working**  
→ Check that your backend's CORS allows the frontend origin. The current config uses `allow_origins=["*"]` which covers all cases. If you add a custom domain, this is already handled.

**Frontend shows blank page**  
→ Open browser DevTools → Console. Usually means `VITE_API_URL` is wrong or the backend isn't running. Double-check the backend URL has no trailing slash.

---

## Render Alternative

If you prefer [Render](https://render.com):

1. Create two **Web Services** (one per service)
2. Set **Docker** as the environment
3. Same env vars as above
4. Render also has a free tier but cold starts take ~30s on free plans

---

## Cost

Railway free tier includes $5/month of usage credit — enough for a portfolio demo
running intermittently. Backend (with the model baked in) is ~800MB image, 
frontend is ~30MB. Typical cost for light demo traffic: **$0–2/month**.
