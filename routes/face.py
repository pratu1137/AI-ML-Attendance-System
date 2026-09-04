from datetime import datetime, timezone

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from sqlalchemy.exc import IntegrityError

from extensions import db
from models import FaceEnrollment, Student, UserRole
from routes.auth import role_required
from services.face_detector import face_detector
from services.face_encoder import FaceEncodingError, face_encoder

face_bp = Blueprint("face", __name__)


@face_bp.get("/live-attendance")
@role_required(UserRole.ADMIN.value, UserRole.FACULTY.value, UserRole.STUDENT.value)
def live_attendance():
    return render_template("face/live_attendance.html")


@face_bp.post("/api/face/detect")
@role_required(UserRole.ADMIN.value, UserRole.FACULTY.value, UserRole.STUDENT.value)
def detect_faces():
    frame = request.files.get("frame")
    if frame is None or not frame.filename:
        return jsonify({"success": False, "error": "A frame image is required."}), 400

    image_bytes = frame.read()
    if not image_bytes:
        return jsonify({"success": False, "error": "The frame image is empty."}), 400

    try:
        faces = face_detector.detect(image_bytes)
    except ValueError as error:
        return jsonify({"success": False, "error": str(error)}), 400
    except RuntimeError:
        return jsonify({"success": False, "error": "Face detection is temporarily unavailable."}), 503

    return jsonify({
        "success": True,
        "faces_detected": len(faces),
        "faces": [face.as_dict() for face in faces],
    })


@face_bp.get("/face-enrollment")
@role_required(UserRole.ADMIN.value)
def enrollment_page():
    students = db.session.scalars(db.select(Student).where(Student.is_active.is_(True)).order_by(Student.full_name)).all()
    enrollments = db.session.scalars(db.select(FaceEnrollment)).all()
    enrolled_ids = {enrollment.student_id for enrollment in enrollments if enrollment.is_active}
    return render_template("face/enrollment.html", students=students, enrolled_ids=enrolled_ids)


@face_bp.post("/api/face/enroll")
@role_required(UserRole.ADMIN.value)
def enroll_face():
    student_id = request.form.get("student_id", "").strip()
    consent = request.form.get("consent", "").lower() in {"1", "true", "on"}
    samples = request.files.getlist("samples")
    student = db.session.scalar(db.select(Student).where(Student.student_id == student_id, Student.is_active.is_(True)))
    if not student:
        return jsonify({"success": False, "error": "An active student is required."}), 400
    if not consent:
        return jsonify({"success": False, "error": "Enrollment consent is required."}), 400
    if len(samples) < 3:
        return jsonify({"success": False, "error": "At least three face samples are required."}), 400
    existing = db.session.scalar(db.select(FaceEnrollment).where(FaceEnrollment.student_id == student.id, FaceEnrollment.is_active.is_(True)))
    if existing:
        return jsonify({"success": False, "error": "This student already has an active face enrollment."}), 409

    encodings = []
    try:
        for sample in samples:
            image_bytes = sample.read()
            faces = face_detector.detect(image_bytes)
            if len(faces) != 1:
                raise FaceEncodingError("Each sample must contain exactly one face.")
            encodings.append(face_encoder.encode_sample(image_bytes, faces[0]))
        aggregate = face_encoder.aggregate(encodings)
        enrollment = FaceEnrollment(
            student_id=student.id,
            representation=face_encoder.serialize(aggregate),
            representation_version=aggregate.version,
            sample_count=len(encodings),
            consent_at=datetime.now(timezone.utc),
        )
        db.session.add(enrollment)
        db.session.commit()
    except (FaceEncodingError, ValueError) as error:
        db.session.rollback()
        return jsonify({"success": False, "error": str(error)}), 400
    except RuntimeError:
        db.session.rollback()
        return jsonify({"success": False, "error": "Face detection is temporarily unavailable."}), 503
    except IntegrityError:
        db.session.rollback()
        return jsonify({"success": False, "error": "This student already has an enrollment."}), 409

    return jsonify({"success": True, "student_id": student.student_id, "sample_count": len(encodings)})


@face_bp.post("/face-enrollment/<int:enrollment_id>/deactivate")
@role_required(UserRole.ADMIN.value)
def deactivate_enrollment(enrollment_id: int):
    enrollment = db.get_or_404(FaceEnrollment, enrollment_id)
    enrollment.is_active = False
    db.session.commit()
    flash("Face enrollment deactivated.", "success")
    return redirect(url_for("face.enrollment_page"))