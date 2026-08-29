# ============================================================
# NERRO - Vehicles Routes (routes/vehicles.py)
# Endpoints      : GET /api/vehicles, /api/vehicles/active, POST /api/vehicles,
#                  GET /api/vehicles/{id}, PUT /{id}/location, PUT /{id}/status
# Purpose        : Fleet registry + live GPS tracking (lat/lng/speed/heading).
# TEAM NOTE      : The /{id}/location endpoint is where GPS/IoT feeds push live
#                  telemetry; broadcast those updates over WebSocket for real-time
#                  fleet tracking on the Vehicles page and map.
# ============================================================
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.routes.auth import get_current_user

router = APIRouter(prefix="/api/vehicles", tags=["Vehicles"])

# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------


class VehicleRegister(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    vehicle_type: str = Field(..., pattern="^(truck|van|bike|ambulance|4x4|boat|helicopter)$")
    registration_number: str = Field(..., min_length=4, max_length=20)
    driver_name: Optional[str] = None
    driver_phone: Optional[str] = None
    state: Optional[str] = None
    district: Optional[str] = None
    capacity_kg: Optional[float] = None
    fuel_type: str = Field(default="diesel")


class LocationUpdate(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    speed_kmh: Optional[float] = Field(None, ge=0)
    heading: Optional[float] = Field(None, ge=0, le=360)
    altitude_m: Optional[float] = None


class StatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(idle|en_route|returning|maintenance|offline|emergency)$")
    reason: Optional[str] = None


class VehicleResponse(BaseModel):
    id: str
    name: str
    vehicle_type: str
    registration_number: str
    driver_name: Optional[str] = None
    driver_phone: Optional[str] = None
    status: str
    state: Optional[str] = None
    district: Optional[str] = None
    capacity_kg: Optional[float] = None
    fuel_type: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    speed_kmh: Optional[float] = None
    heading: Optional[float] = None
    last_location_update: Optional[str] = None
    assigned_route_id: Optional[str] = None
    created_at: str


class VehicleListResponse(BaseModel):
    vehicles: list[VehicleResponse]
    total: int
    active_count: int


# ---------------------------------------------------------------------------
# Demo Data
# ---------------------------------------------------------------------------

_DEMO_VEHICLES: list[dict] = [
    {
        "id": "veh_001",
        "name": "NERRO Supply Truck Alpha",
        "vehicle_type": "truck",
        "registration_number": "AR-01-B-1234",
        "driver_name": "Karma Wangdi",
        "driver_phone": "+91-9402012345",
        "status": "en_route",
        "state": "Arunachal Pradesh",
        "district": "Tawang",
        "capacity_kg": 10000,
        "fuel_type": "diesel",
        "latitude": 27.0500,
        "longitude": 92.3500,
        "speed_kmh": 35.0,
        "heading": 315.0,
        "last_location_update": "2026-01-21T10:30:00Z",
        "assigned_route_id": "route_001",
        "created_at": "2025-06-15T08:00:00Z",
    },
    {
        "id": "veh_002",
        "name": "NERRO Emergency Van Bravo",
        "vehicle_type": "van",
        "registration_number": "AS-01-C-5678",
        "driver_name": "Pranab Teron",
        "driver_phone": "+91-9864012345",
        "status": "idle",
        "state": "Assam",
        "district": "Kamrup Metro",
        "capacity_kg": 2500,
        "fuel_type": "diesel",
        "latitude": 26.1445,
        "longitude": 91.7362,
        "speed_kmh": 0.0,
        "heading": 0.0,
        "last_location_update": "2026-01-21T10:25:00Z",
        "assigned_route_id": None,
        "created_at": "2025-07-20T08:00:00Z",
    },
    {
        "id": "veh_003",
        "name": "NERRO Field Bike Charlie",
        "vehicle_type": "bike",
        "registration_number": "MN-01-A-9012",
        "driver_name": "Lalrinawma",
        "driver_phone": "+91-9856012345",
        "status": "en_route",
        "state": "Manipur",
        "district": "Imphal West",
        "capacity_kg": 50,
        "fuel_type": "petrol",
        "latitude": 24.8200,
        "longitude": 93.9400,
        "speed_kmh": 45.0,
        "heading": 180.0,
        "last_location_update": "2026-01-21T10:28:00Z",
        "assigned_route_id": "route_003",
        "created_at": "2025-08-01T08:00:00Z",
    },
    {
        "id": "veh_004",
        "name": "NERRO 4x4 Scout Delta",
        "vehicle_type": "4x4",
        "registration_number": "ML-01-D-3456",
        "driver_name": "Badstar Kharshiing",
        "driver_phone": "+91-9612012345",
        "status": "maintenance",
        "state": "Meghalaya",
        "district": "East Khasi Hills",
        "capacity_kg": 1500,
        "fuel_type": "diesel",
        "latitude": 25.5788,
        "longitude": 91.8933,
        "speed_kmh": 0.0,
        "heading": 0.0,
        "last_location_update": "2026-01-20T16:00:00Z",
        "assigned_route_id": None,
        "created_at": "2025-05-10T08:00:00Z",
    },
    {
        "id": "veh_005",
        "name": "NERRO Ambulance Echo",
        "vehicle_type": "ambulance",
        "registration_number": "MZ-01-E-7890",
        "driver_name": "Lalrinkima",
        "driver_phone": "+91-9365012345",
        "status": "idle",
        "state": "Mizoram",
        "district": "Aizawl",
        "capacity_kg": 800,
        "fuel_type": "diesel",
        "latitude": 23.7271,
        "longitude": 92.7176,
        "speed_kmh": 0.0,
        "heading": 0.0,
        "last_location_update": "2026-01-21T09:00:00Z",
        "assigned_route_id": None,
        "created_at": "2025-09-15T08:00:00Z",
    },
]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/active", response_model=list[VehicleResponse])
async def get_active_vehicles(
    state: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    active = [v for v in _DEMO_VEHICLES if v["status"] in ("en_route", "returning")]
    if state:
        active = [v for v in active if v.get("state", "").lower() == state.lower()]
    return [VehicleResponse(**v) for v in active]


@router.get("", response_model=VehicleListResponse)
async def list_vehicles(
    vehicle_type: Optional[str] = Query(None),
    vehicle_status: Optional[str] = Query(None, alias="status"),
    state: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    vehicles = list(_DEMO_VEHICLES)
    if vehicle_type:
        vehicles = [v for v in vehicles if v["vehicle_type"] == vehicle_type]
    if vehicle_status:
        vehicles = [v for v in vehicles if v["status"] == vehicle_status]
    if state:
        vehicles = [v for v in vehicles if v.get("state", "").lower() == state.lower()]

    active_count = sum(1 for v in vehicles if v["status"] in ("en_route", "returning"))
    return VehicleListResponse(
        vehicles=[VehicleResponse(**v) for v in vehicles],
        total=len(vehicles),
        active_count=active_count,
    )


@router.post("", response_model=VehicleResponse, status_code=status.HTTP_201_CREATED)
async def register_vehicle(
    request: VehicleRegister,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    duplicate = next((v for v in _DEMO_VEHICLES if v["registration_number"] == request.registration_number), None)
    if duplicate:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Vehicle with this registration number already exists")

    new_vehicle = {
        "id": f"veh_{len(_DEMO_VEHICLES)+1:03d}",
        **request.model_dump(),
        "status": "idle",
        "latitude": None,
        "longitude": None,
        "speed_kmh": None,
        "heading": None,
        "last_location_update": None,
        "assigned_route_id": None,
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    _DEMO_VEHICLES.append(new_vehicle)
    return VehicleResponse(**new_vehicle)


@router.get("/{vehicle_id}", response_model=VehicleResponse)
async def get_vehicle(vehicle_id: str, db: Session = Depends(get_db), _user: dict = Depends(get_current_user)):
    vehicle = next((v for v in _DEMO_VEHICLES if v["id"] == vehicle_id), None)
    if not vehicle:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Vehicle {vehicle_id} not found")
    return VehicleResponse(**vehicle)


@router.put("/{vehicle_id}/location", response_model=VehicleResponse)
async def update_vehicle_location(
    vehicle_id: str,
    location: LocationUpdate,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    vehicle = next((v for v in _DEMO_VEHICLES if v["id"] == vehicle_id), None)
    if not vehicle:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Vehicle {vehicle_id} not found")

    vehicle["latitude"] = location.latitude
    vehicle["longitude"] = location.longitude
    vehicle["speed_kmh"] = location.speed_kmh
    vehicle["heading"] = location.heading
    vehicle["last_location_update"] = datetime.utcnow().isoformat() + "Z"
    return VehicleResponse(**vehicle)


@router.put("/{vehicle_id}/status", response_model=VehicleResponse)
async def update_vehicle_status(
    vehicle_id: str,
    update: StatusUpdate,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    vehicle = next((v for v in _DEMO_VEHICLES if v["id"] == vehicle_id), None)
    if not vehicle:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Vehicle {vehicle_id} not found")

    vehicle["status"] = update.status
    return VehicleResponse(**vehicle)
