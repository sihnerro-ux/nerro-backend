# ============================================================
# NERRO - Incidents Routes (routes/incidents.py)
# Endpoints      : GET /api/incidents, /api/incidents/active, POST /api/incidents,
#                  GET/PUT /api/incidents/{id}
# Purpose        : Report, list, filter and update road incidents.
# TEAM NOTE      : New reports are stored in memory (_DEMO_INCIDENTS). Persist to the
#                  Incident DB table and broadcast via WebSocket for live dashboards.
# ============================================================
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.routes.auth import get_current_user

router = APIRouter(prefix="/api/incidents", tags=["Incidents"])

# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------


class IncidentCreate(BaseModel):
    type: str = Field(..., pattern="^(landslide|flooding|earthquake|fire|accident|road_damage|bridge_failure|avalanche|cyclone|other)$")
    severity: str = Field(..., pattern="^(low|medium|high|critical)$")
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1)
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    road_id: Optional[str] = None
    state: Optional[str] = None
    district: Optional[str] = None
    affected_population: Optional[int] = None
    images: list[str] = Field(default_factory=list)


class IncidentUpdate(BaseModel):
    severity: Optional[str] = Field(None, pattern="^(low|medium|high|critical)$")
    status: Optional[str] = Field(None, pattern="^(reported|verified|responding|resolved|closed)$")
    description: Optional[str] = None
    affected_population: Optional[int] = None
    responder_notes: Optional[str] = None


class IncidentResponse(BaseModel):
    id: str
    type: str
    severity: str
    status: str
    title: str
    description: str
    latitude: float
    longitude: float
    road_id: Optional[str] = None
    state: Optional[str] = None
    district: Optional[str] = None
    affected_population: Optional[int] = None
    reported_by: Optional[str] = None
    reported_at: str
    updated_at: str
    images: list[str] = Field(default_factory=list)
    responder_notes: Optional[str] = None


class IncidentListResponse(BaseModel):
    incidents: list[IncidentResponse]
    total: int
    active_count: int


# ---------------------------------------------------------------------------
# Demo Data
# ---------------------------------------------------------------------------

_DEMO_INCIDENTS: list[dict] = [
    {
        "id": "inc_001",
        "type": "landslide",
        "severity": "critical",
        "status": "responding",
        "title": "Major landslide on NH-13 near Sela Pass",
        "description": "A massive landslide triggered by heavy rainfall has blocked NH-13 near km marker 187. Multiple vehicles stranded. BRO teams mobilized.",
        "latitude": 27.2500,
        "longitude": 92.1000,
        "road_id": "road_001",
        "state": "Arunachal Pradesh",
        "district": "Tawang",
        "affected_population": 1200,
        "reported_by": "field_officer1",
        "reported_at": "2026-01-20T14:30:00Z",
        "updated_at": "2026-01-20T18:00:00Z",
        "images": [],
        "responder_notes": "BRO dispatched 2 excavators. Expected clearance in 8 hours.",
    },
    {
        "id": "inc_002",
        "type": "flooding",
        "severity": "high",
        "status": "verified",
        "title": "Flash flood at Bharali River crossing",
        "description": "Bharali River has risen 3m above normal. Road submerged for 200m stretch near Udalguri. Traffic diverted.",
        "latitude": 26.7528,
        "longitude": 92.1500,
        "road_id": "road_002",
        "state": "Assam",
        "district": "Udalguri",
        "affected_population": 3500,
        "reported_by": "field_officer2",
        "reported_at": "2026-01-19T08:15:00Z",
        "updated_at": "2026-01-19T12:30:00Z",
        "images": [],
        "responder_notes": None,
    },
    {
        "id": "inc_003",
        "type": "road_damage",
        "severity": "medium",
        "status": "reported",
        "title": "Pothole damage on Imphal-Dimapur road",
        "description": "Severe pothole damage across 2km stretch after monsoon. Speed reduced to 20km/h. NHP alerted.",
        "latitude": 25.4167,
        "longitude": 93.8833,
        "road_id": "road_003",
        "state": "Manipur",
        "district": "Senapati",
        "affected_population": 500,
        "reported_by": "local_police",
        "reported_at": "2026-01-18T10:00:00Z",
        "updated_at": "2026-01-18T10:00:00Z",
        "images": [],
        "responder_notes": None,
    },
    {
        "id": "inc_004",
        "type": "bridge_failure",
        "severity": "critical",
        "status": "verified",
        "title": "Bridge crack on Umiam Lake approach",
        "description": "Structural crack detected on Umiam bridge approach. Bridge closed for heavy vehicles. Assessment team deployed.",
        "latitude": 25.5500,
        "longitude": 91.8833,
        "road_id": "road_004",
        "state": "Meghalaya",
        "district": "East Khasi Hills",
        "affected_population": 8000,
        "reported_by": "PWD_engineer",
        "reported_at": "2026-01-21T06:45:00Z",
        "updated_at": "2026-01-21T09:00:00Z",
        "images": [],
        "responder_notes": "Bridge closed for loads > 5 tonnes. Light vehicles permitted with escort.",
    },
    {
        "id": "inc_005",
        "type": "earthquake",
        "severity": "high",
        "status": "resolved",
        "title": "5.2 magnitude earthquake near Mokokchung",
        "description": "Earthquake epicenter 30km NE of Mokokchung. Minor road cracks reported on SH-61. No casualties.",
        "latitude": 26.5500,
        "longitude": 94.7500,
        "road_id": "road_006",
        "state": "Nagaland",
        "district": "Mokokchung",
        "affected_population": 15000,
        "reported_by": "IMD_alert",
        "reported_at": "2026-01-15T03:22:00Z",
        "updated_at": "2026-01-16T14:00:00Z",
        "images": [],
        "responder_notes": "Road inspection completed. Minor repairs completed on SH-61.",
    },
]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/active", response_model=list[IncidentResponse])
async def get_active_incidents(
    severity: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    active = [i for i in _DEMO_INCIDENTS if i["status"] in ("reported", "verified", "responding")]
    if severity:
        active = [i for i in active if i["severity"] == severity]
    return [IncidentResponse(**i) for i in active]


@router.get("", response_model=IncidentListResponse)
async def list_incidents(
    incident_type: Optional[str] = Query(None, alias="type"),
    severity: Optional[str] = Query(None),
    incident_status: Optional[str] = Query(None, alias="status"),
    state: Optional[str] = Query(None),
    district: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    incidents = list(_DEMO_INCIDENTS)
    if incident_type:
        incidents = [i for i in incidents if i["type"] == incident_type]
    if severity:
        incidents = [i for i in incidents if i["severity"] == severity]
    if incident_status:
        incidents = [i for i in incidents if i["status"] == incident_status]
    if state:
        incidents = [i for i in incidents if i.get("state", "").lower() == state.lower()]
    if district:
        incidents = [i for i in incidents if i.get("district", "").lower() == district.lower()]

    active_count = sum(1 for i in incidents if i["status"] in ("reported", "verified", "responding"))
    return IncidentListResponse(
        incidents=[IncidentResponse(**i) for i in incidents],
        total=len(incidents),
        active_count=active_count,
    )


@router.post("", response_model=IncidentResponse, status_code=status.HTTP_201_CREATED)
async def create_incident(
    request: IncidentCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    now = datetime.utcnow().isoformat() + "Z"
    new_incident = {
        "id": f"inc_{len(_DEMO_INCIDENTS)+1:03d}",
        "type": request.type,
        "severity": request.severity,
        "status": "reported",
        "title": request.title,
        "description": request.description,
        "latitude": request.latitude,
        "longitude": request.longitude,
        "road_id": request.road_id,
        "state": request.state,
        "district": request.district,
        "affected_population": request.affected_population,
        "reported_by": current_user.get("username", "unknown"),
        "reported_at": now,
        "updated_at": now,
        "images": request.images,
        "responder_notes": None,
    }
    _DEMO_INCIDENTS.append(new_incident)
    return IncidentResponse(**new_incident)


@router.get("/{incident_id}", response_model=IncidentResponse)
async def get_incident(incident_id: str, db: Session = Depends(get_db), _user: dict = Depends(get_current_user)):
    incident = next((i for i in _DEMO_INCIDENTS if i["id"] == incident_id), None)
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Incident {incident_id} not found")
    return IncidentResponse(**incident)


@router.put("/{incident_id}", response_model=IncidentResponse)
async def update_incident(
    incident_id: str,
    update: IncidentUpdate,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    incident = next((i for i in _DEMO_INCIDENTS if i["id"] == incident_id), None)
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Incident {incident_id} not found")

    update_data = update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        incident[key] = value
    incident["updated_at"] = datetime.utcnow().isoformat() + "Z"
    return IncidentResponse(**incident)
