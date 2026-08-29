# ============================================================
# NERRO - Emergency Routes (routes/emergency.py)
# Endpoints      : GET /api/emergency/status, POST /activate, POST /deactivate,
#                  GET /accessible-routes, /critical-deliveries, /isolated-regions
# Purpose        : Emergency-mode control: toggle state, route accessibility,
#                  priority deliveries and isolated regions needing aid.
# TEAM NOTE      : Emergency state is in-memory (_emergency_state). Pull live data
#                  from Incident/Route/Delivery tables + WebSocket during operations.
# ============================================================
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.routes.auth import get_current_user

router = APIRouter(prefix="/api/emergency", tags=["Emergency"])

# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------


class EmergencyActivateRequest(BaseModel):
    reason: str = Field(..., min_length=1)
    severity: str = Field(..., pattern="^(elevated|severe|extreme)$")
    affected_states: list[str] = Field(default_factory=list)
    affected_districts: list[str] = Field(default_factory=list)
    activated_by: Optional[str] = None


class EmergencyStatus(BaseModel):
    is_active: bool
    severity: Optional[str] = None
    reason: Optional[str] = None
    activated_at: Optional[str] = None
    activated_by: Optional[str] = None
    affected_states: list[str] = Field(default_factory=list)
    affected_districts: list[str] = Field(default_factory=list)
    active_deliveries: int = 0
    vehicles_deployed: int = 0
    incidents_active: int = 0


class AccessibleRoute(BaseModel):
    road_id: str
    road_name: str
    state: str
    district: str
    status: str
    risk_score: float
    accessible: bool
    reason: str
    current_weather: str


class CriticalDelivery(BaseModel):
    id: str
    description: str
    origin: str
    destination: str
    vehicle_id: Optional[str] = None
    priority: str
    status: str
    eta_hours: Optional[float] = None
    commodities: list[str]


class IsolatedRegion(BaseModel):
    region_name: str
    state: str
    district: str
    population: int
    accessible_roads: int
    blocked_roads: list[str]
    last_supply_date: Optional[str] = None
    severity: str
    alternative_access: str


class AccessibleRoutesResponse(BaseModel):
    routes: list[AccessibleRoute]
    total_accessible: int
    total_blocked: int


class CriticalDeliveriesResponse(BaseModel):
    deliveries: list[CriticalDelivery]
    total: int


class IsolatedRegionsResponse(BaseModel):
    regions: list[IsolatedRegion]
    total: int


# ---------------------------------------------------------------------------
# In-memory state
# ---------------------------------------------------------------------------

_emergency_state: dict = {
    "is_active": False,
    "severity": None,
    "reason": None,
    "activated_at": None,
    "activated_by": None,
    "affected_states": [],
    "affected_districts": [],
}


# ---------------------------------------------------------------------------
# Demo Data
# ---------------------------------------------------------------------------

_DEMO_ACCESSIBLE_ROUTES: list[dict] = [
    {"road_id": "road_001", "road_name": "NH-13 (Tawang Highway)", "state": "Arunachal Pradesh", "district": "Tawang", "status": "open", "risk_score": 0.72, "accessible": True, "reason": "Passable with caution. Sela Pass section slippery.", "current_weather": "Heavy rain"},
    {"road_id": "road_002", "road_name": "NH-37 (Assam Trunk Road)", "state": "Assam", "district": "Kamrup Metro", "status": "open", "risk_score": 0.35, "accessible": True, "reason": "Clear. Normal traffic flow.", "current_weather": "Overcast"},
    {"road_id": "road_003", "road_name": "Imphal-Dimapur Road", "state": "Manipur", "district": "Imphal West", "status": "restricted", "risk_score": 0.61, "accessible": True, "reason": "Restricted to essential vehicles only. Pothole section at km 87.", "current_weather": "Light rain"},
    {"road_id": "road_004", "road_name": "Shillong-Cherrapunji Road", "state": "Meghalaya", "district": "East Khasi Hills", "status": "open", "risk_score": 0.48, "accessible": True, "reason": "Good condition. Bridge restriction in effect.", "current_weather": "Cloudy"},
    {"road_id": "road_005", "road_name": "Aizawl-Lunglei Road", "state": "Mizoram", "district": "Aizawl", "status": "flooding", "risk_score": 0.83, "accessible": False, "reason": "Road flooded at Tuivawl. 300m submerged. impassable.", "current_weather": "Heavy rain"},
    {"road_id": "road_007", "road_name": "Gangtok-Nathula Road", "state": "Sikkim", "district": "East Sikkim", "status": "restricted", "risk_score": 0.78, "accessible": False, "reason": "Closed for civilian traffic. Military use only during emergency.", "current_weather": "Snow"},
]

_DEMO_CRITICAL_DELIVERIES: list[dict] = [
    {
        "id": "del_001",
        "description": "Emergency medicines to Tawang PHC",
        "origin": "Guwahati",
        "destination": "Tawang Primary Health Centre",
        "vehicle_id": "veh_001",
        "priority": "critical",
        "status": "in_transit",
        "eta_hours": 6.5,
        "commodities": ["Insulin", "Antibiotics", "ORS packets", "First-aid kits"],
    },
    {
        "id": "del_002",
        "description": "Food supplies to flood-affected Udalguri",
        "origin": "Tezpur",
        "destination": "Udalguri Relief Camp",
        "vehicle_id": None,
        "priority": "high",
        "status": "scheduled",
        "eta_hours": None,
        "commodities": ["Rice (500kg)", "Dal (200kg)", "Cooking oil", "Drinking water"],
    },
    {
        "id": "del_003",
        "description": "Medical team transport to Mokokchung",
        "origin": "Kohima",
        "destination": "Mokokchung District Hospital",
        "vehicle_id": "veh_005",
        "priority": "high",
        "status": "in_transit",
        "eta_hours": 3.0,
        "commodities": ["Medical team (4 doctors)", "Surgical equipment", "Emergency drugs"],
    },
]

_DEMO_ISOLATED_REGIONS: list[dict] = [
    {
        "region_name": "Upper Tawang Sub-division",
        "state": "Arunachal Pradesh",
        "district": "Tawang",
        "population": 12000,
        "accessible_roads": 0,
        "blocked_roads": ["NH-13 (Sela Pass section)"],
        "last_supply_date": "2026-01-18",
        "severity": "critical",
        "alternative_access": "Helicopter airlift via Army helipad. Next sortie scheduled tomorrow.",
    },
    {
        "region_name": "Dhubri River Islands",
        "state": "Assam",
        "district": "Dhubri",
        "population": 25000,
        "accessible_roads": 0,
        "blocked_roads": ["Embankment access road", "Ferry jetty approach"],
        "last_supply_date": "2026-01-19",
        "severity": "high",
        "alternative_access": "Country boats and INDO-THIBET BORDER POLICE boats. Limited capacity.",
    },
    {
        "region_name": "Lunglei South District",
        "state": "Mizoram",
        "district": "Lunglei",
        "population": 8500,
        "accessible_roads": 1,
        "blocked_roads": ["Aizawl-Lunglei Road (Tuivawl section)"],
        "last_supply_date": "2026-01-20",
        "severity": "medium",
        "alternative_access": "Alternative interior road via Champhai (adds 6 hours).",
    },
]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/status", response_model=EmergencyStatus)
async def get_emergency_status(db: Session = Depends(get_db), _user: dict = Depends(get_current_user)):
    return EmergencyStatus(
        **_emergency_state,
        active_deliveries=sum(1 for d in _DEMO_CRITICAL_DELIVERIES if d["status"] == "in_transit"),
        vehicles_deployed=3,
        incidents_active=3,
    )


@router.post("/activate", response_model=EmergencyStatus)
async def activate_emergency(
    request: EmergencyActivateRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    _emergency_state.update({
        "is_active": True,
        "severity": request.severity,
        "reason": request.reason,
        "activated_at": datetime.utcnow().isoformat() + "Z",
        "activated_by": current_user.get("username", "unknown"),
        "affected_states": request.affected_states,
        "affected_districts": request.affected_districts,
    })
    return EmergencyStatus(**_emergency_state, active_deliveries=2, vehicles_deployed=3, incidents_active=3)


@router.post("/deactivate", response_model=EmergencyStatus)
async def deactivate_emergency(
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    _emergency_state.update({
        "is_active": False,
        "severity": None,
        "reason": None,
        "activated_at": None,
        "activated_by": None,
        "affected_states": [],
        "affected_districts": [],
    })
    return EmergencyStatus(**_emergency_state)


@router.get("/accessible-routes", response_model=AccessibleRoutesResponse)
async def get_accessible_routes(
    state: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    routes = list(_DEMO_ACCESSIBLE_ROUTES)
    if state:
        routes = [r for r in routes if r["state"].lower() == state.lower()]
    total_accessible = sum(1 for r in routes if r["accessible"])
    return AccessibleRoutesResponse(
        routes=[AccessibleRoute(**r) for r in routes],
        total_accessible=total_accessible,
        total_blocked=len(routes) - total_accessible,
    )


@router.get("/critical-deliveries", response_model=CriticalDeliveriesResponse)
async def get_critical_deliveries(
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    deliveries = list(_DEMO_CRITICAL_DELIVERIES)
    if status_filter:
        deliveries = [d for d in deliveries if d["status"] == status_filter]
    return CriticalDeliveriesResponse(deliveries=[CriticalDelivery(**d) for d in deliveries], total=len(deliveries))


@router.get("/isolated-regions", response_model=IsolatedRegionsResponse)
async def get_isolated_regions(
    severity: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    regions = list(_DEMO_ISOLATED_REGIONS)
    if severity:
        regions = [r for r in regions if r["severity"] == severity]
    if state:
        regions = [r for r in regions if r["state"].lower() == state.lower()]
    return IsolatedRegionsResponse(regions=[IsolatedRegion(**r) for r in regions], total=len(regions))
