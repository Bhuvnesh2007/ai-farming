# IBM Cloud Deployment Guide
## Smart Farming AI Agent — Step-by-Step

---

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| IBM Cloud account | Free Tier OK | Hosting |
| IBM Cloud CLI (`ibmcloud`) | Latest | Deploy commands |
| Docker Desktop | 24.x+ | Build images |
| Python | 3.11+ | Local dev |
| Git | Any | Version control |

---

## Step 1 — Create IBM Cloud Resources

### 1a. watsonx.ai (Granite LLM)

1. Log in at [cloud.ibm.com](https://cloud.ibm.com)
2. Create a **watsonx.ai** service instance (Lite tier is free)
3. Create a new **Project** inside watsonx Studio
4. Copy your **Project ID** from project settings
5. Generate an **API Key**: `Manage → Access → API Keys → Create`
6. Copy both into your `.env` file:
   ```
   WATSONX_API_KEY=your_key_here
   WATSONX_PROJECT_ID=your_project_id
   ```

### 1b. IBM Cloud Container Registry (ICR)

```bash
# Install ICR plugin
ibmcloud plugin install container-registry

# Log in
ibmcloud login --apikey YOUR_API_KEY -r us-south
ibmcloud cr login

# Create a namespace for your images
ibmcloud cr namespace-add smart-farming
```

### 1c. IBM Code Engine (serverless containers)

```bash
ibmcloud plugin install code-engine

# Create a project
ibmcloud ce project create --name smart-farming-project
ibmcloud ce project select --name smart-farming-project
```

---

## Step 2 — Set Up Local Environment

```bash
# Clone / enter the project
cd smart-farming-agent

# Create virtual environment
python -m venv venv
source venv/bin/activate          # Linux/macOS
# venv\Scripts\activate           # Windows

# Install dependencies
pip install -r requirements.txt

# Copy and fill in your credentials
cp .env.example .env
# Edit .env with your WATSONX_API_KEY and WATSONX_PROJECT_ID

# Ingest crop guides into ChromaDB (one time)
python -m scripts.ingest_docs

# Test locally
uvicorn backend.main:app --reload &
streamlit run frontend/app.py
```

Open `http://localhost:8501` — dashboard should load with weather and chat.

---

## Step 3 — Build Docker Images

### Backend (FastAPI)

Create `deployment/Dockerfile.backend`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY scripts/ ./scripts/
COPY .env .env

# Pre-ingest docs into the image
RUN python -m scripts.ingest_docs

EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Frontend (Streamlit)

Create `deployment/Dockerfile.frontend`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir streamlit plotly deep-translator SpeechRecognition requests pandas

COPY frontend/ ./frontend/
EXPOSE 8501
CMD ["streamlit", "run", "frontend/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

### Build & Push

```bash
# Build backend
docker build -f deployment/Dockerfile.backend -t us.icr.io/smart-farming/backend:v1 .
docker push us.icr.io/smart-farming/backend:v1

# Build frontend
docker build -f deployment/Dockerfile.frontend -t us.icr.io/smart-farming/frontend:v1 .
docker push us.icr.io/smart-farming/frontend:v1
```

---

## Step 4 — Deploy to IBM Code Engine

### 4a. Deploy Backend

```bash
ibmcloud ce application create \
  --name farming-backend \
  --image us.icr.io/smart-farming/backend:v1 \
  --port 8000 \
  --cpu 1 \
  --memory 4G \
  --min-scale 1 \
  --max-scale 3 \
  --env WATSONX_API_KEY=your_key \
  --env WATSONX_PROJECT_ID=your_project_id \
  --env WATSONX_URL=https://us-south.ml.cloud.ibm.com \
  --env OFFLINE_MODE=false

# Get the backend URL
ibmcloud ce application get --name farming-backend | grep URL
# Example: https://farming-backend.xxxxxxx.us-south.codeengine.appdomain.cloud
```

### 4b. Deploy Frontend

```bash
# Replace <BACKEND_URL> with the URL from above
ibmcloud ce application create \
  --name farming-frontend \
  --image us.icr.io/smart-farming/frontend:v1 \
  --port 8501 \
  --cpu 0.5 \
  --memory 2G \
  --min-scale 1 \
  --env API_BASE=https://farming-backend.xxxxxxx.us-south.codeengine.appdomain.cloud

# Get the frontend URL
ibmcloud ce application get --name farming-frontend | grep URL
```

> ⚠️ Update `API_BASE` in `frontend/app.py` line 34 to your backend URL before building the image.

---

## Step 5 — Use IBM Secrets (recommended for production)

```bash
# Create a secret for API keys instead of --env flags
ibmcloud ce secret create \
  --name watsonx-secrets \
  --from-literal WATSONX_API_KEY=your_key \
  --from-literal WATSONX_PROJECT_ID=your_project_id

# Reference the secret in the application
ibmcloud ce application update \
  --name farming-backend \
  --env-from-secret watsonx-secrets
```

---

## Step 6 — Custom Domain (optional)

```bash
# Map a custom domain via IBM Cloud Internet Services
ibmcloud ce application update \
  --name farming-frontend \
  --request-timeout 300
```

---

## Step 7 — Monitoring & Logs

```bash
# View live logs
ibmcloud ce application logs --name farming-backend --follow

# View metrics in IBM Cloud Monitoring
# Navigate: IBM Cloud Console → Observability → Monitoring
```

---

## Step 8 — Scaling & Cost

| Service | Free Tier | Paid |
|---------|-----------|------|
| Code Engine | 100K vCPU-s/month free | $0.00002/vCPU-s |
| Container Registry | 0.5 GB free | $0.07/GB |
| watsonx.ai (Granite) | ~$0 with Lite plan | Token-based pricing |
| Open-Meteo Weather | Free (no key needed) | Free |

**Estimated monthly cost for demo traffic (<1000 queries/day): ~$0–5 USD**

---

## Step 9 — Update & Re-deploy

```bash
# After code changes:
docker build -f deployment/Dockerfile.backend -t us.icr.io/smart-farming/backend:v2 .
docker push us.icr.io/smart-farming/backend:v2

ibmcloud ce application update \
  --name farming-backend \
  --image us.icr.io/smart-farming/backend:v2
```

Code Engine performs a zero-downtime rolling update automatically.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `WATSONX_API_KEY` error | Check key at cloud.ibm.com → API Keys |
| ChromaDB empty | Re-run `python -m scripts.ingest_docs` inside container |
| Weather not loading | Open-Meteo is free; check internet access |
| Image push fails | Run `ibmcloud cr login` and check namespace |
| Streamlit blank | Check `API_BASE` env var points to backend URL |

---

*Deployment guide for Smart Farming AI Hackathon Prototype — IBM Cloud, 2024*
