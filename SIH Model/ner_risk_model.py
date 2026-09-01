# ============================================================
# NER (North-East Region) Road-Block Risk Prediction Model
# ============================================================
# Prerequisites:
#   pip install pandas scikit-learn xgboost matplotlib requests joblib
# ============================================================

import os
import time
import json
import requests
import numpy as np
import pandas as pd
import joblib
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, confusion_matrix, classification_report
from xgboost import XGBClassifier

# ------------------------------------------------------------------
# 1. NER Towns with coordinates
# ------------------------------------------------------------------
ner_towns = {
    # Assam
    'Guwahati':      (26.1445, 91.7362),
    'Dibrugarh':     (27.4728, 94.9120),
    'Silchar':       (24.8333, 92.7789),
    # Meghalaya
    'Shillong':      (25.5788, 91.8933),
    'Cherrapunji':   (25.3000, 91.7000),
    'Tura':          (25.5138, 90.2039),
    # Arunachal Pradesh
    'Itanagar':      (27.0844, 93.6053),
    'Tawang':        (27.5860, 91.8594),
    # Nagaland
    'Kohima':        (25.6751, 94.1086),
    'Dimapur':       (25.9091, 93.7267),
    # Manipur
    'Imphal':        (24.8170, 93.9368),
    'Churachandpur': (24.3333, 93.6833),
    # Mizoram
    'Aizawl':        (23.7271, 92.7176),
    'Lunglei':       (22.8879, 92.7320),
    # Tripura
    'Agartala':      (23.8315, 91.2868),
    'Udaipur':       (23.5333, 91.4833),
    # Sikkim
    'Gangtok':       (27.3389, 88.6065),
    'Namchi':        (27.1660, 88.3639),
}

# ------------------------------------------------------------------
# 2. API helper functions (were previously undefined)
# ------------------------------------------------------------------

def get_rainfall(lat, lon):
    """Fetch daily rainfall from Open-Meteo archive for June 2024."""
    url = (
        f"https://archive-api.open-meteo.com/v1/archive?"
        f"latitude={lat}&longitude={lon}"
        f"&start_date=2024-06-01&end_date=2024-06-30"
        f"&daily=precipitation_sum&timezone=Asia/Kolkata"
    )
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.json()['daily']
    return pd.DataFrame({
        'date': data['time'],
        'rainfall_mm': data['precipitation_sum'],
    })


def get_elevation(lat, lon):
    """Fetch elevation (metres) from Open Elevation API."""
    url = f"https://api.open-elevation.com/api/v1/lookup?locations={lat},{lon}"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.json()['results'][0]['elevation']


# ------------------------------------------------------------------
# 3. Caching wrappers (fixed file-handle leaks)
# ------------------------------------------------------------------

def get_rainfall_cached(name, lat, lon):
    path = f'cache_rainfall_{name}.csv'
    if os.path.exists(path):
        return pd.read_csv(path)
    try:
        df = get_rainfall(lat, lon)
        df.to_csv(path, index=False)
        return df
    except Exception as e:
        print(f"[rainfall] Failed for {name}: {e}")
        return None


def get_elevation_cached(name, lat, lon):
    path = f'cache_elev_{name}.json'
    if os.path.exists(path):
        with open(path, 'r') as f:
            return json.load(f)['elevation']
    try:
        elev = get_elevation(lat, lon)
        with open(path, 'w') as f:
            json.dump({'elevation': elev}, f)
        return elev
    except Exception as e:
        print(f"[elevation] Failed for {name}: {e}")
        return None


# ------------------------------------------------------------------
# 4. Fetch real data for every NER town
# ------------------------------------------------------------------

rainfall = {}
elevations = {}
for name, (lat, lon) in ner_towns.items():
    rainfall[name] = get_rainfall_cached(name, lat, lon)
    elevations[name] = get_elevation_cached(name, lat, lon)
    time.sleep(1)  # be polite to free APIs — avoid rate-limit blocks
    print(f"Done: {name}")

# ------------------------------------------------------------------
# 5. Synthetic training data
#    (Replace this with real labelled data when available)
# ------------------------------------------------------------------

np.random.seed(42)
n = 2000
df = pd.DataFrame({
    'rainfall_mm':        np.random.gamma(2, 15, n),
    'slope_deg':          np.random.uniform(0, 45, n),
    'past_incident_count': np.random.poisson(1.2, n),
    'is_monsoon':         np.random.binomial(1, 0.35, n),
})

risk_score = (
    0.04 * df['rainfall_mm']
    + 0.05 * df['slope_deg']
    + 0.80 * df['past_incident_count']
    + 1.50 * df['is_monsoon']
    + np.random.normal(0, 1.5, n)
)
df['blocked'] = (risk_score > risk_score.quantile(0.75)).astype(int)

X = df[['rainfall_mm', 'slope_deg', 'past_incident_count', 'is_monsoon']]
y = df['blocked']

# ------------------------------------------------------------------
# 6. Train / test split
# ------------------------------------------------------------------

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42,
)

# ------------------------------------------------------------------
# 7. Random Forest
# ------------------------------------------------------------------

rf_model = RandomForestClassifier(n_estimators=100, random_state=42)
rf_model.fit(X_train, y_train)

y_pred_rf = rf_model.predict(X_test)

print("\n=== Random Forest ===")
print("Accuracy:", accuracy_score(y_test, y_pred_rf))
print(confusion_matrix(y_test, y_pred_rf))
print(classification_report(y_test, y_pred_rf))

# Feature importances
importances = pd.Series(rf_model.feature_importances_, index=X.columns)
print("\nFeature importances:")
print(importances.sort_values(ascending=False))

# Probability of "blocked"
risk_prob = rf_model.predict_proba(X_test)[:, 1]

# ------------------------------------------------------------------
# 8. XGBoost
# ------------------------------------------------------------------

xgb_model = XGBClassifier(n_estimators=100, random_state=42, eval_metric='logloss')
xgb_model.fit(X_train, y_train)

y_pred_xgb = xgb_model.predict(X_test)

print("\n=== XGBoost ===")
print("Accuracy:", accuracy_score(y_test, y_pred_xgb))

# ------------------------------------------------------------------
# 9. Save the model
# ------------------------------------------------------------------

joblib.dump(rf_model, 'ner_risk_model.pkl')
print("\nModel saved to ner_risk_model.pkl")

# To load later in your Flask / FastAPI backend:
# model = joblib.load('ner_risk_model.pkl')
