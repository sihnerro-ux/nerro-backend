"""
NERRO ML — Data Collector
Fetches weather, rainfall, and elevation data from free public APIs.
Uses local file caching to avoid redundant network calls.
"""

import json
import os
import time
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

from app.config import DATA_DIR, NER_TOWNS


# ── Weather & Rainfall ────────────────────────────────────────────

def get_rainfall(lat: float, lon: float,
                 start_date: str = "2024-06-01",
                 end_date: str = "2024-06-30") -> pd.DataFrame:
    """Fetch daily rainfall from Open-Meteo archive API."""
    url = (
        f"https://archive-api.open-meteo.com/v1/archive?"
        f"latitude={lat}&longitude={lon}"
        f"&start_date={start_date}&end_date={end_date}"
        f"&daily=precipitation_sum&timezone=Asia/Kolkata"
    )
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.json()["daily"]
    return pd.DataFrame({
        "date": data["time"],
        "rainfall_mm": data["precipitation_sum"],
    })


def get_current_weather(lat: float, lon: float) -> dict:
    """Fetch current weather conditions from Open-Meteo forecast API.

    Returns dict with keys:
        temperature_c, wind_speed_kmh, precipitation_mm, weather_code
    """
    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}"
        f"&current=temperature_2m,wind_speed_10m,precipitation,weather_code"
        f"&timezone=Asia/Kolkata"
    )
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    current = resp.json()["current"]
    return {
        "temperature_c": current.get("temperature_2m", 25.0),
        "wind_speed_kmh": current.get("wind_speed_10m", 0.0),
        "precipitation_mm": current.get("precipitation", 0.0),
        "weather_code": current.get("weather_code", 0),
    }


def weather_code_to_severity(code: int) -> int:
    """Convert WMO weather code to a severity scale 0-5.

    0 = clear, 1 = mild, 2 = moderate rain, 3 = heavy rain,
    4 = storm/thunderstorm, 5 = extreme (hurricane, hail).
    """
    if code <= 3:
        return 0        # clear / partly cloudy
    if code <= 48:
        return 1        # fog / depositing rime fog
    if code <= 55:
        return 2        # drizzle
    if code <= 65:
        return 3        # rain (slight → heavy)
    if code <= 77:
        return 3        # snow / ice pellets
    if code <= 82:
        return 4        # rain showers (violent)
    if code <= 99:
        return 5        # thunderstorm / hail
    return 0


# ── Elevation ─────────────────────────────────────────────────────

def get_elevation(lat: float, lon: float) -> float:
    """Fetch elevation (metres) from Open Elevation API."""
    url = f"https://api.open-elevation.com/api/v1/lookup?locations={lat},{lon}"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return float(resp.json()["results"][0]["elevation"])


# ── Caching wrappers ──────────────────────────────────────────────

def get_rainfall_cached(name: str, lat: float, lon: float) -> Optional[pd.DataFrame]:
    """Return cached rainfall CSV or fetch + cache it."""
    path = DATA_DIR / f"cache_rainfall_{name}.csv"
    if path.exists():
        return pd.read_csv(path)
    try:
        df = get_rainfall(lat, lon)
        df.to_csv(path, index=False)
        return df
    except Exception as exc:
        print(f"[rainfall] Failed for {name}: {exc}")
        return None


def get_elevation_cached(name: str, lat: float, lon: float) -> Optional[float]:
    """Return cached elevation or fetch + cache it."""
    path = DATA_DIR / f"cache_elev_{name}.json"
    if path.exists():
        with open(path, "r") as fh:
            return json.load(fh)["elevation"]
    try:
        elev = get_elevation(lat, lon)
        with open(path, "w") as fh:
            json.dump({"elevation": elev}, fh)
        return elev
    except Exception as exc:
        print(f"[elevation] Failed for {name}: {exc}")
        return None


def fetch_all_town_data(sleep_seconds: float = 1.0) -> tuple[dict, dict]:
    """Fetch rainfall and elevation for every NER town (with caching).

    Returns:
        (rainfall_dict, elevation_dict)
    """
    rainfall: dict[str, Optional[pd.DataFrame]] = {}
    elevations: dict[str, Optional[float]] = {}

    for name, (lat, lon) in NER_TOWNS.items():
        rainfall[name] = get_rainfall_cached(name, lat, lon)
        elevations[name] = get_elevation_cached(name, lat, lon)
        time.sleep(sleep_seconds)
        print(f"Done: {name}")

    return rainfall, elevations
