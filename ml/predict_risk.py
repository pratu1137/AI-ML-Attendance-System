from pathlib import Path

import joblib
import numpy as np

from ml.feature_engineering import FEATURE_NAMES, features_for_student
from ml.train_model import MODEL_VERSION


def load_artifact(path: str | Path):
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError("No approved attendance risk model is installed.")
    try:
        artifact = joblib.load(path)
    except (OSError, ValueError, EOFError) as error:
        raise ValueError("The installed attendance risk model is invalid.") from error
    if not isinstance(artifact, dict) or artifact.get("model_version") != MODEL_VERSION:
        raise ValueError("The installed attendance risk model is incompatible.")
    if artifact.get("feature_names") != FEATURE_NAMES or "model" not in artifact:
        raise ValueError("The installed attendance risk model has invalid metadata.")
    return artifact


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