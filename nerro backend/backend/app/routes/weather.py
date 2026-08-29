# ============================================================
# NERRO - Weather Routes (routes/weather.py)
# Endpoints      : GET /api/weather/current, /forecast, /logistics-impact
# Purpose        : Current weather, 7-day forecast and logistics impact per location.
# TEAM NOTE      : *** REAL-TIME DATA INTEGRATION POINT ***
#                  Demo cache lives here; weather_service.py has the live
#                  Open-Meteo integration - point these endpoints at it for real data.
# ============================================================
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.routes.auth import get_current_user

router = APIRouter(prefix="/api/weather", tags=["Weather"])

# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------


class CurrentWeather(BaseModel):
    location: str
    latitude: float
    longitude: float
    temperature_c: float
    feels_like_c: float
    humidity_percent: float
    precipitation_mm: float
    precipitation_type: str
    wind_speed_kmh: float
    wind_direction_deg: float
    visibility_km: float
    cloud_cover_percent: float
    condition: str
    uv_index: float
    source: str


class ForecastDay(BaseModel):
    date: str
    temp_max_c: float
    temp_min_c: float
    precipitation_mm: float
    precipitation_probability: float
    wind_speed_kmh: float
    condition: str
    humidity_percent: float


class ForecastResponse(BaseModel):
    location: str
    latitude: float
    longitude: float
    forecast: list[ForecastDay]
    source: str


class LogisticsImpact(BaseModel):
    location: str
    latitude: float
    longitude: float
    impact_level: str
    road_condition_impact: str
    visibility_impact: str
    flood_risk: str
    landslide_risk: str
    recommended_actions: list[str]
    affected_segments: list[dict]
    data_source: str
    data_note: str


# ---------------------------------------------------------------------------
# Demo Data
# ---------------------------------------------------------------------------

_DEMO_CURRENT_WEATHER: dict = {
    "Guwahati": {
        "location": "Guwahati, Assam",
        "latitude": 26.1445,
        "longitude": 91.7362,
        "temperature_c": 22.5,
        "feels_like_c": 24.1,
        "humidity_percent": 85.0,
        "precipitation_mm": 12.3,
        "precipitation_type": "rain",
        "wind_speed_kmh": 18.0,
        "wind_direction_deg": 225.0,
        "visibility_km": 6.5,
        "cloud_cover_percent": 80,
        "condition": "Moderate Rain",
        "uv_index": 3.0,
        "source": "Open-Meteo API (demo)",
    },
    "Tawang": {
        "location": "Tawang, Arunachal Pradesh",
        "latitude": 27.5869,
        "longitude": 91.8593,
        "temperature_c": 8.2,
        "feels_like_c": 3.5,
        "humidity_percent": 95.0,
        "precipitation_mm": 35.7,
        "precipitation_type": "snow",
        "wind_speed_kmh": 42.0,
        "wind_direction_deg": 310.0,
        "visibility_km": 1.2,
        "cloud_cover_percent": 95,
        "condition": "Heavy Snow",
        "uv_index": 1.5,
        "source": "Open-Meteo API (demo)",
    },
    "Shillong": {
        "location": "Shillong, Meghalaya",
        "latitude": 25.5788,
        "longitude": 91.8933,
        "temperature_c": 15.8,
        "feels_like_c": 14.2,
        "humidity_percent": 90.0,
        "precipitation_mm": 28.1,
        "precipitation_type": "rain",
        "wind_speed_kmh": 25.0,
        "wind_direction_deg": 180.0,
        "visibility_km": 3.0,
        "cloud_cover_percent": 88,
        "condition": "Heavy Rain",
        "uv_index": 2.0,
        "source": "Open-Meteo API (demo)",
    },
}

_DEMO_FORECAST: list[dict] = [
    {"date": "2026-01-21", "temp_max_c": 24.0, "temp_min_c": 18.0, "precipitation_mm": 35.0, "precipitation_probability": 0.85, "wind_speed_kmh": 22.0, "condition": "Heavy Rain", "humidity_percent": 88},
    {"date": "2026-01-22", "temp_max_c": 22.0, "temp_min_c": 16.0, "precipitation_mm": 45.0, "precipitation_probability": 0.92, "wind_speed_kmh": 28.0, "condition": "Heavy Rain", "humidity_percent": 92},
    {"date": "2026-01-23", "temp_max_c": 20.0, "temp_min_c": 15.0, "precipitation_mm": 20.0, "precipitation_probability": 0.70, "wind_speed_kmh": 15.0, "condition": "Moderate Rain", "humidity_percent": 85},
    {"date": "2026-01-24", "temp_max_c": 23.0, "temp_min_c": 17.0, "precipitation_mm": 8.0, "precipitation_probability": 0.45, "wind_speed_kmh": 12.0, "condition": "Light Rain", "humidity_percent": 78},
    {"date": "2026-01-25", "temp_max_c": 25.0, "temp_min_c": 18.0, "precipitation_mm": 2.0, "precipitation_probability": 0.20, "wind_speed_kmh": 10.0, "condition": "Partly Cloudy", "humidity_percent": 70},
    {"date": "2026-01-26", "temp_max_c": 26.0, "temp_min_c": 19.0, "precipitation_mm": 0.0, "precipitation_probability": 0.05, "wind_speed_kmh": 8.0, "condition": "Clear", "humidity_percent": 65},
    {"date": "2026-01-27", "temp_max_c": 25.0, "temp_min_c": 18.0, "precipitation_mm": 5.0, "precipitation_probability": 0.35, "wind_speed_kmh": 14.0, "condition": "Partly Cloudy", "humidity_percent": 72},
]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/current", response_model=CurrentWeather)
async def get_current_weather(
    latitude: float = Query(26.1445, ge=-90, le=90),
    longitude: float = Query(91.7362, ge=-180, le=180),
    location: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    if location and location in _DEMO_CURRENT_WEATHER:
        return CurrentWeather(**_DEMO_CURRENT_WEATHER[location])

    closest_name = min(
        _DEMO_CURRENT_WEATHER.keys(),
        key=lambda n: abs(_DEMO_CURRENT_WEATHER[n]["latitude"] - latitude)
        + abs(_DEMO_CURRENT_WEATHER[n]["longitude"] - longitude),
    )
    return CurrentWeather(**_DEMO_CURRENT_WEATHER[closest_name])


@router.get("/forecast", response_model=ForecastResponse)
async def get_forecast(
    latitude: float = Query(26.1445, ge=-90, le=90),
    longitude: float = Query(91.7362, ge=-180, le=180),
    location: Optional[str] = Query(None),
    days: int = Query(7, ge=1, le=16),
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    return ForecastResponse(
        location=location or f"Location ({latitude}, {longitude})",
        latitude=latitude,
        longitude=longitude,
        forecast=[ForecastDay(**d) for d in _DEMO_FORECAST[:days]],
        source="Open-Meteo API (demo data)",
    )


@router.get("/logistics-impact", response_model=LogisticsImpact)
async def get_logistics_impact(
    latitude: float = Query(26.1445, ge=-90, le=90),
    longitude: float = Query(91.7362, ge=-180, le=180),
    location: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    impact_level = "moderate"
    road_impact = "Wet roads reduce traction. Moderate caution advised."
    visibility_impact = "Visibility reduced to 3-6km in rainy areas."
    flood_risk = "moderate"
    landslide_risk = "low"
    actions = [
        "Reduce speed on wet roads, especially in hilly terrain",
        "Carry emergency supplies (water, food, first-aid)",
        "Monitor IMD weather alerts for updates",
        "Avoid travel during peak rainfall hours (2PM-6PM)",
    ]
    affected = [
        {"segment": "Sela Pass section", "risk": "high", "reason": "Heavy snow, reduced visibility"},
        {"segment": "Brahmaputra floodplain", "risk": "moderate", "reason": "Waterlogging possible"},
    ]

    if "tawang" in (location or "").lower():
        impact_level = "severe"
        flood_risk = "high"
        landslide_risk = "high"
        actions.insert(0, "AVOID non-essential travel to Tawang")
        affected[0]["risk"] = "critical"

    return LogisticsImpact(
        location=location or f"Area ({latitude}, {longitude})",
        latitude=latitude,
        longitude=longitude,
        impact_level=impact_level,
        road_condition_impact=road_impact,
        visibility_impact=visibility_impact,
        flood_risk=flood_risk,
        landslide_risk=landslide_risk,
        recommended_actions=actions,
        affected_segments=affected,
        data_source="Open-Meteo + NERRO heuristic model",
        data_note="Demo data. Integrate real-time Open-Meteo API for production.",
    )
