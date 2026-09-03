"""
NERRO ML — Model Training Script

Generates synthetic data, trains both ML models,
evaluates them, and saves the trained models/reports to disk.

For the hackathon prototype, we use 1,000 synthetic samples
for each dataset.

Usage:
    cd nerro_ml
    python -m scripts.train
"""

import sys
import json
from pathlib import Path


# ============================================================
# PROJECT SETUP
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Ensure project root is available so app.* imports work
sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================
# PROJECT IMPORTS
# ============================================================

from app.config import TRAINED_MODELS_DIR
from app.data.synthetic import (
    generate_risk_dataset,
    generate_delay_dataset,
)
from app.models.risk_classifier import RiskClassifier
from app.models.delay_regressor import DelayRegressor


# ============================================================
# CONFIGURATION
# ============================================================

# Number of synthetic rows generated PER dataset.
#
# Risk dataset  : 1,000 rows
# Delay dataset : 1,000 rows
#
# Total synthetic rows generated = 2,000
N_SAMPLES = 1000

# Fixed seed makes the generated data reproducible.
RANDOM_SEED = 42


# ============================================================
# MAIN TRAINING PIPELINE
# ============================================================

def main():

    print("=" * 60)
    print("              NERRO ML")
    print("          Model Training Pipeline")
    print("=" * 60)

    # ========================================================
    # 1. GENERATE SYNTHETIC DATA
    # ========================================================

    print(
        f"\n[DATA] Generating synthetic risk dataset "
        f"({N_SAMPLES} samples)..."
    )

    risk_df = generate_risk_dataset(
        n_samples=N_SAMPLES,
        seed=RANDOM_SEED,
    )

    print(f"   Dataset shape: {risk_df.shape}")

    print(
        f"   Disrupted ratio: "
        f"{risk_df['disrupted'].mean():.2%}"
    )


    print(
        f"\n[DATA] Generating synthetic delay dataset "
        f"({N_SAMPLES} samples)..."
    )

    delay_df = generate_delay_dataset(
        n_samples=N_SAMPLES,
        seed=RANDOM_SEED,
    )

    print(f"   Dataset shape: {delay_df.shape}")

    print(
        f"   Mean delay: "
        f"{delay_df['delay_minutes'].mean():.1f} min"
    )


    # ========================================================
    # 2. TRAIN RISK CLASSIFIER
    # ========================================================

    print("\n" + "-" * 60)

    print(
        " Training Route Disruption Risk Classifier "
        "(5 algorithms)..."
    )

    print("-" * 60)


    risk_model = RiskClassifier()

    risk_report = risk_model.train(
        risk_df,
        target_col="disrupted",
    )


    # --------------------------------------------------------
    # Risk classifier leaderboard
    # --------------------------------------------------------

    print("\n   RISK CLASSIFIER LEADERBOARD")

    print(
        f"   {'Rank':<6}"
        f"{'Model':<25}"
        f"{'Macro-F1':<12}"
        f"{'Accuracy':<12}"
        f"{'Selected'}"
    )

    print(
        f"   {'-' * 6}"
        f"{'-' * 25}"
        f"{'-' * 12}"
        f"{'-' * 12}"
        f"{'-' * 10}"
    )


    for entry in risk_report["leaderboard"]:

        marker = (
            " <<< BEST"
            if entry["selected"]
            else ""
        )

        print(
            f"   {entry['rank']:<6}"
            f"{entry['model']:<25}"
            f"{entry['macro_f1']:<12.4f}"
            f"{entry['accuracy']:<12.4f}"
            f"{marker}"
        )


    # --------------------------------------------------------
    # Risk feature importance
    # --------------------------------------------------------

    print(
        f"\n   Feature importances "
        f"({risk_report['best_model']}):"
    )


    sorted_features = sorted(
        risk_report["feature_importances"].items(),
        key=lambda x: -x[1],
    )


    for feature, importance in sorted_features:

        bar = "#" * int(importance * 50)

        print(
            f"     {feature:25s} "
            f"{importance:.4f}  "
            f"{bar}"
        )


    # --------------------------------------------------------
    # Confusion matrix
    # --------------------------------------------------------

    print("\n   Confusion Matrix:")

    for row in risk_report["confusion_matrix"]:
        print(f"     {row}")


    # --------------------------------------------------------
    # Classification report
    # --------------------------------------------------------

    print("\n   Classification Report:")

    print(
        risk_report[
            "classification_report"
        ]
    )


    # --------------------------------------------------------
    # Save classifier
    # --------------------------------------------------------

    risk_model.save()

    print(
        "\n[SAVED] Risk classifier model saved."
    )


    # ========================================================
    # 3. TRAIN DELAY REGRESSOR
    # ========================================================

    print("\n" + "-" * 60)

    print(
        " Training Travel Delay Regressor "
        "(5 algorithms)..."
    )

    print("-" * 60)


    delay_model = DelayRegressor()

    delay_report = delay_model.train(
        delay_df,
        target_col="delay_minutes",
    )


    # --------------------------------------------------------
    # Delay model leaderboard
    # --------------------------------------------------------

    print("\n   DELAY REGRESSOR LEADERBOARD")

    print(
        f"   {'Rank':<6}"
        f"{'Model':<25}"
        f"{'RMSE':<12}"
        f"{'MAE':<12}"
        f"{'R2':<12}"
        f"{'Selected'}"
    )

    print(
        f"   {'-' * 6}"
        f"{'-' * 25}"
        f"{'-' * 12}"
        f"{'-' * 12}"
        f"{'-' * 12}"
        f"{'-' * 10}"
    )


    for entry in delay_report["leaderboard"]:

        marker = (
            " <<< BEST"
            if entry["selected"]
            else ""
        )

        print(
            f"   {entry['rank']:<6}"
            f"{entry['model']:<25}"
            f"{entry['rmse']:<12.2f}"
            f"{entry['mae']:<12.2f}"
            f"{entry['r2']:<12.4f}"
            f"{marker}"
        )


    # --------------------------------------------------------
    # Delay feature importance
    # --------------------------------------------------------

    print(
        f"\n   Feature importances "
        f"({delay_report['best_model']}):"
    )


    sorted_features = sorted(
        delay_report["feature_importances"].items(),
        key=lambda x: -x[1],
    )


    for feature, importance in sorted_features:

        bar = "#" * int(importance * 50)

        print(
            f"     {feature:25s} "
            f"{importance:.4f}  "
            f"{bar}"
        )


    # --------------------------------------------------------
    # Save delay model
    # --------------------------------------------------------

    delay_model.save()

    print(
        "\n[SAVED] Delay regressor model saved."
    )


    # ========================================================
    # 4. SAVE TRAINING REPORT
    # ========================================================

    reports = {
        "dataset_info": {
            "risk_samples": len(risk_df),
            "delay_samples": len(delay_df),
            "seed": RANDOM_SEED,
        },
        "risk_classifier": risk_report,
        "delay_regressor": delay_report,
    }


    # Ensure output directory exists
    TRAINED_MODELS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


    report_path = (
        TRAINED_MODELS_DIR
        / "training_report.json"
    )


    with open(
        report_path,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            reports,
            file,
            indent=2,
            default=str,
        )


    print(
        f"\n[SAVED] Training report -> "
        f"{report_path}"
    )


    # ========================================================
    # FINISHED
    # ========================================================

    print("\n" + "=" * 60)

    print("              TRAINING COMPLETE")

    print("=" * 60)

    print(
        f"\nSynthetic data used:"
    )

    print(
        f"   Risk model  : {len(risk_df)} rows"
    )

    print(
        f"   Delay model : {len(delay_df)} rows"
    )

    print(
        f"   Total       : "
        f"{len(risk_df) + len(delay_df)} rows"
    )

    print(
        f"\nModels saved to:"
    )

    print(
        f"   {TRAINED_MODELS_DIR}"
    )

    print("=" * 60)


# ============================================================
# RUN SCRIPT
# ============================================================

if __name__ == "__main__":
    main()
