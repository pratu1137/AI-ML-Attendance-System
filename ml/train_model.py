import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, confusion_matrix, precision_score, recall_score
from sklearn.model_selection import train_test_split

from ml.feature_engineering import FEATURE_NAMES


MODEL_VERSION = "attendance-risk-rf-v1"
RISK_CLASSES = ["LOW", "MEDIUM", "HIGH"]


def synthetic_dataset(sample_count: int = 240) -> tuple[np.ndarray, np.ndarray]:
    generator = np.random.default_rng(42)
    total = generator.integers(10, 100, sample_count).astype(float)
    attendance = generator.uniform(25, 98, sample_count)
    previous = np.clip(attendance + generator.normal(0, 10, sample_count), 0, 100)
    recent = np.clip(attendance + generator.normal(0, 12, sample_count), 0, 100)
    absences = generator.integers(0, 9, sample_count).astype(float)
    attended = np.round(total * attendance / 100)
    subject_average = np.clip((attendance + previous + recent) / 3 + generator.normal(0, 5, sample_count), 0, 100)
    risk_score = (100 - attendance) * 0.45 + (100 - recent) * 0.3 + absences * 3 + (100 - subject_average) * 0.25
    labels = np.select([risk_score < 30, risk_score < 58], ["LOW", "MEDIUM"], default="HIGH")
    features = np.column_stack([attendance, previous, recent, absences, total, attended, subject_average])
    return features, labels


def train_model(output_path: str | Path, features: np.ndarray | None = None, labels: np.ndarray | None = None) -> dict:
    data_source = "REAL" if features is not None and labels is not None and len(labels) >= 30 else "DEMO_SYNTHETIC"
    if data_source == "DEMO_SYNTHETIC":
        features, labels = synthetic_dataset()
    x_train, x_test, y_train, y_test = train_test_split(features, labels, test_size=0.25, random_state=42, stratify=labels)
    model = RandomForestClassifier(n_estimators=160, random_state=42, class_weight="balanced")
    model.fit(x_train, y_train)
    predictions = model.predict(x_test)
    evaluation = {
        "accuracy": round(float(accuracy_score(y_test, predictions)), 4),
        "precision_weighted": round(float(precision_score(y_test, predictions, average="weighted", zero_division=0)), 4),
        "recall_weighted": round(float(recall_score(y_test, predictions, average="weighted", zero_division=0)), 4),
        "confusion_matrix": confusion_matrix(y_test, predictions, labels=RISK_CLASSES).tolist(),
    }
    artifact = {
        "model": model,
        "feature_names": FEATURE_NAMES,
        "risk_classes": RISK_CLASSES,
        "data_source": data_source,
        "model_version": MODEL_VERSION,
        "evaluation": evaluation,
        "trained_at": datetime.now(timezone.utc).isoformat(),
    }
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, output_path)
    return artifact


def train_from_cli(output_path: str | Path) -> dict:
    artifact = train_model(output_path)
    return {key: value for key, value in artifact.items() if key not in {"model"}}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="instance/ml_risk_model.joblib")
    args = parser.parse_args()
    print(json.dumps(train_from_cli(args.output), indent=2))