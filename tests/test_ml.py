from datetime import date

import joblib
import numpy as np

from extensions import db
from ml.feature_engineering import FEATURE_NAMES, features_for_student
from ml.predict_risk import predict_student_risk
from ml.train_model import train_model
from models import Student, User, UserRole


def test_training_uses_labeled_demo_fallback_and_evaluates(tmp_path):
    artifact = train_model(tmp_path / "risk.joblib")

    assert artifact["data_source"] == "DEMO_SYNTHETIC"
    assert set(artifact["risk_classes"]) == {"LOW", "MEDIUM", "HIGH"}
    assert 0 <= artifact["evaluation"]["accuracy"] <= 1
    assert len(artifact["evaluation"]["confusion_matrix"]) == 3
    assert (tmp_path / "risk.joblib").exists()


def test_prediction_does_not_train_when_model_is_missing(app, tmp_path):
    with app.app_context():
        student = Student(student_id="STU-MISSING", roll_number="R-MISSING", full_name="Missing Model", branch="CS", year=2, division="A", email="missing@example.com")
        db.session.add(student)
        db.session.commit()
        import pytest
        with pytest.raises(FileNotFoundError):
            predict_student_risk(student, tmp_path / "missing.joblib")


def test_feature_engineering_and_prediction_are_persisted(app, tmp_path):
    with app.app_context():
        student = Student(student_id="STU-001", roll_number="R-001", full_name="Ada Student", branch="CS", year=2, division="A", email="ada@example.com")
        db.session.add(student)
        db.session.commit()
        features = features_for_student(student)
        train_model(tmp_path / "risk.joblib")
        result = predict_student_risk(student, tmp_path / "risk.joblib")
        assert list(features) == FEATURE_NAMES
        assert result["data_source"] == "DEMO_SYNTHETIC"
        assert result["risk_class"] in {"LOW", "MEDIUM", "HIGH"}


def test_student_can_view_only_own_ml_risk(app, client):
    with app.app_context():
        user = User(email="student@example.com", role=UserRole.STUDENT.value)
        user.set_password("student-password")
        student = Student(user=user, student_id="STU-001", roll_number="R-001", full_name="Ada Student", branch="CS", year=2, division="A", email="ada@example.com")
        other = Student(student_id="STU-002", roll_number="R-002", full_name="Other Student", branch="CS", year=2, division="A", email="other@example.com")
        db.session.add_all([user, student, other])
        db.session.commit()
    client.post("/login", data={"email": "student@example.com", "password": "student-password"})

    own = client.get("/api/ml-risk/1")
    other_response = client.get("/api/ml-risk/2")

    assert own.status_code == 200
    assert own.get_json()["data_source"] == "DEMO_SYNTHETIC"
    assert other_response.status_code == 403