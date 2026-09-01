"""
NERRO ML — Route Disruption Risk Classifier (Model A)
Trains 5 algorithms and auto-selects the best performer:
  1. Random Forest
  2. XGBoost
  3. Logistic Regression
  4. Gradient Boosting
  5. Support Vector Machine (SVM)
"""

from pathlib import Path
from typing import Optional

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.svm import SVC
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
)
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

from app.config import RISK_MODEL_PATH, RISK_THRESHOLDS
from app.data.preprocessor import RISK_FEATURES


class RiskClassifier:
    """Wrapper around the trained disruption-risk classifier.

    Compares 5 algorithms during training and keeps the best one.
    """

    def __init__(self, model=None, model_path: Optional[Path] = None):
        self.model = model
        self._path = model_path or RISK_MODEL_PATH
        if self.model is None and self._path.exists():
            self.load()

    # ── Training ──────────────────────────────────────────────────

    def train(self, df: pd.DataFrame, target_col: str = "disrupted"):
        """Train 5 classifiers and keep the best one (by macro-F1).

        Algorithms compared:
            1. Random Forest
            2. XGBoost
            3. Logistic Regression (with feature scaling)
            4. Gradient Boosting
            5. SVM with RBF kernel (with feature scaling)
        """
        X = df[RISK_FEATURES]
        y = df[target_col]

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y,
        )

        # ── Define all candidate models ───────────────────────────
        candidates = {
            "RandomForest": RandomForestClassifier(
                n_estimators=200, max_depth=12, min_samples_leaf=5,
                random_state=42, n_jobs=-1,
            ),
            "XGBoost": XGBClassifier(
                n_estimators=200, max_depth=6, learning_rate=0.1,
                eval_metric="logloss", random_state=42, n_jobs=-1,
            ),
            "LogisticRegression": Pipeline([
                ("scaler", StandardScaler()),
                ("lr", LogisticRegression(
                    max_iter=1000, random_state=42, C=1.0,
                    solver="lbfgs",
                )),
            ]),
            "GradientBoosting": GradientBoostingClassifier(
                n_estimators=200, max_depth=5, learning_rate=0.1,
                random_state=42,
            ),
            "SVM": Pipeline([
                ("scaler", StandardScaler()),
                ("svm", SVC(
                    kernel="rbf", C=1.0, gamma="scale",
                    probability=True, random_state=42,
                )),
            ]),
        }

        # ── Train and evaluate each model ─────────────────────────
        results = {}
        for name, model in candidates.items():
            model.fit(X_train, y_train)
            y_pred = model.predict(X_test)
            f1 = f1_score(y_test, y_pred, average="macro")
            acc = accuracy_score(y_test, y_pred)
            results[name] = {
                "model": model,
                "f1": round(f1, 4),
                "accuracy": round(acc, 4),
            }

        # ── Pick the best model by macro-F1 ───────────────────────
        best_name = max(results, key=lambda k: results[k]["f1"])
        self.model = results[best_name]["model"]

        # ── Build leaderboard ─────────────────────────────────────
        leaderboard = []
        for rank, (name, res) in enumerate(
            sorted(results.items(), key=lambda x: -x[1]["f1"]), start=1
        ):
            leaderboard.append({
                "rank": rank,
                "model": name,
                "macro_f1": res["f1"],
                "accuracy": res["accuracy"],
                "selected": name == best_name,
            })

        # ── Detailed report for the best model ────────────────────
        y_pred = self.model.predict(X_test)

        # Feature importances (not all models expose them the same way)
        feat_imp = self._extract_feature_importances()

        report = {
            "best_model": best_name,
            "accuracy": results[best_name]["accuracy"],
            "macro_f1": results[best_name]["f1"],
            "leaderboard": leaderboard,
            "confusion_matrix": confusion_matrix(y_test, y_pred).tolist(),
            "classification_report": classification_report(y_test, y_pred),
            "feature_importances": feat_imp,
        }
        return report

    def _extract_feature_importances(self) -> dict:
        """Extract feature importances from the best model.

        Works for tree-based models and linear models alike.
        """
        model = self.model

        # If it's a Pipeline, get the last step
        if hasattr(model, "named_steps"):
            # Pipeline — get the actual estimator (last step)
            estimator = list(model.named_steps.values())[-1]
        else:
            estimator = model

        if hasattr(estimator, "feature_importances_"):
            # Tree-based models (RF, XGBoost, GradientBoosting)
            return dict(zip(
                RISK_FEATURES,
                np.round(estimator.feature_importances_, 4).tolist(),
            ))
        elif hasattr(estimator, "coef_"):
            # Linear models (LogisticRegression, SVM with linear kernel)
            # Use absolute coefficient values as importance proxy
            coefs = np.abs(estimator.coef_[0]) if estimator.coef_.ndim > 1 else np.abs(estimator.coef_)
            normalized = coefs / coefs.sum() if coefs.sum() > 0 else coefs
            return dict(zip(
                RISK_FEATURES,
                np.round(normalized, 4).tolist(),
            ))
        else:
            return {f: 0.0 for f in RISK_FEATURES}

    # ── Prediction ────────────────────────────────────────────────

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Return probability of disruption (class 1) for each row."""
        if self.model is None:
            raise RuntimeError("Model not loaded. Call train() or load() first.")
        return self.model.predict_proba(X)[:, 1]

    def predict_risk(self, X: pd.DataFrame) -> list[dict]:
        """Return risk_score + risk_level for each row."""
        probs = self.predict_proba(X)
        results = []
        for p in probs:
            level = self._score_to_level(float(p))
            results.append({"risk_score": round(float(p), 4), "risk_level": level})
        return results

    @staticmethod
    def _score_to_level(score: float) -> str:
        if score < RISK_THRESHOLDS["LOW"]:
            return "LOW"
        if score < RISK_THRESHOLDS["MEDIUM"]:
            return "MEDIUM"
        if score < RISK_THRESHOLDS["HIGH"]:
            return "HIGH"
        return "BLOCKED"

    # ── Persistence ───────────────────────────────────────────────

    def save(self, path: Optional[Path] = None):
        p = path or self._path
        p.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.model, p)
        print(f"Risk model saved -> {p}")

    def load(self, path: Optional[Path] = None):
        p = path or self._path
        self.model = joblib.load(p)
        print(f"Risk model loaded <- {p}")
