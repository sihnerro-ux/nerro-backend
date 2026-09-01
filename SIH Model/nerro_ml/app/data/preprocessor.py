"""
NERRO ML — Feature Preprocessor
Transforms raw data into model-ready feature vectors.
"""

import numpy as np
import pandas as pd


# ── Feature names (canonical order) ───────────────────────────────

RISK_FEATURES = [
    "rainfall_mm",
    "slope_deg",
    "elevation_m",
    "past_incident_count",
    "is_monsoon",
    "weather_severity",
    "road_condition",
    "traffic_density",
]

DELAY_FEATURES = [
    "distance_km",
    "traffic_density",
    "rainfall_mm",
    "road_condition",
    "historical_avg_minutes",
    "active_incidents",
]


# ── Preprocessing helpers ─────────────────────────────────────────

def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def preprocess_risk_features(data: dict) -> pd.DataFrame:
    """Build a single-row DataFrame with the canonical risk feature order.

    Accepts a dict with at least the keys in RISK_FEATURES.
    Missing keys get sensible defaults.  Values are clamped to valid
    ranges so the model never sees out-of-distribution garbage.
    """
    row = {
        "rainfall_mm":        _clamp(float(data.get("rainfall_mm", 0)), 0, 1000),
        "slope_deg":          _clamp(float(data.get("slope_deg", 0)), 0, 90),
        "elevation_m":        _clamp(float(data.get("elevation_m", 0)), 0, 9000),
        "past_incident_count": max(0, int(data.get("past_incident_count", 0))),
        "is_monsoon":         int(bool(data.get("is_monsoon", 0))),
        "weather_severity":   _clamp(int(data.get("weather_severity", 0)), 0, 5),
        "road_condition":     _clamp(int(data.get("road_condition", 1)), 1, 3),
        "traffic_density":    _clamp(float(data.get("traffic_density", 0.3)), 0, 1),
    }
    return pd.DataFrame([row], columns=RISK_FEATURES)


def preprocess_delay_features(data: dict) -> pd.DataFrame:
    """Build a single-row DataFrame with the canonical delay feature order.

    Accepts a dict with at least the keys in DELAY_FEATURES.
    Missing keys get sensible defaults.
    """
    row = {
        "distance_km":           max(0.1, float(data.get("distance_km", 10))),
        "traffic_density":       _clamp(float(data.get("traffic_density", 0.3)), 0, 1),
        "rainfall_mm":           _clamp(float(data.get("rainfall_mm", 0)), 0, 1000),
        "road_condition":        _clamp(int(data.get("road_condition", 1)), 1, 3),
        "historical_avg_minutes": max(0, float(data.get("historical_avg_minutes", 30))),
        "active_incidents":      max(0, int(data.get("active_incidents", 0))),
    }
    return pd.DataFrame([row], columns=DELAY_FEATURES)


def preprocess_risk_batch(records: list[dict]) -> pd.DataFrame:
    """Preprocess a list of dicts into a multi-row risk feature DataFrame."""
    rows = [preprocess_risk_features(r).iloc[0] for r in records]
    return pd.DataFrame(rows, columns=RISK_FEATURES)


def preprocess_delay_batch(records: list[dict]) -> pd.DataFrame:
    """Preprocess a list of dicts into a multi-row delay feature DataFrame."""
    rows = [preprocess_delay_features(r).iloc[0] for r in records]
    return pd.DataFrame(rows, columns=DELAY_FEATURES)
