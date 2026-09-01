"""
NERRO ML — Model Training Script
Generates synthetic data, trains both models, saves them to disk.

Usage:
    cd nerro_ml
    python -m scripts.train
"""

import sys
import os
import json
from pathlib import Path

# Ensure the project root is on sys.path so `app.*` imports work
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.config import TRAINED_MODELS_DIR
from app.data.synthetic import generate_risk_dataset, generate_delay_dataset
from app.models.risk_classifier import RiskClassifier
from app.models.delay_regressor import DelayRegressor


def main():
    print("=" * 60)
    print("  NERRO ML -- Model Training Pipeline")
    print("=" * 60)

    # ── 1. Generate synthetic training data ───────────────────────
    print("\n[DATA] Generating synthetic risk dataset (5000 samples)...")
    risk_df = generate_risk_dataset(n_samples=5000, seed=42)
    print(f"   Shape: {risk_df.shape}")
    print(f"   Disrupted ratio: {risk_df['disrupted'].mean():.2%}")

    print("\n[DATA] Generating synthetic delay dataset (5000 samples)...")
    delay_df = generate_delay_dataset(n_samples=5000, seed=42)
    print(f"   Shape: {delay_df.shape}")
    print(f"   Mean delay: {delay_df['delay_minutes'].mean():.1f} min")

    # ── 2. Train risk classifier ──────────────────────────────────
    print("\n" + "-" * 60)
    print("    Training Route Disruption Risk Classifier (5 algorithms)...")
    print("-" * 60)

    risk_model = RiskClassifier()
    risk_report = risk_model.train(risk_df, target_col="disrupted")

    print(f"\n   RISK CLASSIFIER LEADERBOARD:")
    print(f"   {'Rank':<6} {'Model':<25} {'Macro-F1':<10} {'Accuracy':<10} {'Selected'}")
    print(f"   {'-'*6} {'-'*25} {'-'*10} {'-'*10} {'-'*8}")
    for entry in risk_report["leaderboard"]:
        marker = " <<< BEST" if entry["selected"] else ""
        print(f"   {entry['rank']:<6} {entry['model']:<25} {entry['macro_f1']:<10} {entry['accuracy']:<10}{marker}")

    print(f"\n   Feature importances ({risk_report['best_model']}):")
    for feat, imp in sorted(
        risk_report["feature_importances"].items(), key=lambda x: -x[1]
    ):
        bar = "#" * int(imp * 50)
        print(f"     {feat:25s} {imp:.4f}  {bar}")
    print(f"\n   Confusion matrix:")
    for row in risk_report["confusion_matrix"]:
        print(f"     {row}")
    print(f"\n{risk_report['classification_report']}")

    risk_model.save()

    # ── 3. Train delay regressor ──────────────────────────────────
    print("\n" + "-" * 60)
    print("    Training Travel Delay Regressor (5 algorithms)...")
    print("-" * 60)

    delay_model = DelayRegressor()
    delay_report = delay_model.train(delay_df, target_col="delay_minutes")

    print(f"\n   DELAY REGRESSOR LEADERBOARD:")
    print(f"   {'Rank':<6} {'Model':<25} {'RMSE':<10} {'MAE':<10} {'R2':<10} {'Selected'}")
    print(f"   {'-'*6} {'-'*25} {'-'*10} {'-'*10} {'-'*10} {'-'*8}")
    for entry in delay_report["leaderboard"]:
        marker = " <<< BEST" if entry["selected"] else ""
        print(f"   {entry['rank']:<6} {entry['model']:<25} {entry['rmse']:<10} {entry['mae']:<10} {entry['r2']:<10}{marker}")

    print(f"\n   Feature importances ({delay_report['best_model']}):")
    for feat, imp in sorted(
        delay_report["feature_importances"].items(), key=lambda x: -x[1]
    ):
        bar = "#" * int(imp * 50)
        print(f"     {feat:25s} {imp:.4f}  {bar}")

    delay_model.save()

    # ── 4. Save reports ───────────────────────────────────────────
    reports = {
        "risk_classifier": risk_report,
        "delay_regressor": delay_report,
    }
    # Convert numpy arrays in confusion matrix to lists for JSON
    report_path = TRAINED_MODELS_DIR / "training_report.json"
    with open(report_path, "w") as f:
        json.dump(reports, f, indent=2, default=str)
    print(f"\n[SAVED] Training report -> {report_path}")

    print("\n" + "=" * 60)
    print("  [DONE] Training complete! Models saved to:")
    print(f"     {TRAINED_MODELS_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
