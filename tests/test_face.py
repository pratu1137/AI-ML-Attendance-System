from io import BytesIO

import cv2
import numpy as np

from extensions import db
from models import User, UserRole


def create_student_user(app):
    with app.app_context():
        user = User(email="student@example.com", role=UserRole.STUDENT.value)
        user.set_password("student-password")
        db.session.add(user)
        db.session.commit()


def login_student(app, client):
    create_student_user(app)
    client.post("/login", data={"email": "student@example.com", "password": "student-password"})


def test_live_attendance_page_requires_login(client):
    response = client.get("/live-attendance")

    assert response.status_code == 302
    assert "/login?next=%2Flive-attendance" in response.headers["Location"]


def test_live_attendance_page_is_available_to_students(app, client):
    login_student(app, client)

    response = client.get("/live-attendance")
    script = client.get("/static/js/live-attendance.js")

    assert response.status_code == 200
    assert b"live-attendance.js" in response.data
    assert b"getUserMedia" in script.data
    assert b"Start camera" in response.data


def test_detection_rejects_missing_and_invalid_frames(app, client):
    login_student(app, client)

    missing = client.post("/api/face/detect")
    invalid = client.post("/api/face/detect", data={"frame": (b"not-an-image", "frame.jpg")})

    assert missing.status_code == 400
    assert missing.get_json()["success"] is False
    assert invalid.status_code == 400
    assert invalid.get_json()["success"] is False


def test_detection_returns_face_array_for_valid_image(app, client):
    login_student(app, client)
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    success, encoded = cv2.imencode(".jpg", image)
    assert success

    response = client.post("/api/face/detect", data={"frame": (BytesIO(encoded.tobytes()), "frame.jpg")})

    assert response.status_code == 200
    assert response.get_json()["success"] is True
    assert response.get_json()["faces_detected"] == 0
    assert response.get_json()["faces"] == []