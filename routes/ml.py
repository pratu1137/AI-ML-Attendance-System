import json
from pathlib import Path

from flask import Blueprint, current_app, jsonify, render_template
from flask_login import current_user

from extensions import db
from models import MLPrediction, Student, UserRole
from ml.predict_risk import predict_student_risk
from routes.auth import role_required

ml_bp = Blueprint("ml", __name__)


def _model_path() -> Path:
    return Path(current_app.instance_path) / "ml_risk_model.joblib"


def _prediction(student: Student) -> dict:
    result = predict_student_risk(student, _model_path())
    return {"student": student, "prediction": result}


@ml_bp.get("/ml-risk")
@role_required(UserRole.ADMIN.value, UserRole.FACULTY.value, UserRole.STUDENT.value)
def ml_risk_page():
    if current_user.role == UserRole.STUDENT.value:
        students = [current_user.student_profile] if current_user.student_profile else []
    else:
        students = db.session.scalars(db.select(Student).where(Student.is_active.is_(True)).order_by(Student.full_name)).all()
    results = [_prediction(student) for student in students]
    return render_template("ml/risk.html", results=results)


@ml_bp.get("/api/ml-risk/<int:student_id>")
@role_required(UserRole.ADMIN.value, UserRole.FACULTY.value, UserRole.STUDENT.value)
def ml_risk_api(student_id: int):
    student = db.get_or_404(Student, student_id)
    if current_user.role == UserRole.STUDENT.value and student.user_id != current_user.id:
        return jsonify({"success": False, "error": "Students may view only their own risk."}), 403
    result = _prediction(student)
    prediction = result["prediction"]
    return jsonify({
        "success": True,
        "student_id": student.student_id,
        "risk_class": prediction["risk_class"],
        "high_risk_probability": prediction["high_risk_probability"],
        "features": prediction["features"],
        "data_source": prediction["data_source"],
        "model_version": prediction["model_version"],
        "evaluation": prediction["evaluation"],
    })