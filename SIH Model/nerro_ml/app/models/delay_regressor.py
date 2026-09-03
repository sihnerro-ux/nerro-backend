"""
NERRO ML — Travel Delay Regressor (Model B)

Predicts:
    1. Expected travel delay in minutes
    2. Estimated total travel time

Designed for a lightweight college hackathon prototype using
approximately 1,000 synthetic rows.

The model compares 5 regression algorithms and automatically
selects the best one based on lowest RMSE.

Algorithms:
    1. Random Forest Regressor
    2. Gradient Boosting Regressor
    3. Linear Regression
    4. XGBoost Regressor
    5. Ridge Regression
"""

from pathlib import Path
from typing import Optional

import joblib
import numpy as np
import pandas as pd

from sklearn.ensemble import (
    GradientBoostingRegressor,
    RandomForestRegressor,
)
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.metrics import (
    mean_absolute_error,
    root_mean_squared_error,
    r2_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from xgboost import XGBRegressor

from app.config import DELAY_MODEL_PATH
from app.data.preprocessor import DELAY_FEATURES


# ============================================================
# CONFIGURATION
# ============================================================

# 20% of the synthetic dataset will be used for testing.
#
# With 1,000 rows:
#   Training = ~800 rows
#   Testing  = ~200 rows
TEST_SIZE = 0.20

RANDOM_SEED = 42


# ============================================================
# DELAY REGRESSOR
# ============================================================

class DelayRegressor:
    """
    Travel-delay regression model wrapper.

    During training, five different regression algorithms
    are compared.

    The model with the LOWEST RMSE is selected automatically.
    """

    def __init__(
        self,
        model=None,
        model_path: Optional[Path] = None,
    ):
        self.model = model

        self._path = (
            model_path
            if model_path is not None
            else DELAY_MODEL_PATH
        )

        # Automatically load model if one already exists
        if self.model is None and self._path.exists():
            self.load()


    # ========================================================
    # TRAINING
    # ========================================================

    def train(
        self,
        df: pd.DataFrame,
        target_col: str = "delay_minutes",
    ):
        """
        Train five regressors and select the model
        with the lowest RMSE.

        Parameters
        ----------
        df:
            Training dataframe.

        target_col:
            Column containing actual delay in minutes.

        Returns
        -------
        dict
            Training report containing model performance,
            leaderboard and feature importances.
        """

        # ----------------------------------------------------
        # Basic validation
        # ----------------------------------------------------

        if df.empty:
            raise ValueError(
                "Training dataframe is empty."
            )

        missing_features = [
            feature
            for feature in DELAY_FEATURES
            if feature not in df.columns
        ]

        if missing_features:
            raise ValueError(
                f"Missing required features: "
                f"{missing_features}"
            )

        if target_col not in df.columns:
            raise ValueError(
                f"Target column '{target_col}' "
                f"not found in dataframe."
            )


        # ----------------------------------------------------
        # Prepare input features and target
        # ----------------------------------------------------

        X = df[DELAY_FEATURES]

        y = df[target_col]


        # ----------------------------------------------------
        # Train / Test Split
        # ----------------------------------------------------

        X_train, X_test, y_train, y_test = (
            train_test_split(
                X,
                y,
                test_size=TEST_SIZE,
                random_state=RANDOM_SEED,
            )
        )


        print(
            f"\nDelay dataset rows: {len(df)}"
        )

        print(
            f"Training rows: {len(X_train)}"
        )

        print(
            f"Testing rows: {len(X_test)}"
        )

        print(
            f"Features used: {len(DELAY_FEATURES)}"
        )


        # ====================================================
        # CANDIDATE MODELS
        # ====================================================

        # These settings are deliberately lightweight because
        # the hackathon dataset contains only ~1,000 rows.

        candidates = {

            # ------------------------------------------------
            # 1. Random Forest
            # ------------------------------------------------

            "RandomForest": RandomForestRegressor(
                n_estimators=100,
                max_depth=8,
                min_samples_leaf=3,
                random_state=RANDOM_SEED,
                n_jobs=-1,
            ),


            # ------------------------------------------------
            # 2. Gradient Boosting
            # ------------------------------------------------

            "GradientBoosting": GradientBoostingRegressor(
                n_estimators=100,
                max_depth=4,
                learning_rate=0.05,
                random_state=RANDOM_SEED,
            ),


            # ------------------------------------------------
            # 3. Linear Regression
            # ------------------------------------------------

            "LinearRegression": Pipeline([
                (
                    "scaler",
                    StandardScaler(),
                ),
                (
                    "linear_regression",
                    LinearRegression(),
                ),
            ]),


            # ------------------------------------------------
            # 4. XGBoost
            # ------------------------------------------------

            "XGBoost": XGBRegressor(
                n_estimators=100,
                max_depth=4,
                learning_rate=0.05,
                subsample=0.9,
                colsample_bytree=0.9,
                random_state=RANDOM_SEED,
                n_jobs=-1,
                objective="reg:squarederror",
            ),


            # ------------------------------------------------
            # 5. Ridge Regression
            # ------------------------------------------------

            "Ridge": Pipeline([
                (
                    "scaler",
                    StandardScaler(),
                ),
                (
                    "ridge",
                    Ridge(
                        alpha=1.0,
                    ),
                ),
            ]),
        }


        # ====================================================
        # TRAIN AND EVALUATE MODELS
        # ====================================================

        results = {}

        print("\nTraining delay models...")


        for name, model in candidates.items():

            print(
                f"   Training {name}..."
            )

            # Train model
            model.fit(
                X_train,
                y_train,
            )

            # Generate predictions
            y_pred = model.predict(
                X_test
            )


            # -----------------------------------------------
            # Evaluation metrics
            # -----------------------------------------------

            rmse = root_mean_squared_error(
                y_test,
                y_pred,
            )

            mae = mean_absolute_error(
                y_test,
                y_pred,
            )

            r2 = r2_score(
                y_test,
                y_pred,
            )


            results[name] = {
                "model": model,
                "rmse": round(
                    float(rmse),
                    2,
                ),
                "mae": round(
                    float(mae),
                    2,
                ),
                "r2": round(
                    float(r2),
                    4,
                ),
            }


            print(
                f"      RMSE: {rmse:.2f} | "
                f"MAE: {mae:.2f} | "
                f"R2: {r2:.4f}"
            )


        # ====================================================
        # SELECT BEST MODEL
        # ====================================================

        best_name = min(
            results,
            key=lambda name: (
                results[name]["rmse"]
            ),
        )


        self.model = (
            results[best_name]["model"]
        )


        print(
            f"\nBest delay model: "
            f"{best_name}"
        )


        # ====================================================
        # BUILD LEADERBOARD
        # ====================================================

        leaderboard = []


        sorted_results = sorted(
            results.items(),
            key=lambda item: (
                item[1]["rmse"]
            ),
        )


        for rank, (name, result) in enumerate(
            sorted_results,
            start=1,
        ):

            leaderboard.append({
                "rank": rank,
                "model": name,
                "rmse": result["rmse"],
                "mae": result["mae"],
                "r2": result["r2"],
                "selected": (
                    name == best_name
                ),
            })


        # ====================================================
        # FEATURE IMPORTANCE
        # ====================================================

        feature_importances = (
            self._extract_feature_importances()
        )


        # ====================================================
        # FINAL REPORT
        # ====================================================

        report = {

            "best_model": best_name,

            "rmse": (
                results[best_name]["rmse"]
            ),

            "mae": (
                results[best_name]["mae"]
            ),

            "r2": (
                results[best_name]["r2"]
            ),

            "training_rows": len(
                X_train
            ),

            "testing_rows": len(
                X_test
            ),

            "total_rows": len(
                df
            ),

            "feature_count": len(
                DELAY_FEATURES
            ),

            "leaderboard": leaderboard,

            "feature_importances": (
                feature_importances
            ),
        }


        return report


    # ========================================================
    # FEATURE IMPORTANCE
    # ========================================================

    def _extract_feature_importances(
        self,
    ) -> dict:
        """
        Extract feature importance values from
        the currently selected model.
        """

        model = self.model


        # Pipelines contain scaler + estimator.
        # We only need the final estimator.
        if hasattr(
            model,
            "named_steps",
        ):

            estimator = list(
                model.named_steps.values()
            )[-1]

        else:

            estimator = model


        # ----------------------------------------------------
        # Tree-based models
        # ----------------------------------------------------

        if hasattr(
            estimator,
            "feature_importances_",
        ):

            importance_values = (
                estimator.feature_importances_
            )

            return dict(
                zip(
                    DELAY_FEATURES,
                    np.round(
                        importance_values,
                        4,
                    ).tolist(),
                )
            )


        # ----------------------------------------------------
        # Linear models
        # ----------------------------------------------------

        elif hasattr(
            estimator,
            "coef_",
        ):

            coefficients = np.abs(
                estimator.coef_
            )

            coefficient_sum = (
                coefficients.sum()
            )


            if coefficient_sum > 0:

                normalized = (
                    coefficients
                    / coefficient_sum
                )

            else:

                normalized = coefficients


            return dict(
                zip(
                    DELAY_FEATURES,
                    np.round(
                        normalized,
                        4,
                    ).tolist(),
                )
            )


        # ----------------------------------------------------
        # Fallback
        # ----------------------------------------------------

        return {
            feature: 0.0
            for feature
            in DELAY_FEATURES
        }


    # ========================================================
    # PREDICTION
    # ========================================================

    def predict_delay(
        self,
        X: pd.DataFrame,
    ) -> list[dict]:
        """
        Predict delay and estimated travel time.

        Returns
        -------
        list[dict]

        Example:

        [
            {
                "predicted_delay_minutes": 12.4,
                "estimated_travel_minutes": 47.4
            }
        ]
        """

        if self.model is None:

            raise RuntimeError(
                "Delay model is not loaded. "
                "Call train() or load() first."
            )


        # Ensure prediction dataframe uses
        # exactly the expected feature order.
        missing_features = [
            feature
            for feature in DELAY_FEATURES
            if feature not in X.columns
        ]


        if missing_features:

            raise ValueError(
                f"Missing prediction features: "
                f"{missing_features}"
            )


        X_input = X[
            DELAY_FEATURES
        ]


        delays = self.model.predict(
            X_input
        )


        results = []


        for i, predicted_delay in enumerate(
            delays
        ):

            # Delay cannot realistically be negative.
            delay = max(
                0.0,
                float(predicted_delay),
            )


            # historical_avg_minutes represents
            # normal journey duration.
            historical_average = float(
                X_input.iloc[i].get(
                    "historical_avg_minutes",
                    30,
                )
            )


            estimated_total = (
                historical_average
                + delay
            )


            results.append({

                "predicted_delay_minutes":
                    round(
                        delay,
                        1,
                    ),

                "estimated_travel_minutes":
                    round(
                        estimated_total,
                        1,
                    ),
            })


        return results


    # ========================================================
    # SAVE MODEL
    # ========================================================

    def save(
        self,
        path: Optional[Path] = None,
    ):
        """
        Save trained model to disk.
        """

        if self.model is None:

            raise RuntimeError(
                "No trained model available to save."
            )


        save_path = (
            path
            if path is not None
            else self._path
        )


        save_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )


        joblib.dump(
            self.model,
            save_path,
        )


        print(
            f"Delay model saved -> "
            f"{save_path}"
        )


    # ========================================================
    # LOAD MODEL
    # ========================================================

    def load(
        self,
        path: Optional[Path] = None,
    ):
        """
        Load previously trained model from disk.
        """

        load_path = (
            path
            if path is not None
            else self._path
        )


        if not load_path.exists():

            raise FileNotFoundError(
                f"Delay model not found: "
                f"{load_path}"
            )


        self.model = joblib.load(
            load_path
        )


        print(
            f"Delay model loaded <- "
            f"{load_path}"
        )
