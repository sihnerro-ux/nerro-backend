# ============================================================
# NERRO - Roads Routes (routes/roads.py)
# Endpoints      : GET /api/roads, GET /api/roads/{id},
#                  PUT /api/roads/{id}/status, GET /api/roads/{id}/intelligence
# Purpose        : Road catalog, status updates and full per-road intelligence
#                  (weather, incidents, risk prediction, alternatives).
# TEAM NOTE      : *_DEMO_ROADS is the fallback dataset. Replace list/filter logic
#                  with the Road DB table + PostGIS for live road network data.
# ============================================================
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.routes.auth import get_current_user

router = APIRouter(prefix="/api/roads", tags=["Roads"])

# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------


class RoadStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(open|closed|restricted|under_repair|flooding)$")
    reason: Optional[str] = None
    reported_by: Optional[str] = None


class WeatherInfo(BaseModel):
    condition: str
    temperature_c: float
    humidity_percent: float
    precipitation_mm: float
    wind_speed_kmh: float
    visibility_km: float
    alert: Optional[str] = None


class IncidentBrief(BaseModel):
    id: str
    type: str
    severity: str
    description: str
    reported_at: str


class RoadIntelligence(BaseModel):
    road_id: str
    road_name: str
    current_status: str
    risk_score: float
    risk_level: str
    weather: WeatherInfo
    recent_incidents: list[IncidentBrief]
    prediction: dict
    alternative_routes: list[dict]
    last_updated: str


class RoadResponse(BaseModel):
    id: str
    name: str
    state: str
    district: str
    status: str
    distance_km: float
    start_point: str
    end_point: str
    road_type: str
    last_maintained: Optional[str] = None
    risk_score: float
    elevation_m: Optional[float] = None
    coordinates: dict


class RoadListResponse(BaseModel):
    roads: list[RoadResponse]
    total: int
    filters_applied: dict


# ---------------------------------------------------------------------------
# Demo Data
# ---------------------------------------------------------------------------

_DEMO_ROADS: list[dict] = [
    {
        "id": "road_001",
        "name": "NH-13 (Tawang Highway)",
        "state": "Arunachal Pradesh",
        "district": "Tawang",
        "status": "open",
        "distance_km": 327.0,
        "start_point": "Tezpur",
        "end_point": "Tawang",
        "road_type": "national_highway",
        "last_maintained": "2025-10-15",
        "risk_score": 0.72,
        "elevation_m": 3500,
        "coordinates": {"start": {"lat": 26.6528, "lng": 92.7926}, "end": {"lat": 27.5869, "lng": 91.8593}},
    },
    {
        "id": "road_002",
        "name": "NH-37 (Assam Trunk Road)",
        "state": "Assam",
        "district": "Kamrup Metro",
        "status": "open",
        "distance_km": 580.0,
        "start_point": "Dibrugarh",
        "end_point": "Guwahati",
        "road_type": "national_highway",
        "last_maintained": "2025-12-01",
        "risk_score": 0.35,
        "elevation_m": 55,
        "coordinates": {"start": {"lat": 27.4839, "lng": 94.8982}, "end": {"lat": 26.1445, "lng": 91.7362}},
    },
    {
        "id": "road_003",
        "name": "Imphal-Dimapur Road",
        "state": "Manipur",
        "district": "Imphal West",
        "status": "restricted",
        "distance_km": 215.0,
        "start_point": "Imphal",
        "end_point": "Dimapur",
        "road_type": "national_highway",
        "last_maintained": "2025-09-20",
        "risk_score": 0.61,
        "elevation_m": 1200,
        "coordinates": {"start": {"lat": 24.8170, "lng": 93.9368}, "end": {"lat": 25.9171, "lng": 93.7264}},
    },
    {
        "id": "road_004",
        "name": "Shillong-Cherrapunji Road",
        "state": "Meghalaya",
        "district": "East Khasi Hills",
        "status": "open",
        "distance_km": 55.0,
        "start_point": "Shillong",
        "end_point": "Cherrapunji",
        "road_type": "state_highway",
        "last_maintained": "2025-11-10",
        "risk_score": 0.48,
        "elevation_m": 1484,
        "coordinates": {"start": {"lat": 25.5788, "lng": 91.8933}, "end": {"lat": 25.2975, "lng": 91.7000}},
    },
    {
        "id": "road_005",
        "name": "Aizawl-Lunglei Road",
        "state": "Mizoram",
        "district": "Aizawl",
        "status": "flooding",
        "distance_km": 170.0,
        "start_point": "Aizawl",
        "end_point": "Lunglei",
        "road_type": "state_highway",
        "last_maintained": "2025-08-25",
        "risk_score": 0.83,
        "elevation_m": 850,
        "coordinates": {"start": {"lat": 23.7271, "lng": 92.7176}, "end": {"lat": 22.8092, "lng": 92.7378}},
    },
    {
        "id": "road_006",
        "name": "Kohima-Mokokchung Road",
        "state": "Nagaland",
        "district": "Kohima",
        "status": "open",
        "distance_km": 150.0,
        "start_point": "Kohima",
        "end_point": "Mokokchung",
        "road_type": "state_highway",
        "last_maintained": "2025-10-05",
        "risk_score": 0.55,
        "elevation_m": 1800,
        "coordinates": {"start": {"lat": 25.6586, "lng": 94.1086}, "end": {"lat": 26.3274, "lng": 94.5267}},
    },
    {
        "id": "road_007",
        "name": "Gangtok-Nathula Road",
        "state": "Sikkim",
        "district": "East Sikkim",
        "status": "restricted",
        "distance_km": 56.0,
        "start_point": "Gangtok",
        "end_point": "Nathula Pass",
        "road_type": "strategic",
        "last_maintained": "2025-12-20",
        "risk_score": 0.78,
        "elevation_m": 4310,
        "coordinates": {"start": {"lat": 27.3389, "lng": 88.6065}, "end": {"lat": 27.3944, "lng": 88.6000}},
    },
    {
        "id": "road_008",
        "name": "Agartala-Udaipur Road",
        "state": "Tripura",
        "district": "West Tripura",
        "status": "open",
        "distance_km": 78.0,
        "start_point": "Agartala",
        "end_point": "Udaipur",
        "road_type": "state_highway",
        "last_maintained": "2025-11-28",
        "risk_score": 0.30,
        "elevation_m": 35,
        "coordinates": {"start": {"lat": 23.8315, "lng": 91.2868}, "end": {"lat": 23.5300, "lng": 91.4800}},
    },
]

_DEMO_WEATHER: WeatherInfo = WeatherInfo(
    condition="Heavy Rain",
    temperature_c=18.5,
    humidity_percent=92.0,
    precipitation_mm=45.2,
    wind_speed_kmh=35.0,
    visibility_km=2.1,
    alert="Flash flood warning for Tawang district",
)

_DEMO_INCIDENTS: list[dict] = [
    {"id": "inc_001", "type": "landslide", "severity": "high", "description": "Major landslide near Sela Pass blocking NH-13", "reported_at": "2026-01-20T14:30:00Z"},
    {"id": "inc_002", "type": "flooding", "severity": "medium", "description": "Waterlogging at Bhalukpong bridge approach road", "reported_at": "2026-01-19T08:15:00Z"},
]


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _risk_level(score: float) -> str:
    if score >= 0.7:
        return "high"
    elif score >= 0.4:
        return "medium"
    return "low"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("", response_model=RoadListResponse)
async def list_roads(
    state: Optional[str] = Query(None),
    district: Optional[str] = Query(None),
    road_status: Optional[str] = Query(None, alias="status"),
    min_risk: Optional[float] = Query(None, ge=0, le=1),
    max_risk: Optional[float] = Query(None, ge=0, le=1),
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    filters_applied = {}
    roads = list(_DEMO_ROADS)

    if state:
        roads = [r for r in roads if r["state"].lower() == state.lower()]
        filters_applied["state"] = state
    if district:
        roads = [r for r in roads if r["district"].lower() == district.lower()]
        filters_applied["district"] = district
    if road_status:
        roads = [r for r in roads if r["status"] == road_status]
        filters_applied["status"] = road_status
    if min_risk is not None:
        roads = [r for r in roads if r["risk_score"] >= min_risk]
        filters_applied["min_risk"] = min_risk
    if max_risk is not None:
        roads = [r for r in roads if r["risk_score"] <= max_risk]
        filters_applied["max_risk"] = max_risk

    return RoadListResponse(
        roads=[RoadResponse(**r) for r in roads],
        total=len(roads),
        filters_applied=filters_applied,
    )


@router.get("/{road_id}", response_model=RoadResponse)
async def get_road(road_id: str, db: Session = Depends(get_db), _user: dict = Depends(get_current_user)):
    road = next((r for r in _DEMO_ROADS if r["id"] == road_id), None)
    if not road:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Road {road_id} not found")
    return RoadResponse(**road)


@router.put("/{road_id}/status", response_model=RoadResponse)
async def update_road_status(
    road_id: str,
    update: RoadStatusUpdate,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    road = next((r for r in _DEMO_ROADS if r["id"] == road_id), None)
    if not road:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Road {road_id} not found")
    road["status"] = update.status
    return RoadResponse(**road)


@router.get("/{road_id}/intelligence", response_model=RoadIntelligence)
async def get_road_intelligence(road_id: str, db: Session = Depends(get_db), _user: dict = Depends(get_current_user)):
    road = next((r for r in _DEMO_ROADS if r["id"] == road_id), None)
    if not road:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Road {road_id} not found")

    return RoadIntelligence(
        road_id=road["id"],
        road_name=road["name"],
        current_status=road["status"],
        risk_score=road["risk_score"],
        risk_level=_risk_level(road["risk_score"]),
        weather=_DEMO_WEATHER,
        recent_incidents=[IncidentBrief(**i) for i in _DEMO_INCIDENTS],
        prediction={
            "next_24h_risk": min(road["risk_score"] + 0.12, 1.0),
            "next_48h_risk": min(road["risk_score"] + 0.05, 1.0),
            "clearance_probability": 0.65,
            "recommended_action": "Monitor conditions; prepare alternate route via Bhalukpong",
            "confidence": 0.78,
        },
        alternative_routes=[
            {"name": "Via Bomdila", "detour_km": 45, "extra_time_hrs": 2.5, "risk_reduction": 0.15},
            {"name": "Via Kalaktang", "detour_km": 72, "extra_time_hrs": 4.0, "risk_reduction": 0.30},
        ],
        last_updated=datetime.utcnow().isoformat() + "Z",
    )
