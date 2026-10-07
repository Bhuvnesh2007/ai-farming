"""
main.py
───────
FastAPI application — the HTTP layer that bridges the Streamlit frontend
and the multi-agent backend.

Endpoints:
  POST /api/chat          — Main chat endpoint (text + optional image)
  POST /api/ingest        — Trigger document ingestion into ChromaDB
  GET  /api/weather       — Fetch weather for given lat/lon
  GET  /api/market/{crop} — Fetch mandi price data for a crop
  GET  /health            — Health check
"""

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
import base64
import uvicorn
from loguru import logger

from backend.config import get_settings
from backend.models.schemas import (
    AgentRequest,
    FarmerProfile,
    OrchestratorResponse,
    Language,
    Season,
    SoilType,
)
from backend.agents.orchestrator import orchestrate
from backend.agents.weather_agent import fetch_weather, OFFLINE_WEATHER
from backend.agents.market_agent import load_mandi_data, analyse_trend, _build_mandi_prices

settings = get_settings()

# ── App setup ──────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Smart Farming AI Agent API",
    description=(
        "Multi-agent system for personalised agricultural advice. "
        "Powered by IBM Granite on watsonx.ai."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],    # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request / Response models ─────────────────────────────────────────────────

class ChatRequest(BaseModel):
    query: str
    name: str = "Farmer"
    location: str = "Delhi"
    latitude: float = 28.6139
    longitude: float = 77.2090
    land_size_acres: float = 2.0
    soil_type: str = "loamy"
    current_crop: str = "wheat"
    season: str = "rabi"
    language: str = "en"
    image_base64: Optional[str] = None
    history: list = []


# ── Helpers ────────────────────────────────────────────────────────────────────

def _build_profile(req: ChatRequest) -> FarmerProfile:
    return FarmerProfile(
        name=req.name,
        location=req.location,
        latitude=req.latitude,
        longitude=req.longitude,
        land_size_acres=req.land_size_acres,
        soil_type=SoilType(req.soil_type),
        current_crop=req.current_crop,
        season=Season(req.season),
        language=Language(req.language),
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0", "offline_mode": settings.offline_mode}


@app.post("/api/chat", response_model=OrchestratorResponse)
async def chat(req: ChatRequest):
    """
    Main multi-agent chat endpoint.
    Accepts text query + optional base64 image.
    Returns merged answer from all relevant agents.
    """
    logger.info(f"/api/chat | query='{req.query[:60]}' | crop={req.current_crop}")

    try:
        profile = _build_profile(req)
        agent_req = AgentRequest(
            query=req.query,
            farmer_profile=profile,
            image_base64=req.image_base64,
            language=Language(req.language),
            history=req.history,
        )
        response = orchestrate(agent_req)
        return response
    except Exception as exc:
        logger.error(f"Chat endpoint error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/chat/upload")
async def chat_with_image(
    query: str = Form(...),
    name: str = Form("Farmer"),
    location: str = Form("Delhi"),
    latitude: float = Form(28.6139),
    longitude: float = Form(77.2090),
    land_size_acres: float = Form(2.0),
    soil_type: str = Form("loamy"),
    current_crop: str = Form("wheat"),
    season: str = Form("rabi"),
    language: str = Form("en"),
    image: Optional[UploadFile] = File(None),
):
    """
    Multipart form endpoint for image + query upload from the frontend.
    Encodes the image as base64 and delegates to the main chat logic.
    """
    image_b64 = None
    if image:
        contents = await image.read()
        image_b64 = base64.b64encode(contents).decode("utf-8")

    req = ChatRequest(
        query=query,
        name=name,
        location=location,
        latitude=latitude,
        longitude=longitude,
        land_size_acres=land_size_acres,
        soil_type=soil_type,
        current_crop=current_crop,
        season=season,
        language=language,
        image_base64=image_b64,
    )
    return await chat(req)


@app.get("/api/weather")
async def get_weather(lat: float = 28.6139, lon: float = 77.2090):
    """Return 7-day weather forecast for given coordinates."""
    weather = fetch_weather(lat, lon)
    if weather is None:
        weather = OFFLINE_WEATHER
    return weather.model_dump()


@app.get("/api/market/{crop}")
async def get_market(crop: str):
    """Return mandi price data and trend for a specific crop."""
    df = load_mandi_data(crop)
    if df.empty:
        raise HTTPException(status_code=404, detail=f"No price data for crop: {crop}")

    trend, avg_price, change_pct = analyse_trend(df)
    prices = _build_mandi_prices(df)

    return {
        "crop": crop,
        "trend": trend,
        "avg_modal_price": round(avg_price, 2),
        "change_pct_4wk": change_pct,
        "prices": [p.model_dump() for p in prices],
    }


@app.post("/api/ingest")
async def trigger_ingest():
    """Trigger document ingestion (run after uploading new crop guides)."""
    try:
        from scripts.ingest_docs import ingest_documents
        ingest_documents()
        return {"status": "success", "message": "Documents ingested into ChromaDB"}
    except Exception as exc:
        logger.error(f"Ingest failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host=settings.backend_host,
        port=settings.backend_port,
        reload=True,
        log_level=settings.log_level.lower(),
    )
