"""
NERRO ML Intelligence Engine — Configuration
"""
import os
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
TRAINED_MODELS_DIR = BASE_DIR / "trained_models"
DATA_DIR = BASE_DIR / "data"

TRAINED_MODELS_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)

# ── Model file paths ──────────────────────────────────────────────
RISK_MODEL_PATH = TRAINED_MODELS_DIR / "risk_classifier.pkl"
DELAY_MODEL_PATH = TRAINED_MODELS_DIR / "delay_regressor.pkl"

# ── API settings ──────────────────────────────────────────────────
API_HOST = os.getenv("NERRO_HOST", "0.0.0.0")
API_PORT = int(os.getenv("NERRO_PORT", "8000"))

# ── NER Towns ─────────────────────────────────────────────────────
NER_TOWNS = {
    # Assam
    "Guwahati":      (26.1445, 91.7362),
    "Dibrugarh":     (27.4728, 94.9120),
    "Silchar":       (24.8333, 92.7789),
    # Meghalaya
    "Shillong":      (25.5788, 91.8933),
    "Cherrapunji":   (25.3000, 91.7000),
    "Tura":          (25.5138, 90.2039),
    # Arunachal Pradesh
    "Itanagar":      (27.0844, 93.6053),
    "Tawang":        (27.5860, 91.8594),
    # Nagaland
    "Kohima":        (25.6751, 94.1086),
    "Dimapur":       (25.9091, 93.7267),
    # Manipur
    "Imphal":        (24.8170, 93.9368),
    "Churachandpur": (24.3333, 93.6833),
    # Mizoram
    "Aizawl":        (23.7271, 92.7176),
    "Lunglei":       (22.8879, 92.7320),
    # Tripura
    "Agartala":      (23.8315, 91.2868),
    "Udaipur":       (23.5333, 91.4833),
    # Sikkim
    "Gangtok":       (27.3389, 88.6065),
    "Namchi":        (27.1660, 88.3639),
}

# ── Risk thresholds ───────────────────────────────────────────────
RISK_THRESHOLDS = {
    "LOW":     0.25,
    "MEDIUM":  0.55,
    "HIGH":    0.80,
    # above 0.80 → BLOCKED
}

# ── Route cost weights ────────────────────────────────────────────
ROUTE_COST_WEIGHTS = {
    "distance":  1.0,
    "delay":     2.0,
    "risk":      3.0,
    "blockage_penalty": 1000.0,
}
