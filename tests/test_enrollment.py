from io import BytesIO

import cv2
import numpy as np

from extensions import db
from models import FaceEnrollment, Student, User, UserRole
from services.face_detector import FaceBox
from services.face_encoder import FaceEncoding


def create_admin_and_student(app):
    with app.app_context():
        admin = User(email="admin@example.com", role=UserRole.ADMIN.value)
        admin.set_password("admin-password")
        student = Student(
            student_id="STU-001", roll_number="R-001", full_name="Ada Student", branch="CS",
            year=2, division="A", email="ada@example.com",
        )
        db.session.add_all([admin, student])
        db.session.commit()


def login_admin(app, client):
    create_admin_and_student(app)
    client.post("/login", data={"email": "admin@example.com", "password": "admin-password"})


def sample_image():
    image = np.full((160, 160, 3), 128, dtype=np.uint8)
    for index in range(0, 160, 8):
        image[index:index + 2, :] = 180
    success, encoded = cv2.imencode(".jpg", image)
    assert success
    return encoded.tobytes()


def test_enrollment_page_is_admin_only(app, client):
    response = client.get("/face-enrollment")
    assert response.status_code == 302

    login_admin(app, client)
    response = client.get("/face-enrollment")
    assert response.status_code == 200
    assert b"Student consent received" in response.data


def test_enrollment_requires_consent_and_three_samples(app, client):
    login_admin(app, client)

    response = client.post("/api/face/enroll", data={"student_id": "STU-001"})

    assert response.status_code == 400
    assert response.get_json()["error"] == "Enrollment consent is required."


def test_enrollment_rejects_multiple_faces(app, client, monkeypatch):
    login_admin(app, client)
    from routes import face

    monkeypatch.setattr(face.face_detector, "detect", lambda _image: [FaceBox(0, 0, 80, 80), FaceBox(80, 0, 80, 80)])
    data = {"student_id": "STU-001", "consent": "true", "samples": [(BytesIO(sample_image()), "one.jpg")] * 3}

    response = client.post("/api/face/enroll", data=data)

    assert response.status_code == 400
    assert "exactly one face" in response.get_json()["error"]


def test_enrollment_stores_representation_not_frames(app, client, monkeypatch):
    login_admin(app, client)
    from routes import face

    monkeypatch.setattr(face.face_detector, "detect", lambda _image: [FaceBox(0, 0, 100, 100)])
    vector = np.ones(128 * 128, dtype=np.float32)
    monkeypatch.setattr(face.face_encoder, "encode_sample", lambda _image, _box: FaceEncoding(vector=vector))
    data = {"student_id": "STU-001", "consent": "true", "samples": [(BytesIO(sample_image()), f"{index}.jpg") for index in range(3)]}

    response = client.post("/api/face/enroll", data=data)

    assert response.status_code == 200
    with app.app_context():
        enrollment = db.session.scalar(db.select(FaceEnrollment))
        assert enrollment.sample_count == 3
        assert len(enrollment.representation) == 128 * 128 * 4
        assert sample_image() not in enrollment.representation


def test_duplicate_enrollment_is_rejected_and_can_be_deactivated(app, client, monkeypatch):
    login_admin(app, client)
    from routes import face

    monkeypatch.setattr(face.face_detector, "detect", lambda _image: [FaceBox(0, 0, 100, 100)])
    vector = np.ones(128 * 128, dtype=np.float32)
    monkeypatch.setattr(face.face_encoder, "encode_sample", lambda _image, _box: FaceEncoding(vector=vector))
    data = {"student_id": "STU-001", "consent": "true", "samples": [(BytesIO(sample_image()), f"{index}.jpg") for index in range(3)]}
    first = client.post("/api/face/enroll", data=data)
    duplicate = client.post("/api/face/enroll", data={"student_id": "STU-001", "consent": "true", "samples": [(BytesIO(sample_image()), f"{index}.jpg") for index in range(3)]})

    assert first.status_code == 200
    assert duplicate.status_code == 409
    with app.app_context():
        enrollment = db.session.scalar(db.select(FaceEnrollment))
        enrollment_id = enrollment.id
    response = client.post(f"/face-enrollment/{enrollment_id}/deactivate", follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        assert db.session.get(FaceEnrollment, enrollment_id).is_active is False