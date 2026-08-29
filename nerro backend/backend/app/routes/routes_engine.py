# ============================================================
# NERRO - Route Engine Routes (routes/routes_engine.py)
# Endpoints      : GET /api/routes, POST /api/routes/find,
#                  GET /api/routes/{id}, POST /api/routes/{id}/reroute
# Purpose        : Safest-route planning - origin/destination, priority
#                  (speed/safety/balanced/economy), waypoints, risk + alternatives.
# TEAM NOTE      : *** ROUTE OPTIMISATION INTEGRATION POINT ***
#                  generate_demo_route returns canned profiles. Replace with real
#                  routing over the PostGIS road graph, costed by risk_engine score
#                  and live weather for production route results.
# ============================================================
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.routes.auth import get_current_user

router = APIRouter(prefix="/api/routes", tags=["Route Engine"])

# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------


class RouteFindRequest(BaseModel):
    origin: str = Field(..., min_length=1, description="Origin location name")
    destination: str = Field(..., min_length=1, description="Destination location name")
    origin_lat: Optional[float] = Field(None, ge=-90, le=90)
    origin_lng: Optional[float] = Field(None, ge=-180, le=180)
    dest_lat: Optional[float] = Field(None, ge=-90, le=90)
    dest_lng: Optional[float] = Field(None, ge=-180, le=180)
    commodity: Optional[str] = Field(None, description="Type of cargo")
    priority: str = Field(default="balanced", pattern="^(speed|safety|balanced|economy)$")
    vehicle_type: str = Field(default="truck")
    avoid_flooded: bool = True
    avoid_restricted: bool = False
    max_risk_score: float = Field(default=0.8, ge=0, le=1)


class RouteWaypoint(BaseModel):
    name: str
    latitude: float
    longitude: float
    road_id: Optional[str] = None
    distance_from_prev_km: float
    cumulative_km: float
    estimated_time_min: float
    risk_score: float
    road_condition: str


class RouteEvaluation(BaseModel):
    distance_km: float
    estimated_time_hrs: float
    overall_risk_score: float
    risk_level: str
    road_condition_score: float
    weather_impact_score: float
    elevation_gain_m: float
    fuel_estimate_liters: float
    reliability_score: float


class RouteResponse(BaseModel):
    id: str
    name: str
    origin: str
    destination: str
    status: str
    evaluation: RouteEvaluation
    waypoints: list[RouteWaypoint]
    weather_summary: dict
    created_at: str


class RouteFindResponse(BaseModel):
    recommended_route: RouteResponse
    alternatives: list[RouteResponse]
    total_options_evaluated: int
    recommendation_reason: str


class RouteListResponse(BaseModel):
    routes: list[RouteResponse]
    total: int


class RerouteRequest(BaseModel):
    reason: str = Field(..., min_length=1)
    current_lat: Optional[float] = None
    current_lng: Optional[float] = None
    avoid_roads: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Demo Data
# ---------------------------------------------------------------------------

_DEMO_ROUTES: list[dict] = [
    {
        "id": "route_001",
        "name": "Guwahati → Tawang (Primary NH-13)",
        "origin": "Guwahati",
        "destination": "Tawang",
        "status": "active",
        "evaluation": {
            "distance_km": 522.0,
            "estimated_time_hrs": 14.5,
            "overall_risk_score": 0.68,
            "risk_level": "medium",
            "road_condition_score": 0.65,
            "weather_impact_score": 0.40,
            "elevation_gain_m": 3200,
            "fuel_estimate_liters": 156,
            "reliability_score": 0.72,
        },
        "waypoints": [
            {"name": "Guwahati", "latitude": 26.1445, "longitude": 91.7362, "road_id": "road_002", "distance_from_prev_km": 0, "cumulative_km": 0, "estimated_time_min": 0, "risk_score": 0.2, "road_condition": "good"},
            {"name": "Bhalukpong", "latitude": 26.8300, "longitude": 92.6300, "road_id": "road_001", "distance_from_prev_km": 155, "cumulative_km": 155, "estimated_time_min": 210, "risk_score": 0.45, "road_condition": "fair"},
            {"name": "Bomdila", "latitude": 27.2500, "longitude": 92.4200, "road_id": "road_001", "distance_from_prev_km": 98, "cumulative_km": 253, "estimated_time_min": 360, "risk_score": 0.65, "road_condition": "fair"},
            {"name": "Sela Pass", "latitude": 27.5800, "longitude": 92.1000, "road_id": "road_001", "distance_from_prev_km": 85, "cumulative_km": 338, "estimated_time_min": 540, "risk_score": 0.82, "road_condition": "poor"},
            {"name": "Tawang", "latitude": 27.5869, "longitude": 91.8593, "road_id": "road_001", "distance_from_prev_km": 184, "cumulative_km": 522, "estimated_time_min": 870, "risk_score": 0.55, "road_condition": "fair"},
        ],
        "weather_summary": {"route_weather": "rainy", "high_risk_segment": "Sela Pass - heavy snow possible", "best_departure": "06:00 AM"},
        "created_at": "2026-01-21T08:00:00Z",
    },
    {
        "id": "route_002",
        "name": "Guwahati → Tawang (Via Kalaktang Alternative)",
        "origin": "Guwahati",
        "destination": "Tawang",
        "status": "active",
        "evaluation": {
            "distance_km": 594.0,
            "estimated_time_hrs": 18.0,
            "overall_risk_score": 0.45,
            "risk_level": "medium",
            "road_condition_score": 0.55,
            "weather_impact_score": 0.30,
            "elevation_gain_m": 2800,
            "fuel_estimate_liters": 178,
            "reliability_score": 0.65,
        },
        "waypoints": [
            {"name": "Guwahati", "latitude": 26.1445, "longitude": 91.7362, "road_id": "road_002", "distance_from_prev_km": 0, "cumulative_km": 0, "estimated_time_min": 0, "risk_score": 0.2, "road_condition": "good"},
            {"name": "Bhalukpong", "latitude": 26.8300, "longitude": 92.6300, "road_id": "road_001", "distance_from_prev_km": 155, "cumulative_km": 155, "estimated_time_min": 210, "risk_score": 0.45, "road_condition": "fair"},
            {"name": "Kalaktang", "latitude": 27.1000, "longitude": 92.2000, "road_id": None, "distance_from_prev_km": 65, "cumulative_km": 220, "estimated_time_min": 360, "risk_score": 0.50, "road_condition": "poor"},
            {"name": "Tawang (via South)", "latitude": 27.5869, "longitude": 91.8593, "road_id": "road_001", "distance_from_prev_km": 374, "cumulative_km": 594, "estimated_time_min": 1080, "risk_score": 0.40, "road_condition": "fair"},
        ],
        "weather_summary": {"route_weather": "overcast", "high_risk_segment": "Kalaktang-Tawang stretch", "best_departure": "05:30 AM"},
        "created_at": "2026-01-21T08:00:00Z",
    },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _risk_level(score: float) -> str:
    if score >= 0.7:
        return "high"
    elif score >= 0.4:
        return "medium"
    return "low"


def _generate_demo_route(origin: str, destination: str, priority: str, commodity: Optional[str]) -> dict:
    is_tawang = "tawang" in destination.lower()
    if is_tawang:
        return _DEMO_ROUTES[0]

    return {
        "id": f"route_{len(_DEMO_ROUTES)+1:03d}",
        "name": f"{origin} → {destination} ({priority.title()})",
        "origin": origin,
        "destination": destination,
        "status": "active",
        "evaluation": {
            "distance_km": 280.0,
            "estimated_time_hrs": 8.5,
            "overall_risk_score": 0.35,
            "risk_level": "low",
            "road_condition_score": 0.70,
            "weather_impact_score": 0.25,
            "elevation_gain_m": 600,
            "fuel_estimate_liters": 84,
            "reliability_score": 0.82,
        },
        "waypoints": [
            {"name": origin, "latitude": 26.1445, "longitude": 91.7362, "road_id": None, "distance_from_prev_km": 0, "cumulative_km": 0, "estimated_time_min": 0, "risk_score": 0.2, "road_condition": "good"},
            {"name": destination, "latitude": 25.9000, "longitude": 93.0000, "road_id": None, "distance_from_prev_km": 280, "cumulative_km": 280, "estimated_time_min": 510, "risk_score": 0.35, "road_condition": "good"},
        ],
        "weather_summary": {"route_weather": "clear", "high_risk_segment": "none", "best_departure": "07:00 AM"},
        "created_at": datetime.utcnow().isoformat() + "Z",
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("", response_model=RouteListResponse)
async def list_routes(
    origin: Optional[str] = Query(None),
    destination: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    routes = list(_DEMO_ROUTES)
    if origin:
        routes = [r for r in routes if origin.lower() in r["origin"].lower()]
    if destination:
        routes = [r for r in routes if destination.lower() in r["destination"].lower()]
    if status_filter:
        routes = [r for r in routes if r["status"] == status_filter]

    return RouteListResponse(routes=[RouteResponse(**r) for r in routes], total=len(routes))


@router.post("/find", response_model=RouteFindResponse)
async def find_safest_route(
    request: RouteFindRequest,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    primary = _generate_demo_route(request.origin, request.destination, request.priority, request.commodity)
    alternative = _DEMO_ROUTES[1] if "tawang" in request.destination.lower() else _generate_demo_route(
        request.origin, request.destination, "safety", request.commodity
    )

    reason = "Balanced route with moderate risk and reasonable travel time."
    if request.priority == "safety":
        reason = "Lowest risk route selected. Extra distance added to avoid high-risk segments."
    elif request.priority == "speed":
        reason = "Fastest route selected. Some higher-risk segments included."
    elif request.priority == "economy":
        reason = "Most fuel-efficient route selected. Balanced risk profile."

    return RouteFindResponse(
        recommended_route=RouteResponse(**primary),
        alternatives=[RouteResponse(**alternative)],
        total_options_evaluated=3,
        recommendation_reason=reason,
    )


@router.get("/{route_id}", response_model=RouteResponse)
async def get_route(route_id: str, db: Session = Depends(get_db), _user: dict = Depends(get_current_user)):
    route = next((r for r in _DEMO_ROUTES if r["id"] == route_id), None)
    if not route:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Route {route_id} not found")
    return RouteResponse(**route)


@router.post("/{route_id}/reroute", response_model=RouteFindResponse)
async def reroute(
    route_id: str,
    request: RerouteRequest,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    route = next((r for r in _DEMO_ROUTES if r["id"] == route_id), None)
    if not route:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Route {route_id} not found")

    new_route = _generate_demo_route(route["origin"], route["destination"], "safety", None)
    new_route["name"] = f"{route['origin']} → {route['destination']} (Re-routed: {request.reason})"
    new_route["id"] = f"route_{len(_DEMO_ROUTES)+3:03d}"

    return RouteFindResponse(
        recommended_route=RouteResponse(**new_route),
        alternatives=[RouteResponse(**route)],
        total_options_evaluated=2,
        recommendation_reason=f"Re-routed due to: {request.reason}. Alternative avoids {', '.join(request.avoid_roads) if request.avoid_roads else 'affected segments'}.",
    )
