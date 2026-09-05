from datetime import datetime, timezone

from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy.exc import IntegrityError

from extensions import db
from models import FaceEnrollment, Student, UserRole
from routes.auth import role_required
from services.attendance_service import mark_attendance
from services.face_detector import face_detector
from services.face_encoder import FaceEncodingError, face_encoder
from services.face_recognizer import build_recognizer
from services.timetable_service import get_attendance_timetable_entry
from services.timezone_service import local_now

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


@face_bp.post("/api/face/recognize")
@role_required(UserRole.ADMIN.value, UserRole.FACULTY.value, UserRole.STUDENT.value)
def recognize_face():
    frame = request.files.get("frame")
    if frame is None or not frame.filename:
        return jsonify({"success": False, "error": "A frame image is required."}), 400
    image_bytes = frame.read()
    if not image_bytes:
        return jsonify({"success": False, "error": "The frame image is empty."}), 400
    try:
        faces = face_detector.detect(image_bytes)
        if len(faces) == 0:
            return jsonify({"success": True, "recognized": False, "reason": "NO_FACE", "faces_detected": 0, "faces": []})
        if len(faces) > 1:
            return jsonify({"success": True, "recognized": False, "reason": "MULTIPLE_FACES", "faces_detected": len(faces), "faces": [face.as_dict() for face in faces]})
        encoding = face_encoder.encode_sample(image_bytes, faces[0])
        result = build_recognizer(current_app.config["FACE_RECOGNITION_THRESHOLD"]).recognize(encoding)
    except (FaceEncodingError, ValueError) as error:
        return jsonify({"success": False, "error": str(error)}), 400
    except RuntimeError:
        return jsonify({"success": False, "error": "Face recognition is temporarily unavailable."}), 503

    response = {
        "success": True,
        "recognized": result.recognized,
        "faces_detected": 1,
        "faces": [faces[0].as_dict()],
        "reason": "MATCH" if result.recognized else "UNKNOWN_PERSON",
        "distance": result.distance,
        "threshold": current_app.config["FACE_RECOGNITION_THRESHOLD"],
    }
    if result.recognized and result.student:
        response["student"] = {
            "student_id": result.student.student_id,
            "roll_number": result.student.roll_number,
            "full_name": result.student.full_name,
            "branch": result.student.branch,
            "year": result.student.year,
            "division": result.student.division,
        }
    return jsonify(response)


@face_bp.post("/api/attendance/mark")
@role_required(UserRole.ADMIN.value, UserRole.FACULTY.value, UserRole.STUDENT.value)
def mark_attendance_from_frame():
    frame = request.files.get("frame")
    if frame is None or not frame.filename:
        return jsonify({"success": False, "error": "A frame image is required."}), 400
    image_bytes = frame.read()
    if not image_bytes:
        return jsonify({"success": False, "error": "The frame image is empty."}), 400
    try:
        faces = face_detector.detect(image_bytes)
        if len(faces) != 1:
            reason = "NO_FACE" if not faces else "MULTIPLE_FACES"
            return jsonify({"success": True, "recorded": False, "reason": reason, "faces_detected": len(faces), "faces": [face.as_dict() for face in faces]})
        encoding = face_encoder.encode_sample(image_bytes, faces[0])
        recognition = build_recognizer(current_app.config["FACE_RECOGNITION_THRESHOLD"]).recognize(encoding)
        if not recognition.recognized or not recognition.student:
            return jsonify({
                "success": True, "recorded": False, "reason": "UNKNOWN_PERSON",
                "faces_detected": 1, "faces": [faces[0].as_dict()], "distance": recognition.distance,
            })
        if current_user.role == UserRole.STUDENT.value:
            if not current_user.student_profile or current_user.student_profile.id != recognition.student.id:
                return jsonify({"success": False, "recorded": False, "reason": "FORBIDDEN", "message": "Students may mark only their own attendance."}), 403
        elif current_user.role == UserRole.FACULTY.value:
            timetable_entry = get_attendance_timetable_entry(
                local_now(),
                current_app.config["ATTENDANCE_WINDOW_BEFORE_MINUTES"],
                current_app.config["ATTENDANCE_WINDOW_AFTER_MINUTES"],
            )
            if not timetable_entry or timetable_entry.faculty.user_id != current_user.id:
                return jsonify({"success": False, "recorded": False, "reason": "FORBIDDEN", "message": "Faculty may mark attendance only for their active lecture."}), 403
        result = mark_attendance(
            recognition.student,
            recognition.distance,
            window_before_minutes=current_app.config["ATTENDANCE_WINDOW_BEFORE_MINUTES"],
            window_after_minutes=current_app.config["ATTENDANCE_WINDOW_AFTER_MINUTES"],
            late_after_minutes=current_app.config["ATTENDANCE_LATE_AFTER_MINUTES"],
        )
    except (FaceEncodingError, ValueError) as error:
        return jsonify({"success": False, "error": str(error)}), 400
    except RuntimeError:
        return jsonify({"success": False, "error": "Face recognition is temporarily unavailable."}), 503

    response = {
        "success": True,
        "recorded": result.success,
        "reason": result.code,
        "message": result.message,
        "faces_detected": 1,
        "faces": [faces[0].as_dict()],
        "distance": recognition.distance,
    }
    if result.attendance:
        response["attendance"] = {
            "id": result.attendance.id,
            "status": result.attendance.status,
            "check_in_time": result.attendance.check_in_time.isoformat(),
            "lecture_id": result.attendance.lecture_id,
        }
        response["lecture"] = {
            "subject": result.attendance.lecture.subject.subject_name,
            "subject_code": result.attendance.lecture.subject.subject_code,
            "faculty": result.attendance.lecture.faculty.full_name,
        }
    if recognition.student:
        response["student"] = {
            "student_id": recognition.student.student_id,
            "roll_number": recognition.student.roll_number,
            "full_name": recognition.student.full_name,
            "branch": recognition.student.branch,
            "year": recognition.student.year,
            "division": recognition.student.division,
        }
    return jsonify(response), 200 if result.success else 409 if result.code == "ALREADY_RECORDED" else 400


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