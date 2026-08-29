# ============================================================
# NERRO - Analytics Routes (routes/analytics.py)
# Endpoints      : GET /api/analytics/overview, /disruptions, /district-risk,
#                  /route-reliability, /incidents, /deliveries
# Purpose        : Aggregated KPIs + trends for dashboards and reports.
# TEAM NOTE      : All values are demo aggregates. Compute these from the DB
#                  (counts, averages, groupings) once real data flows in; keep the
#                  response schema identical for the frontend charts.
# ============================================================
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.routes.auth import get_current_user

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])

# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------


class OverviewResponse(BaseModel):
    total_roads: int
    roads_open: int
    roads_restricted: int
    roads_closed: int
    total_vehicles: int
    vehicles_active: int
    total_incidents: int
    active_incidents: int
    critical_incidents: int
    alerts_unread: int
    emergency_mode: bool
    avg_risk_score: float
    roads_by_state: dict
    incidents_by_type: dict
    recent_activity: list[dict]


class DisruptionTrend(BaseModel):
    date: str
    count: int
    severity_breakdown: dict


class DisruptionsResponse(BaseModel):
    trends: list[DisruptionTrend]
    period_days: int
    total_disruptions: int
    avg_per_day: float
    trend_direction: str


class DistrictRisk(BaseModel):
    state: str
    district: str
    risk_score: float
    risk_level: str
    active_incidents: int
    road_condition_avg: float
    population_affected: int


class DistrictRiskResponse(BaseModel):
    districts: list[DistrictRisk]
    total: int


class RouteReliability(BaseModel):
    road_id: str
    road_name: str
    state: str
    reliability_score: float
    on_time_percentage: float
    avg_delay_hours: float
    total_journeys: int
    disruptions_last_30d: int


class RouteReliabilityResponse(BaseModel):
    routes: list[RouteReliability]
    overall_reliability: float


class IncidentDistribution(BaseModel):
    by_type: dict
    by_severity: dict
    by_state: dict
    by_hour: list[dict]
    total: int
    avg_response_time_hrs: float


class DeliveryPerformance(BaseModel):
    total_deliveries: int
    completed: int
    in_transit: int
    delayed: int
    failed: int
    on_time_percentage: float
    avg_delivery_hours: float
    commodities_delivered: dict
    deliveries_by_state: dict


class DeliveriesResponse(BaseModel):
    performance: DeliveryPerformance
    recent_deliveries: list[dict]


# ---------------------------------------------------------------------------
# Demo Data
# ---------------------------------------------------------------------------


@router.get("/overview", response_model=OverviewResponse)
async def get_overview(db: Session = Depends(get_db), _user: dict = Depends(get_current_user)):
    return OverviewResponse(
        total_roads=8,
        roads_open=4,
        roads_restricted=2,
        roads_closed=2,
        total_vehicles=5,
        vehicles_active=2,
        total_incidents=5,
        active_incidents=3,
        critical_incidents=2,
        alerts_unread=3,
        emergency_mode=False,
        avg_risk_score=0.58,
        roads_by_state={
            "Arunachal Pradesh": {"total": 1, "open": 0, "restricted": 0, "closed": 1},
            "Assam": {"total": 1, "open": 1, "restricted": 0, "closed": 0},
            "Manipur": {"total": 1, "open": 0, "restricted": 1, "closed": 0},
            "Meghalaya": {"total": 1, "open": 1, "restricted": 0, "closed": 0},
            "Mizoram": {"total": 1, "open": 0, "restricted": 0, "closed": 1},
            "Nagaland": {"total": 1, "open": 1, "restricted": 0, "closed": 0},
            "Sikkim": {"total": 1, "open": 0, "restricted": 1, "closed": 0},
            "Tripura": {"total": 1, "open": 1, "restricted": 0, "closed": 0},
        },
        incidents_by_type={"landslide": 1, "flooding": 1, "road_damage": 1, "bridge_failure": 1, "earthquake": 1},
        recent_activity=[
            {"time": "2026-01-21T10:35:00Z", "type": "alert", "description": "Critical alert: Landslide on NH-13"},
            {"time": "2026-01-21T09:00:00Z", "type": "alert", "description": "Flash flood warning - Udalguri"},
            {"time": "2026-01-21T07:15:00Z", "type": "incident", "description": "Bridge crack reported at Umiam"},
            {"time": "2026-01-21T06:00:00Z", "type": "weather", "description": "Heavy rain advisory for 48 hours"},
            {"time": "2026-01-20T16:00:00Z", "type": "delivery", "description": "Medicine delivery to Tawang completed"},
        ],
    )


@router.get("/disruptions", response_model=DisruptionsResponse)
async def get_disruptions(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    return DisruptionsResponse(
        trends=[
            {"date": "2026-01-21", "count": 4, "severity_breakdown": {"critical": 2, "high": 1, "medium": 1}},
            {"date": "2026-01-20", "count": 2, "severity_breakdown": {"high": 1, "medium": 1}},
            {"date": "2026-01-19", "count": 3, "severity_breakdown": {"high": 2, "low": 1}},
            {"date": "2026-01-18", "count": 1, "severity_breakdown": {"medium": 1}},
            {"date": "2026-01-17", "count": 0, "severity_breakdown": {}},
            {"date": "2026-01-16", "count": 2, "severity_breakdown": {"medium": 1, "low": 1}},
            {"date": "2026-01-15", "count": 1, "severity_breakdown": {"high": 1}},
        ],
        period_days=days,
        total_disruptions=13,
        avg_per_day=1.86,
        trend_direction="increasing",
    )


@router.get("/district-risk", response_model=DistrictRiskResponse)
async def get_district_risk(
    state: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    districts = [
        {"state": "Arunachal Pradesh", "district": "Tawang", "risk_score": 0.82, "risk_level": "high", "active_incidents": 1, "road_condition_avg": 0.55, "population_affected": 1200},
        {"state": "Assam", "district": "Kamrup Metro", "risk_score": 0.35, "risk_level": "low", "active_incidents": 0, "road_condition_avg": 0.75, "population_affected": 0},
        {"state": "Assam", "district": "Udalguri", "risk_score": 0.70, "risk_level": "high", "active_incidents": 1, "road_condition_avg": 0.50, "population_affected": 3500},
        {"state": "Manipur", "district": "Imphal West", "risk_score": 0.45, "risk_level": "medium", "active_incidents": 0, "road_condition_avg": 0.60, "population_affected": 500},
        {"state": "Meghalaya", "district": "East Khasi Hills", "risk_score": 0.62, "risk_level": "medium", "active_incidents": 1, "road_condition_avg": 0.68, "population_affected": 8000},
        {"state": "Mizoram", "district": "Aizawl", "risk_score": 0.83, "risk_level": "high", "active_incidents": 1, "road_condition_avg": 0.45, "population_affected": 8500},
        {"state": "Nagaland", "district": "Kohima", "risk_score": 0.40, "risk_level": "medium", "active_incidents": 0, "road_condition_avg": 0.70, "population_affected": 0},
        {"state": "Sikkim", "district": "East Sikkim", "risk_score": 0.78, "risk_level": "high", "active_incidents": 0, "road_condition_avg": 0.52, "population_affected": 0},
        {"state": "Tripura", "district": "West Tripura", "risk_score": 0.25, "risk_level": "low", "active_incidents": 0, "road_condition_avg": 0.80, "population_affected": 0},
    ]
    if state:
        districts = [d for d in districts if d["state"].lower() == state.lower()]

    return DistrictRiskResponse(districts=[DistrictRisk(**d) for d in districts], total=len(districts))


@router.get("/route-reliability", response_model=RouteReliabilityResponse)
async def get_route_reliability(db: Session = Depends(get_db), _user: dict = Depends(get_current_user)):
    routes = [
        {"road_id": "road_001", "road_name": "NH-13 (Tawang Highway)", "state": "Arunachal Pradesh", "reliability_score": 0.58, "on_time_percentage": 45.0, "avg_delay_hours": 3.2, "total_journeys": 340, "disruptions_last_30d": 8},
        {"road_id": "road_002", "road_name": "NH-37 (Assam Trunk Road)", "state": "Assam", "reliability_score": 0.85, "on_time_percentage": 82.0, "avg_delay_hours": 0.5, "total_journeys": 1200, "disruptions_last_30d": 2},
        {"road_id": "road_003", "road_name": "Imphal-Dimapur Road", "state": "Manipur", "reliability_score": 0.62, "on_time_percentage": 52.0, "avg_delay_hours": 2.1, "total_journeys": 450, "disruptions_last_30d": 5},
        {"road_id": "road_004", "road_name": "Shillong-Cherrapunji Road", "state": "Meghalaya", "reliability_score": 0.75, "on_time_percentage": 72.0, "avg_delay_hours": 0.8, "total_journeys": 680, "disruptions_last_30d": 3},
        {"road_id": "road_005", "road_name": "Aizawl-Lunglei Road", "state": "Mizoram", "reliability_score": 0.42, "on_time_percentage": 35.0, "avg_delay_hours": 4.5, "total_journeys": 210, "disruptions_last_30d": 7},
        {"road_id": "road_006", "road_name": "Kohima-Mokokchung Road", "state": "Nagaland", "reliability_score": 0.68, "on_time_percentage": 65.0, "avg_delay_hours": 1.2, "total_journeys": 380, "disruptions_last_30d": 3},
        {"road_id": "road_007", "road_name": "Gangtok-Nathula Road", "state": "Sikkim", "reliability_score": 0.48, "on_time_percentage": 40.0, "avg_delay_hours": 3.8, "total_journeys": 150, "disruptions_last_30d": 6},
        {"road_id": "road_008", "road_name": "Agartala-Udaipur Road", "state": "Tripura", "reliability_score": 0.88, "on_time_percentage": 85.0, "avg_delay_hours": 0.3, "total_journeys": 520, "disruptions_last_30d": 1},
    ]
    overall = sum(r["reliability_score"] for r in routes) / len(routes)
    return RouteReliabilityResponse(routes=[RouteReliability(**r) for r in routes], overall_reliability=round(overall, 2))


@router.get("/incidents", response_model=IncidentDistribution)
async def get_incident_analytics(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    return IncidentDistribution(
        by_type={"landslide": 12, "flooding": 18, "earthquake": 3, "road_damage": 8, "bridge_failure": 2, "fire": 1, "accident": 5},
        by_severity={"low": 8, "medium": 15, "high": 18, "critical": 8},
        by_state={"Arunachal Pradesh": 12, "Assam": 15, "Manipur": 8, "Meghalaya": 5, "Mizoram": 4, "Nagaland": 3, "Sikkim": 3, "Tripura": 1},
        by_hour=[
            {"hour": h, "count": max(0, int(3 + 2 * (1 if 6 <= h <= 18 else 0) + (1 if 10 <= h <= 14 else 0)))}
            for h in range(24)
        ],
        total=49,
        avg_response_time_hrs=2.8,
    )


@router.get("/deliveries", response_model=DeliveriesResponse)
async def get_delivery_analytics(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    return DeliveriesResponse(
        performance=DeliveryPerformance(
            total_deliveries=156,
            completed=132,
            in_transit=12,
            delayed=8,
            failed=4,
            on_time_percentage=84.6,
            avg_delivery_hours=11.2,
            commodities_delivered={
                "Medicines": 42,
                "Food Supplies": 38,
                "Fuel": 25,
                "Construction Materials": 18,
                "Medical Equipment": 12,
                "Others": 21,
            },
            deliveries_by_state={
                "Arunachal Pradesh": 35,
                "Assam": 42,
                "Manipur": 18,
                "Meghalaya": 22,
                "Mizoram": 12,
                "Nagaland": 10,
                "Sikkim": 8,
                "Tripura": 9,
            },
        ),
        recent_deliveries=[
            {"id": "del_001", "description": "Emergency medicines to Tawang PHC", "status": "in_transit", "eta_hours": 6.5},
            {"id": "del_002", "description": "Food supplies to flood-affected Udalguri", "status": "scheduled", "eta_hours": None},
            {"id": "del_003", "description": "Medical team transport to Mokokchung", "status": "in_transit", "eta_hours": 3.0},
            {"id": "del_004", "description": "Fuel delivery to Tawang depot", "status": "completed", "eta_hours": 0},
            {"id": "del_005", "description": "Construction materials to Shillong", "status": "completed", "eta_hours": 0},
        ],
    )
