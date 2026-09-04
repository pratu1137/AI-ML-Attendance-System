from io import BytesIO

import cv2
import numpy as np

from extensions import db
from models import FaceEnrollment, Student, User, UserRole
from services.face_detector import FaceBox
from services.face_encoder import FaceEncoding


def setup_user_student(app, active=True):
    with app.app_context():
        user = User(email="student@example.com", role=UserRole.STUDENT.value)
        user.set_password("student-password")
        student = Student(
            student_id="STU-001", roll_number="R-001", full_name="Ada Student", branch="CS",
            year=2, division="A", email="ada@example.com", is_active=active,
        )
        db.session.add_all([user, student])
        db.session.commit()


def login_student(app, client):
    setup_user_student(app)
    client.post("/login", data={"email": "student@example.com", "password": "student-password"})


def image_bytes():
    image = np.full((160, 160, 3), 128, dtype=np.uint8)
    success, encoded = cv2.imencode(".jpg", image)
    assert success
    return encoded.tobytes()


def enroll_vector(app, vector):
    with app.app_context():
        student = db.session.scalar(db.select(Student).where(Student.student_id == "STU-001"))
        db.session.add(FaceEnrollment(
            student_id=student.id, representation=vector.astype(np.float32).tobytes(),
            representation_version="gray128-l2-v1", sample_count=3,
            consent_at=db.func.now(),
        ))
        db.session.commit()


def test_recognition_returns_unknown_when_no_face_is_detected(app, client, monkeypatch):
    login_student(app, client)
    from routes import face
    monkeypatch.setattr(face.face_detector, "detect", lambda _image: [])

    response = client.post("/api/face/recognize", data={"frame": (BytesIO(image_bytes()), "frame.jpg")})

    assert response.status_code == 200
    assert response.get_json()["reason"] == "NO_FACE"


def test_recognition_returns_student_for_match(app, client, monkeypatch):
    login_student(app, client)
    from routes import face
    vector = np.ones(128 * 128, dtype=np.float32)
    enroll_vector(app, vector)
    monkeypatch.setattr(face.face_detector, "detect", lambda _image: [FaceBox(0, 0, 100, 100)])
    monkeypatch.setattr(face.face_encoder, "encode_sample", lambda _image, _box: FaceEncoding(vector=vector))

    response = client.post("/api/face/recognize", data={"frame": (BytesIO(image_bytes()), "frame.jpg")})
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["recognized"] is True
    assert payload["reason"] == "MATCH"
    assert payload["student"]["student_id"] == "STU-001"
    assert "representation" not in payload


def test_recognition_returns_unknown_above_threshold(app, client, monkeypatch):
    login_student(app, client)
    from routes import face
    enroll_vector(app, np.zeros(128 * 128, dtype=np.float32))
    monkeypatch.setattr(face.face_detector, "detect", lambda _image: [FaceBox(0, 0, 100, 100)])
    monkeypatch.setattr(face.face_encoder, "encode_sample", lambda _image, _box: FaceEncoding(vector=np.ones(128 * 128, dtype=np.float32)))

    response = client.post("/api/face/recognize", data={"frame": (BytesIO(image_bytes()), "frame.jpg")})

    assert response.status_code == 200
    assert response.get_json()["reason"] == "UNKNOWN_PERSON"


def test_recognition_does_not_use_inactive_student(app, client, monkeypatch):
    login_student(app, client)
    from routes import face
    with app.app_context():
        student = db.session.scalar(db.select(Student).where(Student.student_id == "STU-001"))
        student.is_active = False
        db.session.add(FaceEnrollment(
            student_id=student.id, representation=np.ones(128 * 128, dtype=np.float32).tobytes(),
            representation_version="gray128-l2-v1", sample_count=3, consent_at=db.func.now(),
        ))
        db.session.commit()
    monkeypatch.setattr(face.face_detector, "detect", lambda _image: [FaceBox(0, 0, 100, 100)])
    monkeypatch.setattr(face.face_encoder, "encode_sample", lambda _image, _box: FaceEncoding(vector=np.ones(128 * 128, dtype=np.float32)))

    response = client.post("/api/face/recognize", data={"frame": (BytesIO(image_bytes()), "frame.jpg")})

    assert response.status_code == 200
    assert response.get_json()["reason"] == "UNKNOWN_PERSON"