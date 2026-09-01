"""
NERRO ML — Travel Delay Regressor (Model B)
Predicts estimated travel time and expected delay in minutes.
Trains 5 algorithms and picks the best by RMSE:
  1. Random Forest Regressor
  2. Gradient Boosting Regressor
  3. Linear Regression
  4. XGBoost Regressor
  5. Ridge Regression (L2 regularized linear)
"""

from pathlib import Path
from typing import Optional

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import mean_absolute_error, root_mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from xgboost import XGBRegressor

from app.config import DELAY_MODEL_PATH
from app.data.preprocessor import DELAY_FEATURES


class DelayRegressor:
    """Wrapper around the trained travel-delay regression model.

    Compares 5 regression algorithms during training and keeps the best.
    """

    def __init__(self, model=None, model_path: Optional[Path] = None):
        self.model = model
        self._path = model_path or DELAY_MODEL_PATH
        if self.model is None and self._path.exists():
            self.load()

    # ── Training ──────────────────────────────────────────────────

    def train(self, df: pd.DataFrame, target_col: str = "delay_minutes"):
        """Train 5 regressors and keep the one with lowest RMSE.

        Algorithms compared:
            1. Random Forest Regressor
            2. Gradient Boosting Regressor
            3. Linear Regression
            4. XGBoost Regressor
            5. Ridge Regression (L2 regularized linear)
        """
        X = df[DELAY_FEATURES]
        y = df[target_col]

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42,
        )

        # ── Define all candidate models ───────────────────────────
        candidates = {
            "RandomForest": RandomForestRegressor(
                n_estimators=200, max_depth=14, min_samples_leaf=5,
                random_state=42, n_jobs=-1,
            ),
            "GradientBoosting": GradientBoostingRegressor(
                n_estimators=200, max_depth=6, learning_rate=0.1,
                random_state=42,
            ),
            "LinearRegression": Pipeline([
                ("scaler", StandardScaler()),
                ("lr", LinearRegression()),
            ]),
            "XGBoost": XGBRegressor(
                n_estimators=200, max_depth=6, learning_rate=0.1,
                random_state=42, n_jobs=-1,
            ),
            "Ridge": Pipeline([
                ("scaler", StandardScaler()),
                ("ridge", Ridge(alpha=1.0, random_state=42)),
            ]),
        }

        # ── Train and evaluate each model ─────────────────────────
        results = {}
        for name, model in candidates.items():
            model.fit(X_train, y_train)
            y_pred = model.predict(X_test)
            rmse = root_mean_squared_error(y_test, y_pred)
            mae = mean_absolute_error(y_test, y_pred)
            r2 = r2_score(y_test, y_pred)
            results[name] = {
                "model": model,
                "rmse": round(rmse, 2),
                "mae": round(mae, 2),
                "r2": round(r2, 4),
            }

        # ── Pick the best model by lowest RMSE ────────────────────
        best_name = min(results, key=lambda k: results[k]["rmse"])
        self.model = results[best_name]["model"]

        # ── Build leaderboard ─────────────────────────────────────
        leaderboard = []
        for rank, (name, res) in enumerate(
            sorted(results.items(), key=lambda x: x[1]["rmse"]), start=1
        ):
            leaderboard.append({
                "rank": rank,
                "model": name,
                "rmse": res["rmse"],
                "mae": res["mae"],
                "r2": res["r2"],
                "selected": name == best_name,
            })

        # ── Feature importances ───────────────────────────────────
        feat_imp = self._extract_feature_importances()

        report = {
            "best_model": best_name,
            "rmse": results[best_name]["rmse"],
            "mae": results[best_name]["mae"],
            "r2": results[best_name]["r2"],
            "leaderboard": leaderboard,
            "feature_importances": feat_imp,
        }
        return report

    def _extract_feature_importances(self) -> dict:
        """Extract feature importances from the best model."""
        model = self.model

        # If it's a Pipeline, get the last step
        if hasattr(model, "named_steps"):
            estimator = list(model.named_steps.values())[-1]
        else:
            estimator = model

        if hasattr(estimator, "feature_importances_"):
            return dict(zip(
                DELAY_FEATURES,
                np.round(estimator.feature_importances_, 4).tolist(),
            ))
        elif hasattr(estimator, "coef_"):
            coefs = np.abs(estimator.coef_)
            normalized = coefs / coefs.sum() if coefs.sum() > 0 else coefs
            return dict(zip(
                DELAY_FEATURES,
                np.round(normalized, 4).tolist(),
            ))
        else:
            return {f: 0.0 for f in DELAY_FEATURES}

    # ── Prediction ────────────────────────────────────────────────

    def predict_delay(self, X: pd.DataFrame) -> list[dict]:
        """Predict delay and estimated total travel time for each row.

        Returns list of dicts with:
            predicted_delay_minutes, estimated_travel_minutes
        """
        if self.model is None:
            raise RuntimeError("Model not loaded. Call train() or load() first.")

        delays = self.model.predict(X)
        results = []
        for i, delay in enumerate(delays):
            hist_avg = float(X.iloc[i].get("historical_avg_minutes", 30))
            total = hist_avg + max(0, float(delay))
            results.append({
                "predicted_delay_minutes": round(max(0, float(delay)), 1),
                "estimated_travel_minutes": round(total, 1),
            })
        return results

    # ── Persistence ───────────────────────────────────────────────

    def save(self, path: Optional[Path] = None):
        p = path or self._path
        p.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.model, p)
        print(f"Delay model saved -> {p}")

    def load(self, path: Optional[Path] = None):
        p = path or self._path
        self.model = joblib.load(p)
        print(f"Delay model loaded <- {p}")
