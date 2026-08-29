# ============================================================
# NERRO - Alerts Routes (routes/alerts.py)
# Endpoints      : GET /api/alerts, /api/alerts/unread, POST /api/alerts,
#                  PUT /api/alerts/{id}/read
# Purpose        : Alert inbox - create, filter (severity/category/state), read state.
# TEAM NOTE      : Persist alerts to the Alert DB table + alert_service for real
#                  delivery (WebSocket/email/SMS). Frontend Notifications page
#                  polls these endpoints today.
# ============================================================
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.routes.auth import get_current_user

router = APIRouter(prefix="/api/alerts", tags=["Alerts"])

# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------


class AlertCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    message: str = Field(..., min_length=1)
    severity: str = Field(..., pattern="^(info|warning|critical|emergency)$")
    category: str = Field(..., pattern="^(weather|incident|route|system|delivery|security)$")
    target_states: list[str] = Field(default_factory=list)
    target_districts: list[str] = Field(default_factory=list)
    target_roles: list[str] = Field(default_factory=list)
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    related_road_id: Optional[str] = None
    related_incident_id: Optional[str] = None


class AlertResponse(BaseModel):
    id: str
    title: str
    message: str
    severity: str
    category: str
    is_read: bool
    target_states: list[str]
    target_districts: list[str]
    target_roles: list[str]
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    related_road_id: Optional[str] = None
    related_incident_id: Optional[str] = None
    created_by: Optional[str] = None
    created_at: str
    read_at: Optional[str] = None


class AlertListResponse(BaseModel):
    alerts: list[AlertResponse]
    total: int
    unread_count: int


class UnreadCountResponse(BaseModel):
    count: int
    by_severity: dict


# ---------------------------------------------------------------------------
# Demo Data
# ---------------------------------------------------------------------------

_DEMO_ALERTS: list[dict] = [
    {
        "id": "alert_001",
        "title": "CRITICAL: Major Landslide on NH-13",
        "message": "Massive landslide near Sela Pass (km 187) blocking NH-13. All traffic halted. BRO team dispatched. Avoid Tezpur-Tawang route.",
        "severity": "critical",
        "category": "incident",
        "is_read": False,
        "target_states": ["Arunachal Pradesh"],
        "target_districts": ["Tawang", "West Kameng"],
        "target_roles": ["admin", "field_officer"],
        "latitude": 27.25,
        "longitude": 92.10,
        "related_road_id": "road_001",
        "related_incident_id": "inc_001",
        "created_by": "system",
        "created_at": "2026-01-21T10:35:00Z",
        "read_at": None,
    },
    {
        "id": "alert_002",
        "title": "Flash Flood Warning - Udalguri District",
        "message": "Bharali River rising fast. Waterlogging on NH-37 near Udalguri. Divert traffic via Mangaldoi. Expected peak at 6PM.",
        "severity": "warning",
        "category": "weather",
        "is_read": False,
        "target_states": ["Assam"],
        "target_districts": ["Udalguri", "Darrang"],
        "target_roles": ["admin", "field_officer"],
        "latitude": 26.75,
        "longitude": 92.15,
        "related_road_id": "road_002",
        "related_incident_id": "inc_002",
        "created_by": "field_officer2",
        "created_at": "2026-01-21T09:00:00Z",
        "read_at": None,
    },
    {
        "id": "alert_003",
        "title": "Weather Advisory: Heavy Rain Expected",
        "message": "IMD predicts heavy rainfall (50-100mm) across Meghalaya and Assam for next 48 hours. Road conditions may deteriorate. Prepare contingency routes.",
        "severity": "info",
        "category": "weather",
        "is_read": True,
        "target_states": ["Assam", "Meghalaya"],
        "target_districts": [],
        "target_roles": ["admin", "field_officer", "viewer"],
        "latitude": None,
        "longitude": None,
        "related_road_id": None,
        "related_incident_id": None,
        "created_by": "system",
        "created_at": "2026-01-21T06:00:00Z",
        "read_at": "2026-01-21T07:30:00Z",
    },
    {
        "id": "alert_004",
        "title": "Bridge Crack - Umiam Lake Approach",
        "message": "Structural crack detected on Umiam bridge approach. Heavy vehicles (>5T) restricted. Light vehicles proceed with escort. Assessment team deployed.",
        "severity": "critical",
        "category": "route",
        "is_read": False,
        "target_states": ["Meghalaya"],
        "target_districts": ["East Khasi Hills", "Ri Bhoi"],
        "target_roles": ["admin", "field_officer"],
        "latitude": 25.55,
        "longitude": 91.88,
        "related_road_id": "road_004",
        "related_incident_id": "inc_004",
        "created_by": "PWD_engineer",
        "created_at": "2026-01-21T07:15:00Z",
        "read_at": None,
    },
    {
        "id": "alert_005",
        "title": "Supply Delivery Completed",
        "message": "Medicine delivery to Tawang PHC completed successfully by vehicle NERRO-Alpha. Next scheduled delivery: 28 Jan.",
        "severity": "info",
        "category": "delivery",
        "is_read": True,
        "target_states": ["Arunachal Pradesh"],
        "target_districts": ["Tawang"],
        "target_roles": ["admin"],
        "latitude": 27.5869,
        "longitude": 91.8593,
        "related_road_id": None,
        "related_incident_id": None,
        "created_by": "veh_001",
        "created_at": "2026-01-20T16:00:00Z",
        "read_at": "2026-01-20T17:00:00Z",
    },
]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/unread", response_model=UnreadCountResponse)
async def get_unread_count(
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    unread = [a for a in _DEMO_ALERTS if not a["is_read"]]
    by_severity: dict = {}
    for a in unread:
        by_severity[a["severity"]] = by_severity.get(a["severity"], 0) + 1
    return UnreadCountResponse(count=len(unread), by_severity=by_severity)


@router.get("", response_model=AlertListResponse)
async def list_alerts(
    severity: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    unread_only: bool = Query(False),
    state: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    alerts = list(_DEMO_ALERTS)
    if severity:
        alerts = [a for a in alerts if a["severity"] == severity]
    if category:
        alerts = [a for a in alerts if a["category"] == category]
    if unread_only:
        alerts = [a for a in alerts if not a["is_read"]]
    if state:
        alerts = [a for a in alerts if state in a["target_states"] or not a["target_states"]]

    unread_count = sum(1 for a in _DEMO_ALERTS if not a["is_read"])
    return AlertListResponse(
        alerts=[AlertResponse(**a) for a in alerts],
        total=len(alerts),
        unread_count=unread_count,
    )


@router.post("", response_model=AlertResponse, status_code=status.HTTP_201_CREATED)
async def create_alert(
    request: AlertCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    new_alert = {
        "id": f"alert_{len(_DEMO_ALERTS)+1:03d}",
        **request.model_dump(),
        "is_read": False,
        "created_by": current_user.get("username", "unknown"),
        "created_at": datetime.utcnow().isoformat() + "Z",
        "read_at": None,
    }
    _DEMO_ALERTS.append(new_alert)
    return AlertResponse(**new_alert)


@router.put("/{alert_id}/read", response_model=AlertResponse)
async def mark_alert_read(
    alert_id: str,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    alert = next((a for a in _DEMO_ALERTS if a["id"] == alert_id), None)
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Alert {alert_id} not found")
    alert["is_read"] = True
    alert["read_at"] = datetime.utcnow().isoformat() + "Z"
    return AlertResponse(**alert)
