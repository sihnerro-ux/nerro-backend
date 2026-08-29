# ============================================================
# NERRO - States Routes (routes/states.py)
# Endpoints      : GET /api/states, GET /api/states/{id},
#                  GET /api/states/{id}/districts
# Purpose        : North-East 8-state reference data (risk, challenges, districts).
# TEAM NOTE      : Static reference dataset; extend from DB when more granular
#                  district/block data is needed.
# ============================================================
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.routes.auth import get_current_user

router = APIRouter(prefix="/api/states", tags=["States"])

# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------


class DistrictInfo(BaseModel):
    id: str
    name: str
    population: int
    area_sq_km: float
    headquarters: str
    road_density_km_per_sq_km: float
    risk_score: float


class StateResponse(BaseModel):
    id: str
    name: str
    code: str
    population: int
    area_sq_km: float
    capital: str
    district_count: int
    total_roads: int
    active_incidents: int
    average_risk_score: float
    coordinates: dict


class StateDetailResponse(BaseModel):
    id: str
    name: str
    code: str
    population: int
    area_sq_km: float
    capital: str
    district_count: int
    total_roads: int
    active_incidents: int
    average_risk_score: float
    coordinates: dict
    description: str
    key_challenges: list[str]
    connectivity_index: float


class StateListResponse(BaseModel):
    states: list[StateResponse]
    total: int


class DistrictListResponse(BaseModel):
    state: str
    districts: list[DistrictInfo]
    total: int


# ---------------------------------------------------------------------------
# Demo Data
# ---------------------------------------------------------------------------

_DEMO_STATES: list[dict] = [
    {
        "id": "state_001",
        "name": "Arunachal Pradesh",
        "code": "AR",
        "population": 1570458,
        "area_sq_km": 83743,
        "capital": "Itanagar",
        "district_count": 26,
        "total_roads": 45,
        "active_incidents": 1,
        "average_risk_score": 0.75,
        "coordinates": {"lat": 27.1044, "lng": 93.6920},
    },
    {
        "id": "state_002",
        "name": "Assam",
        "code": "AS",
        "population": 35607039,
        "area_sq_km": 78438,
        "capital": "Dispur",
        "district_count": 35,
        "total_roads": 82,
        "active_incidents": 1,
        "average_risk_score": 0.38,
        "coordinates": {"lat": 26.2006, "lng": 92.9376},
    },
    {
        "id": "state_003",
        "name": "Manipur",
        "code": "MN",
        "population": 2855794,
        "area_sq_km": 22327,
        "capital": "Imphal",
        "district_count": 16,
        "total_roads": 32,
        "active_incidents": 1,
        "average_risk_score": 0.52,
        "coordinates": {"lat": 24.6637, "lng": 93.9063},
    },
    {
        "id": "state_004",
        "name": "Meghalaya",
        "code": "ML",
        "population": 3211474,
        "area_sq_km": 22429,
        "capital": "Shillong",
        "district_count": 12,
        "total_roads": 28,
        "active_incidents": 1,
        "average_risk_score": 0.55,
        "coordinates": {"lat": 25.4670, "lng": 91.3662},
    },
    {
        "id": "state_005",
        "name": "Mizoram",
        "code": "MZ",
        "population": 1239244,
        "area_sq_km": 21081,
        "capital": "Aizawl",
        "district_count": 11,
        "total_roads": 22,
        "active_incidents": 1,
        "average_risk_score": 0.70,
        "coordinates": {"lat": 23.1645, "lng": 92.9376},
    },
    {
        "id": "state_006",
        "name": "Nagaland",
        "code": "NL",
        "population": 1978502,
        "area_sq_km": 16579,
        "capital": "Kohima",
        "district_count": 16,
        "total_roads": 26,
        "active_incidents": 0,
        "average_risk_score": 0.48,
        "coordinates": {"lat": 26.1581, "lng": 94.5624},
    },
    {
        "id": "state_007",
        "name": "Sikkim",
        "code": "SK",
        "population": 690251,
        "area_sq_km": 7096,
        "capital": "Gangtok",
        "district_count": 6,
        "total_roads": 18,
        "active_incidents": 0,
        "average_risk_score": 0.65,
        "coordinates": {"lat": 27.5330, "lng": 88.5122},
    },
    {
        "id": "state_008",
        "name": "Tripura",
        "code": "TR",
        "population": 4169812,
        "area_sq_km": 10486,
        "capital": "Agartala",
        "district_count": 8,
        "total_roads": 20,
        "active_incidents": 0,
        "average_risk_score": 0.28,
        "coordinates": {"lat": 23.9408, "lng": 92.1060},
    },
]

_DEMO_STATE_DETAILS: dict = {
    "state_001": {
        "description": "The Land of Dawn-Lit Mountains. India's largest state by area in the NE region. Strategically critical border state with difficult mountain terrain.",
        "key_challenges": [
            "Extreme terrain with passes above 4000m",
            "Heavy monsoon rainfall causing landslides",
            "Limited road infrastructure in border areas",
            "Long supply chain distances from main hubs",
        ],
        "connectivity_index": 0.45,
    },
    "state_002": {
        "description": "Gateway to the North-East. Most connected state with major highway intersections. Prone to flooding along the Brahmaputra basin.",
        "key_challenges": [
            "Brahmaputra river basin flooding",
            "Erosion along river embankments",
            "Traffic congestion in Guwahati metro",
            "Bridge maintenance on trunk highways",
        ],
        "connectivity_index": 0.78,
    },
    "state_003": {
        "description": "Jewel of India. Hilly terrain with valley settlements. Key connectivity to the south through Dimapur corridor.",
        "key_challenges": [
            "Imphal-Dimapur road condition",
            "Remote hill district connectivity",
            "Monsoon-induced road damage",
            "Limited alternative routes",
        ],
        "connectivity_index": 0.55,
    },
    "state_004": {
        "description": "Abode of Clouds. receives some of the highest rainfall on Earth. Unique challenge of maintaining roads in extreme precipitation.",
        "key_challenges": [
            "World's heaviest rainfall zones",
            "Bridge and culvert damage",
            "Landslides in Khasi and Jaintia hills",
            "Remote Garo hills connectivity",
        ],
        "connectivity_index": 0.52,
    },
    "state_005": {
        "description": "Land of the Hill People. Remote state with limited connectivity. Heavy monsoon impact with frequent road blockages.",
        "key_challenges": [
            "Limited road network density",
            "Extreme monsoon impact",
            "Remote southern districts",
            "Landslide-prone terrain",
        ],
        "connectivity_index": 0.40,
    },
    "state_006": {
        "description": "Land of Festivals. Mountainous terrain with important connectivity to Assam via Kohima-Dimapur corridor.",
        "key_challenges": [
            "Kohima-Mokokchung road condition",
            "Remote Naga hills connectivity",
            "Seismic zone risk",
            "Limited emergency response infrastructure",
        ],
        "connectivity_index": 0.50,
    },
    "state_007": {
        "description": "India's smallest state with strategic border importance. Extremely challenging mountain terrain with limited road options.",
        "key_challenges": [
            "Nathula Pass access restrictions",
            "Extreme altitude variations",
            "Seismic risk (high earthquake zone)",
            "Tourism traffic vs logistics conflicts",
        ],
        "connectivity_index": 0.42,
    },
    "state_008": {
        "description": "Land of Fourteen Gods. Relatively flat terrain compared to other NE states. Good connectivity within the state.",
        "key_challenges": [
            "Cross-border trade route maintenance",
            "Flood-prone southern plains",
            "Limited highway capacity",
            "Aging bridge infrastructure",
        ],
        "connectivity_index": 0.65,
    },
}

_DEMO_DISTRICTS: dict = {
    "state_001": [
        {"id": "dist_001", "name": "Tawang", "population": 49977, "area_sq_km": 2172, "headquarters": "Tawang", "road_density_km_per_sq_km": 0.12, "risk_score": 0.85},
        {"id": "dist_002", "name": "West Kameng", "population": 83947, "area_sq_km": 7422, "headquarters": "Bomdila", "road_density_km_per_sq_km": 0.18, "risk_score": 0.70},
        {"id": "dist_003", "name": "East Kameng", "population": 78413, "area_sq_km": 4134, "headquarters": "Seppa", "road_density_km_per_sq_km": 0.14, "risk_score": 0.72},
        {"id": "dist_004", "name": "Papum Pare", "population": 176385, "area_sq_km": 3460, "headquarters": "Yupia", "road_density_km_per_sq_km": 0.25, "risk_score": 0.55},
        {"id": "dist_005", "name": "Itanagar Capital Complex", "population": 118895, "area_sq_km": 100, "headquarters": "Itanagar", "road_density_km_per_sq_km": 0.45, "risk_score": 0.40},
    ],
    "state_002": [
        {"id": "dist_006", "name": "Kamrup Metro", "population": 1260710, "area_sq_km": 1528, "headquarters": "Guwahati", "road_density_km_per_sq_km": 0.55, "risk_score": 0.30},
        {"id": "dist_007", "name": "Udalguri", "population": 831668, "area_sq_km": 1668, "headquarters": "Udalguri", "road_density_km_per_sq_km": 0.32, "risk_score": 0.70},
        {"id": "dist_008", "name": "Dhubri", "population": 1948632, "area_sq_km": 2888, "headquarters": "Dhubri", "road_density_km_per_sq_km": 0.28, "risk_score": 0.65},
        {"id": "dist_009", "name": "Dibrugarh", "product": "Tea capital", "population": 1326331, "area_sq_km": 3381, "headquarters": "Dibrugarh", "road_density_km_per_sq_km": 0.38, "risk_score": 0.25},
        {"id": "dist_010", "name": "Jorhat", "population": 1092311, "area_sq_km": 1709, "headquarters": "Jorhat", "road_density_km_per_sq_km": 0.40, "risk_score": 0.28},
    ],
    "state_003": [
        {"id": "dist_011", "name": "Imphal West", "population": 517866, "area_sq_km": 519, "headquarters": "Imphal", "road_density_km_per_sq_km": 0.50, "risk_score": 0.40},
        {"id": "dist_012", "name": "Senapati", "population": 354772, "area_sq_km": 3271, "headquarters": "Senapati", "road_density_km_per_sq_km": 0.18, "risk_score": 0.62},
        {"id": "dist_013", "name": "Chandel", "population": 144182, "area_sq_km": 3313, "headquarters": "Chandel", "road_density_km_per_sq_km": 0.10, "risk_score": 0.75},
    ],
    "state_004": [
        {"id": "dist_014", "name": "East Khasi Hills", "population": 825923, "area_sq_km": 2752, "headquarters": "Shillong", "road_density_km_per_sq_km": 0.35, "risk_score": 0.55},
        {"id": "dist_015", "name": "West Garo Hills", "population": 633421, "area_sq_km": 3714, "headquarters": "Tura", "road_density_km_per_sq_km": 0.22, "risk_score": 0.50},
    ],
    "state_005": [
        {"id": "dist_016", "name": "Aizawl", "population": 507000, "area_sq_km": 3576, "headquarters": "Aizawl", "road_density_km_per_sq_km": 0.28, "risk_score": 0.65},
        {"id": "dist_017", "name": "Lunglei", "population": 161423, "area_sq_km": 4538, "headquarters": "Lunglei", "road_density_km_per_sq_km": 0.15, "risk_score": 0.80},
    ],
    "state_006": [
        {"id": "dist_018", "name": "Kohima", "population": 270063, "area_sq_km": 1463, "headquarters": "Kohima", "road_density_km_per_sq_km": 0.35, "risk_score": 0.42},
        {"id": "dist_019", "name": "Mokokchung", "population": 194622, "area_sq_km": 1615, "headquarters": "Mokokchung", "road_density_km_per_sq_km": 0.28, "risk_score": 0.50},
    ],
    "state_007": [
        {"id": "dist_020", "name": "East Sikkim", "population": 283583, "area_sq_km": 964, "headquarters": "Gangtok", "road_density_km_per_sq_km": 0.40, "risk_score": 0.70},
        {"id": "dist_021", "name": "West Sikkim", "population": 147734, "area_sq_km": 1166, "headquarters": "Gyalshing", "road_density_km_per_sq_km": 0.25, "risk_score": 0.60},
    ],
    "state_008": [
        {"id": "dist_022", "name": "West Tripura", "population": 1938403, "area_sq_km": 2997, "headquarters": "Agartala", "road_density_km_per_sq_km": 0.48, "risk_score": 0.22},
        {"id": "dist_023", "name": "South Tripura", "population": 931185, "area_sq_km": 2142, "headquarters": "Udaipur", "road_density_km_per_sq_km": 0.32, "risk_score": 0.30},
    ],
}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("", response_model=StateListResponse)
async def list_states(db: Session = Depends(get_db), _user: dict = Depends(get_current_user)):
    return StateListResponse(states=[StateResponse(**s) for s in _DEMO_STATES], total=len(_DEMO_STATES))


@router.get("/{state_id}", response_model=StateDetailResponse)
async def get_state(state_id: str, db: Session = Depends(get_db), _user: dict = Depends(get_current_user)):
    state = next((s for s in _DEMO_STATES if s["id"] == state_id), None)
    if not state:
        raise HTTPException(status_code=404, detail=f"State {state_id} not found")

    details = _DEMO_STATE_DETAILS.get(state_id, {"description": "", "key_challenges": [], "connectivity_index": 0.5})
    return StateDetailResponse(**{**state, **details})


@router.get("/{state_id}/districts", response_model=DistrictListResponse)
async def get_state_districts(state_id: str, db: Session = Depends(get_db), _user: dict = Depends(get_current_user)):
    state = next((s for s in _DEMO_STATES if s["id"] == state_id), None)
    if not state:
        raise HTTPException(status_code=404, detail=f"State {state_id} not found")

    districts = _DEMO_DISTRICTS.get(state_id, [])
    return DistrictListResponse(state=state["name"], districts=[DistrictInfo(**d) for d in districts], total=len(districts))
