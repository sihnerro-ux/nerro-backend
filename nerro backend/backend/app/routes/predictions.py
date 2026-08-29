# ============================================================
# NERRO - AI Predictions Routes (routes/predictions.py)
# Endpoints      : GET /api/predictions, /api/predictions/status,
#                  POST /api/predictions/predict
# Purpose        : Risk predictions for any lat/lng (flood/landslide/route-safety).
# TEAM NOTE      : *** ML MODEL INTEGRATION POINT ***
#                  request_prediction() currently generates a heuristic score.
#                  Call your trained model here (e.g. via RiskFusionEngine or the
#                  new scorer) and return the same PredictionResult schema so the
#                  frontend AI page needs zero changes. /status reports the model
#                  wire-up state shown in Settings.
# ============================================================
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.routes.auth import get_current_user

router = APIRouter(prefix="/api/predictions", tags=["AI Predictions"])

# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------


class PredictionRequest(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    location_name: Optional[str] = None
    prediction_type: str = Field(default="risk_assessment", pattern="^(risk_assessment|weather_impact|landslide|flooding|route_safety|overall)$")
    time_horizon_hrs: int = Field(default=24, ge=1, le=168)
    include_factors: bool = True


class FactorBreakdown(BaseModel):
    factor: str
    contribution: float
    impact: str
    weight: float


class PredictionResult(BaseModel):
    id: str
    location_name: str
    latitude: float
    longitude: float
    prediction_type: str
    risk_score: float
    risk_level: str
    confidence: float
    time_horizon_hrs: int
    factors: list[FactorBreakdown]
    recommendation: str
    created_at: str


class PredictionListResponse(BaseModel):
    predictions: list[PredictionResult]
    total: int


class ModelStatus(BaseModel):
    status: str
    model_name: str
    model_version: str
    last_trained: Optional[str] = None
    accuracy: Optional[float] = None
    features_count: Optional[int] = None
    training_samples: Optional[int] = None
    integration_note: Optional[str] = None


class PredictionResponse(BaseModel):
    prediction: PredictionResult
    model_status: ModelStatus


# ---------------------------------------------------------------------------
# Demo / Model-Status Data
# ---------------------------------------------------------------------------

_MODEL_STATUS: dict = {
    "status": "READY_FOR_INTEGRATION",
    "model_name": "NERRO Risk Prediction Engine",
    "model_version": "0.1.0-demo",
    "last_trained": None,
    "accuracy": None,
    "features_count": 12,
    "training_samples": None,
    "integration_note": (
        "ML model not yet connected. Showing heuristic-based demo predictions. "
        "Integrate with trained PyTorch/TF model via /api/predictions/integrate endpoint."
    ),
}

_DEMO_PREDICTIONS: list[dict] = [
    {
        "id": "pred_001",
        "location_name": "Sela Pass, Arunachal Pradesh",
        "latitude": 27.58,
        "longitude": 92.10,
        "prediction_type": "landslide",
        "risk_score": 0.82,
        "risk_level": "high",
        "confidence": 0.78,
        "time_horizon_hrs": 24,
        "factors": [
            {"factor": "Slope angle (42°)", "contribution": 0.28, "impact": "increases_risk", "weight": 0.25},
            {"factor": "Rainfall (45mm in 24h)", "contribution": 0.25, "impact": "increases_risk", "weight": 0.30},
            {"factor": "Soil saturation (87%)", "contribution": 0.18, "impact": "increases_risk", "weight": 0.20},
            {"factor": "Vegetation cover (moderate)", "contribution": -0.08, "impact": "decreases_risk", "weight": 0.10},
            {"factor": "Historical incidents (3 in 5yr)", "contribution": 0.12, "impact": "increases_risk", "weight": 0.15},
        ],
        "recommendation": "High landslide risk. Avoid travel between 2PM-8PM. Monitor IMD alerts. Pre-position emergency supplies at Bomdila.",
        "created_at": "2026-01-21T08:00:00Z",
    },
    {
        "id": "pred_002",
        "location_name": "Brahmaputra Crossing, Assam",
        "latitude": 26.75,
        "longitude": 92.15,
        "prediction_type": "flooding",
        "risk_score": 0.65,
        "risk_level": "medium",
        "confidence": 0.72,
        "time_horizon_hrs": 48,
        "factors": [
            {"factor": "River level (above danger)", "contribution": 0.30, "impact": "increases_risk", "weight": 0.35},
            {"factor": "Upstream rainfall forecast (30mm)", "contribution": 0.15, "impact": "increases_risk", "weight": 0.25},
            {"factor": "Embankment condition (fair)", "contribution": 0.10, "impact": "increases_risk", "weight": 0.20},
            {"factor": "Tidal influence (low)", "contribution": -0.05, "impact": "decreases_risk", "weight": 0.10},
            {"factor": "Drainage capacity (60%)", "contribution": 0.10, "impact": "increases_risk", "weight": 0.10},
        ],
        "recommendation": "Moderate flood risk. Keep alternative elevated routes ready. Alert downstream communities. Monitor CWC water levels.",
        "created_at": "2026-01-21T08:00:00Z",
    },
    {
        "id": "pred_003",
        "location_name": "Shillong Plateau, Meghalaya",
        "latitude": 25.58,
        "longitude": 91.89,
        "prediction_type": "route_safety",
        "risk_score": 0.32,
        "risk_level": "low",
        "confidence": 0.85,
        "time_horizon_hrs": 24,
        "factors": [
            {"factor": "Road condition (good)", "contribution": -0.15, "impact": "decreases_risk", "weight": 0.30},
            {"factor": "Weather forecast (clear)", "contribution": -0.12, "impact": "decreases_risk", "weight": 0.25},
            {"factor": "Traffic density (moderate)", "contribution": 0.08, "impact": "increases_risk", "weight": 0.15},
            {"factor": "Visibility (good)", "contribution": -0.08, "impact": "decreases_risk", "weight": 0.15},
            {"factor": "Construction zones (1)", "contribution": 0.07, "impact": "increases_risk", "weight": 0.15},
        ],
        "recommendation": "Good conditions for travel. Minor delays possible near construction zone at Mawkdok. Normal speed recommended.",
        "created_at": "2026-01-21T08:00:00Z",
    },
]


def _risk_level(score: float) -> str:
    if score >= 0.7:
        return "high"
    elif score >= 0.4:
        return "medium"
    return "low"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/status", response_model=ModelStatus)
async def get_model_status(_user: dict = Depends(get_current_user)):
    return ModelStatus(**_MODEL_STATUS)


@router.get("", response_model=PredictionListResponse)
async def list_predictions(
    prediction_type: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    min_risk: Optional[float] = Query(None, ge=0, le=1),
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    predictions = list(_DEMO_PREDICTIONS)
    if prediction_type:
        predictions = [p for p in predictions if p["prediction_type"] == prediction_type]
    if location:
        predictions = [p for p in predictions if location.lower() in p["location_name"].lower()]
    if min_risk is not None:
        predictions = [p for p in predictions if p["risk_score"] >= min_risk]

    return PredictionListResponse(
        predictions=[PredictionResult(**p) for p in predictions],
        total=len(predictions),
    )


@router.post("/predict", response_model=PredictionResponse)
async def request_prediction(
    request: PredictionRequest,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    risk_score = min(0.95, max(0.05, abs(hash(f"{request.latitude}{request.longitude}{request.time_horizon_hrs}") % 100) / 100))
    factors = [
        {"factor": "Location elevation", "contribution": 0.15, "impact": "increases_risk", "weight": 0.20},
        {"factor": "Recent weather patterns", "contribution": 0.10, "impact": "increases_risk", "weight": 0.25},
        {"factor": "Road infrastructure age", "contribution": 0.08, "impact": "increases_risk", "weight": 0.15},
        {"factor": "Vegetation and soil", "contribution": -0.05, "impact": "decreases_risk", "weight": 0.15},
        {"factor": "Historical data", "contribution": 0.07, "impact": "increases_risk", "weight": 0.25},
    ]

    prediction = PredictionResult(
        id=f"pred_{len(_DEMO_PREDICTIONS)+1:03d}",
        location_name=request.location_name or f"Location ({request.latitude}, {request.longitude})",
        latitude=request.latitude,
        longitude=request.longitude,
        prediction_type=request.prediction_type,
        risk_score=risk_score,
        risk_level=_risk_level(risk_score),
        confidence=0.75,
        time_horizon_hrs=request.time_horizon_hrs,
        factors=[FactorBreakdown(**f) for f in factors],
        recommendation="Heuristic prediction. Integrate ML model for accurate predictions.",
        created_at=datetime.utcnow().isoformat() + "Z",
    )

    return PredictionResponse(
        prediction=prediction,
        model_status=ModelStatus(**_MODEL_STATUS),
    )
