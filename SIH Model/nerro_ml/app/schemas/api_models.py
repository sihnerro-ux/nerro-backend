"""
NERRO ML — Pydantic API Models (Request / Response schemas)
"""

from typing import Optional
from pydantic import BaseModel, Field


# ── Risk Prediction ───────────────────────────────────────────────

class RiskPredictionRequest(BaseModel):
    route_id: str = Field(..., description="Unique route/segment identifier")
    rainfall_mm: float = Field(0, ge=0, le=1000)
    slope_deg: float = Field(0, ge=0, le=90)
    elevation_m: float = Field(0, ge=0, le=9000)
    past_incident_count: int = Field(0, ge=0)
    is_monsoon: bool = Field(False)
    weather_severity: int = Field(0, ge=0, le=5)
    road_condition: int = Field(1, ge=1, le=3, description="1=good, 2=fair, 3=poor")
    traffic_density: float = Field(0.3, ge=0, le=1)


class RiskPredictionResponse(BaseModel):
    route_id: str
    risk_score: float
    risk_level: str
    predicted_delay_minutes: float
    estimated_travel_minutes: float
    recommended_action: str
    action_label: str
    alternate_route: Optional[str] = None


# ── Delay Prediction ──────────────────────────────────────────────

class DelayPredictionRequest(BaseModel):
    route_id: str = Field(..., description="Unique route/segment identifier")
    distance_km: float = Field(..., gt=0)
    traffic_density: float = Field(0.3, ge=0, le=1)
    rainfall_mm: float = Field(0, ge=0, le=1000)
    road_condition: int = Field(1, ge=1, le=3)
    historical_avg_minutes: float = Field(30, ge=0)
    active_incidents: int = Field(0, ge=0)


class DelayPredictionResponse(BaseModel):
    route_id: str
    predicted_delay_minutes: float
    estimated_travel_minutes: float


# ── Batch Prediction ──────────────────────────────────────────────

class BatchRiskRequest(BaseModel):
    segments: list[RiskPredictionRequest]


class BatchRiskResponse(BaseModel):
    predictions: list[RiskPredictionResponse]


# ── Route Optimization ────────────────────────────────────────────

class RouteOptimizeRequest(BaseModel):
    origin: str = Field(..., description="Starting town name")
    destination: str = Field(..., description="Target town name")
    algorithm: str = Field("astar", description="dijkstra or astar")
    find_alternate: bool = Field(False, description="Also find an alternate route")


class RouteSegment(BaseModel):
    from_town: str = Field(..., alias="from")
    to_town: str = Field(..., alias="to")
    distance_km: float
    risk_score: float
    predicted_delay: float
    is_blocked: bool
    cost: float

    model_config = {"populate_by_name": True}


class RouteOptimizeResponse(BaseModel):
    origin: str
    destination: str
    algorithm: str
    path: list[str]
    total_distance_km: float
    total_delay_minutes: float
    estimated_travel_minutes: float
    total_cost: float
    max_risk_score: float
    has_blocked_segments: bool
    num_stops: int
    segments: list[dict]
    alternate_route: Optional[dict] = None


# ── Network Status ────────────────────────────────────────────────

class NetworkSegment(BaseModel):
    from_town: str = Field(..., alias="from")
    to_town: str = Field(..., alias="to")
    from_lat: float
    from_lon: float
    to_lat: float
    to_lon: float
    distance_km: float
    road_type: int
    risk_score: float
    risk_color: str
    predicted_delay: float
    is_blocked: bool
    cost: float

    model_config = {"populate_by_name": True}


class NetworkStatusResponse(BaseModel):
    total_segments: int
    blocked_count: int
    high_risk_count: int
    segments: list[dict]


# ── Health ────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class ModelHealthResponse(BaseModel):
    risk_model_loaded: bool
    delay_model_loaded: bool
    risk_model_type: Optional[str] = None
    delay_model_type: Optional[str] = None
    towns_count: int
    road_segments_count: int
