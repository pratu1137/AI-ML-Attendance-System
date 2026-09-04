from pathlib import Path

import joblib
import numpy as np

from ml.feature_engineering import FEATURE_NAMES, features_for_student
from ml.train_model import train_model


def load_artifact(path: str | Path):
    path = Path(path)
    if not path.exists():
        return train_model(path)
    return joblib.load(path)


def predict_student_risk(student, model_path: str | Path) -> dict:
    artifact = load_artifact(model_path)
    features = features_for_student(student)
    values = np.array([[features[name] for name in FEATURE_NAMES]], dtype=float)
    model = artifact["model"]
    probabilities = model.predict_proba(values)[0]
    risk_class = str(model.predict(values)[0])
    high_index = list(model.classes_).index("HIGH")
    return {
        "risk_class": risk_class,
        "high_risk_probability": round(float(probabilities[high_index]), 4),
        "features": features,
        "data_source": artifact["data_source"],
        "model_version": artifact["model_version"],
        "evaluation": artifact["evaluation"],
    }