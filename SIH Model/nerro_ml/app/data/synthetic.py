"""
NERRO ML — Synthetic Data Generator
Creates realistic training data for both risk and delay models.
Uses correlated features so the models learn meaningful patterns.
"""

import math
import numpy as np
import pandas as pd

from app.config import NER_TOWNS
from app.data.preprocessor import RISK_FEATURES, DELAY_FEATURES


# ── Road network edges (synthetic but geographically plausible) ───
# Each tuple: (town_a, town_b, distance_km, road_type)
# road_type: 1=national_highway, 2=state_highway, 3=district_road

NER_ROAD_SEGMENTS = [
    # Assam internal
    ("Guwahati", "Dibrugarh", 475, 1),
    ("Guwahati", "Silchar", 340, 1),
    ("Guwahati", "Shillong", 100, 1),
    ("Guwahati", "Tura", 220, 2),
    ("Dibrugarh", "Itanagar", 260, 2),
    ("Dibrugarh", "Dimapur", 185, 1),
    # Meghalaya
    ("Shillong", "Cherrapunji", 55, 2),
    ("Shillong", "Tura", 310, 2),
    # Arunachal Pradesh
    ("Itanagar", "Tawang", 440, 3),
    # Nagaland
    ("Dimapur", "Kohima", 74, 1),
    ("Kohima", "Imphal", 215, 1),
    # Manipur
    ("Imphal", "Churachandpur", 63, 2),
    ("Imphal", "Silchar", 270, 2),
    # Mizoram
    ("Silchar", "Aizawl", 185, 1),
    ("Aizawl", "Lunglei", 170, 2),
    # Tripura
    ("Silchar", "Agartala", 330, 1),
    ("Agartala", "Udaipur", 55, 2),
    # Sikkim
    ("Guwahati", "Gangtok", 560, 1),
    ("Gangtok", "Namchi", 80, 2),
    # Cross-state connectors
    ("Guwahati", "Agartala", 590, 1),
    ("Shillong", "Silchar", 320, 2),
    ("Tawang", "Gangtok", 480, 3),
]

# Pre-computed elevations (metres) — sensible estimates for NER
TOWN_ELEVATIONS = {
    "Guwahati": 50, "Dibrugarh": 110, "Silchar": 30,
    "Shillong": 1496, "Cherrapunji": 1484, "Tura": 350,
    "Itanagar": 320, "Tawang": 3048,
    "Kohima": 1444, "Dimapur": 194,
    "Imphal": 786, "Churachandpur": 914,
    "Aizawl": 1132, "Lunglei": 880,
    "Agartala": 13, "Udaipur": 30,
    "Gangtok": 1650, "Namchi": 1320,
}


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    """Great-circle distance between two lat/lon points in km."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _slope_between(town_a: str, town_b: str, distance_km: float) -> float:
    """Approximate average slope in degrees between two towns."""
    elev_a = TOWN_ELEVATIONS.get(town_a, 100)
    elev_b = TOWN_ELEVATIONS.get(town_b, 100)
    elev_diff = abs(elev_b - elev_a)
    if distance_km <= 0:
        return 0.0
    return math.degrees(math.atan(elev_diff / (distance_km * 1000)))


# ── Risk dataset generator ────────────────────────────────────────

def generate_risk_dataset(n_samples: int = 5000, seed: int = 42) -> pd.DataFrame:
    """Generate synthetic route-disruption training data.

    Features are correlated: high rainfall + steep slope + monsoon
    → higher probability of disruption.  Labels are generated from
    a logistic function so the boundary is smooth, not a hard quantile.
    """
    rng = np.random.RandomState(seed)

    # Base features
    rainfall_mm = rng.gamma(3, 20, n_samples)                    # 0–300+
    slope_deg = rng.uniform(0, 45, n_samples)                    # 0–45
    elevation_m = rng.uniform(10, 3100, n_samples)               # 10–3100
    past_incident_count = rng.poisson(1.5, n_samples)            # 0–8+
    is_monsoon = rng.binomial(1, 0.4, n_samples)                 # 0/1

    # During monsoon, rainfall tends to be heavier
    rainfall_mm = np.where(
        is_monsoon == 1,
        rainfall_mm * rng.uniform(1.3, 2.5, n_samples),
        rainfall_mm,
    )

    weather_severity = np.clip(
        (rainfall_mm / 60).astype(int) + rng.binomial(1, 0.2, n_samples),
        0, 5,
    )
    road_condition = rng.choice([1, 2, 3], n_samples, p=[0.4, 0.35, 0.25])
    traffic_density = rng.beta(2, 5, n_samples)  # skewed low

    # Logistic risk score
    z = (
        0.012 * rainfall_mm
        + 0.04  * slope_deg
        + 0.0005 * elevation_m
        + 0.35  * past_incident_count
        + 0.8   * is_monsoon
        + 0.3   * weather_severity
        + 0.25  * (road_condition - 1)
        + 0.4   * traffic_density
        - 4.5                            # shift so ~30-35% are positive
        + rng.normal(0, 0.8, n_samples)  # noise
    )
    prob = 1 / (1 + np.exp(-z))
    blocked = (prob > 0.5).astype(int)

    df = pd.DataFrame({
        "rainfall_mm": np.round(rainfall_mm, 1),
        "slope_deg": np.round(slope_deg, 2),
        "elevation_m": np.round(elevation_m, 1),
        "past_incident_count": past_incident_count,
        "is_monsoon": is_monsoon,
        "weather_severity": weather_severity,
        "road_condition": road_condition,
        "traffic_density": np.round(traffic_density, 3),
        "disrupted": blocked,
    })
    return df


# ── Delay dataset generator ───────────────────────────────────────

def generate_delay_dataset(n_samples: int = 5000, seed: int = 42) -> pd.DataFrame:
    """Generate synthetic travel-delay training data.

    Travel time is modelled as:
        base_time  = distance / avg_speed
        delay      = f(traffic, rainfall, road_condition, incidents)
    """
    rng = np.random.RandomState(seed)

    # Sample road segments
    seg_indices = rng.choice(len(NER_ROAD_SEGMENTS), n_samples)
    distances = np.array([NER_ROAD_SEGMENTS[i][2] for i in seg_indices], dtype=float)

    # Add jitter to distances (sub-routes)
    distances = distances * rng.uniform(0.3, 1.0, n_samples)

    traffic_density = rng.beta(2, 5, n_samples)
    rainfall_mm = rng.gamma(3, 20, n_samples)
    road_condition = rng.choice([1, 2, 3], n_samples, p=[0.4, 0.35, 0.25])
    active_incidents = rng.poisson(0.5, n_samples)

    # Historical average = distance / 40 kmh → hours → minutes
    historical_avg = (distances / 40) * 60

    # Actual travel time model
    speed_factor = (
        1.0
        - 0.3 * traffic_density             # traffic slows you down
        - 0.002 * rainfall_mm                # rain slows you down
        - 0.1 * (road_condition - 1)         # bad roads slow you down
    )
    speed_factor = np.clip(speed_factor, 0.15, 1.0)

    actual_minutes = (distances / (40 * speed_factor)) * 60
    incident_delay = active_incidents * rng.uniform(10, 40, n_samples)
    actual_minutes += incident_delay + rng.normal(0, 5, n_samples)
    actual_minutes = np.clip(actual_minutes, 5, 2000)

    delay_minutes = np.clip(actual_minutes - historical_avg, 0, 1500)

    df = pd.DataFrame({
        "distance_km": np.round(distances, 1),
        "traffic_density": np.round(traffic_density, 3),
        "rainfall_mm": np.round(rainfall_mm, 1),
        "road_condition": road_condition,
        "historical_avg_minutes": np.round(historical_avg, 1),
        "active_incidents": active_incidents,
        "actual_travel_minutes": np.round(actual_minutes, 1),
        "delay_minutes": np.round(delay_minutes, 1),
    })
    return df
