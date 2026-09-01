"""
NERRO ML — Prediction API Endpoints
POST /predict/risk   — single route risk prediction
POST /predict/delay  — single delay prediction
POST /predict/batch  — batch risk prediction for map coloring
GET  /predict/town/{town_name} — live risk for an NER town
"""

from fastapi import APIRouter, HTTPException

from app.config import NER_TOWNS
from app.data.collector import get_current_weather, weather_code_to_severity
from app.data.preprocessor import (
    preprocess_delay_features,
    preprocess_risk_features,
    preprocess_risk_batch,
)
from app.models.action_engine import build_full_prediction
from app.schemas.api_models import (
    BatchRiskRequest,
    BatchRiskResponse,
    DelayPredictionRequest,
    DelayPredictionResponse,
    RiskPredictionRequest,
    RiskPredictionResponse,
)

router = APIRouter(prefix="/predict", tags=["Predictions"])

# These will be injected by main.py at startup
risk_model = None
delay_model = None


def set_models(risk, delay):
    global risk_model, delay_model
    risk_model = risk
    delay_model = delay


# ── POST /predict/risk ────────────────────────────────────────────

@router.post("/risk", response_model=RiskPredictionResponse)
def predict_risk(req: RiskPredictionRequest):
    """Predict disruption risk for a single route segment."""
    if risk_model is None or delay_model is None:
        raise HTTPException(503, "Models not loaded yet")

    features_risk = preprocess_risk_features(req.model_dump())
    risk_result = risk_model.predict_risk(features_risk)[0]

    features_delay = preprocess_delay_features({
        "distance_km": 50,  # default segment length
        "traffic_density": req.traffic_density,
        "rainfall_mm": req.rainfall_mm,
        "road_condition": req.road_condition,
        "historical_avg_minutes": 60,
        "active_incidents": req.past_incident_count,
    })
    delay_result = delay_model.predict_delay(features_delay)[0]

    response = build_full_prediction(
        route_id=req.route_id,
        risk_score=risk_result["risk_score"],
        risk_level=risk_result["risk_level"],
        predicted_delay_minutes=delay_result["predicted_delay_minutes"],
        estimated_travel_minutes=delay_result["estimated_travel_minutes"],
        active_incidents=req.past_incident_count,
    )
    return response


# ── POST /predict/delay ───────────────────────────────────────────

@router.post("/delay", response_model=DelayPredictionResponse)
def predict_delay(req: DelayPredictionRequest):
    """Predict travel delay for a route segment."""
    if delay_model is None:
        raise HTTPException(503, "Delay model not loaded yet")

    features = preprocess_delay_features(req.model_dump())
    result = delay_model.predict_delay(features)[0]

    return {
        "route_id": req.route_id,
        "predicted_delay_minutes": result["predicted_delay_minutes"],
        "estimated_travel_minutes": result["estimated_travel_minutes"],
    }


# ── POST /predict/batch ───────────────────────────────────────────

@router.post("/batch", response_model=BatchRiskResponse)
def predict_batch(req: BatchRiskRequest):
    """Batch predict risk for multiple segments (for GIS map coloring)."""
    if risk_model is None or delay_model is None:
        raise HTTPException(503, "Models not loaded yet")

    predictions = []
    for seg in req.segments:
        features_risk = preprocess_risk_features(seg.model_dump())
        risk_result = risk_model.predict_risk(features_risk)[0]

        features_delay = preprocess_delay_features({
            "distance_km": 50,
            "traffic_density": seg.traffic_density,
            "rainfall_mm": seg.rainfall_mm,
            "road_condition": seg.road_condition,
            "historical_avg_minutes": 60,
            "active_incidents": seg.past_incident_count,
        })
        delay_result = delay_model.predict_delay(features_delay)[0]

        pred = build_full_prediction(
            route_id=seg.route_id,
            risk_score=risk_result["risk_score"],
            risk_level=risk_result["risk_level"],
            predicted_delay_minutes=delay_result["predicted_delay_minutes"],
            estimated_travel_minutes=delay_result["estimated_travel_minutes"],
            active_incidents=seg.past_incident_count,
        )
        predictions.append(pred)

    return {"predictions": predictions}


# ── GET /predict/town/{town_name} ─────────────────────────────────

@router.get("/town/{town_name}", response_model=RiskPredictionResponse)
def predict_town_risk(town_name: str):
    """Get live risk assessment for an NER town using real-time weather."""
    if risk_model is None or delay_model is None:
        raise HTTPException(503, "Models not loaded yet")

    if town_name not in NER_TOWNS:
        raise HTTPException(404, f"Town '{town_name}' not found in NER database")

    lat, lon = NER_TOWNS[town_name]

    # Fetch live weather
    try:
        weather = get_current_weather(lat, lon)
    except Exception:
        weather = {"precipitation_mm": 0, "weather_code": 0}

    severity = weather_code_to_severity(weather.get("weather_code", 0))

    features_risk = preprocess_risk_features({
        "rainfall_mm": weather.get("precipitation_mm", 0),
        "slope_deg": 15,            # average for NER hilly terrain
        "elevation_m": 500,         # default
        "past_incident_count": 1,   # assume average
        "is_monsoon": 1,            # assume monsoon for safety
        "weather_severity": severity,
        "road_condition": 2,        # fair
        "traffic_density": 0.4,
    })
    risk_result = risk_model.predict_risk(features_risk)[0]

    features_delay = preprocess_delay_features({
        "distance_km": 50,
        "traffic_density": 0.4,
        "rainfall_mm": weather.get("precipitation_mm", 0),
        "road_condition": 2,
        "historical_avg_minutes": 60,
        "active_incidents": 1,
    })
    delay_result = delay_model.predict_delay(features_delay)[0]

    response = build_full_prediction(
        route_id=f"TOWN_{town_name.upper()}",
        risk_score=risk_result["risk_score"],
        risk_level=risk_result["risk_level"],
        predicted_delay_minutes=delay_result["predicted_delay_minutes"],
        estimated_travel_minutes=delay_result["estimated_travel_minutes"],
    )
    return response
