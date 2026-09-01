"""
NERRO ML — Health Check Endpoints
GET /health         — service health
GET /health/models  — model status
"""

from fastapi import APIRouter

from app.config import NER_TOWNS
from app.schemas.api_models import HealthResponse, ModelHealthResponse

router = APIRouter(prefix="/health", tags=["Health"])

# Injected by main.py
risk_model = None
delay_model = None
road_graph = None


def set_dependencies(risk, delay, graph):
    global risk_model, delay_model, road_graph
    risk_model = risk
    delay_model = delay
    road_graph = graph


@router.get("", response_model=HealthResponse)
def health_check():
    return {
        "status": "ok",
        "service": "NERRO ML Intelligence Engine",
        "version": "1.0.0",
    }


@router.get("/models", response_model=ModelHealthResponse)
def model_health():
    risk_loaded = risk_model is not None and risk_model.model is not None
    delay_loaded = delay_model is not None and delay_model.model is not None

    return {
        "risk_model_loaded": risk_loaded,
        "delay_model_loaded": delay_loaded,
        "risk_model_type": (
            type(risk_model.model).__name__ if risk_loaded else None
        ),
        "delay_model_type": (
            type(delay_model.model).__name__ if delay_loaded else None
        ),
        "towns_count": len(NER_TOWNS),
        "road_segments_count": road_graph.number_of_edges() if road_graph else 0,
    }
