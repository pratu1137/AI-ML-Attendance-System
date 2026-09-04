from io import BytesIO

import cv2
import numpy as np

from extensions import db
from models import FaceEnrollment, Student, User, UserRole
from services.face_detector import FaceBox
from services.face_encoder import FaceEncoding


def test_student_cannot_mark_attendance_for_another_enrolled_student(app, client, monkeypatch):
    with app.app_context():
        user = User(email="student@example.com", role=UserRole.STUDENT.value)
        user.set_password("student-password")
        actor = Student(user=user, student_id="STU-001", roll_number="R-001", full_name="Actor", branch="CS", year=2, division="A", email="actor@example.com")
        recognized = Student(student_id="STU-002", roll_number="R-002", full_name="Recognized", branch="CS", year=2, division="A", email="recognized@example.com")
        db.session.add_all([user, actor, recognized])
        db.session.flush()
        db.session.add(FaceEnrollment(
            student_id=recognized.id,
            representation=np.ones(128 * 128, dtype=np.float32).tobytes(),
            representation_version="gray128-l2-v1",
            sample_count=3,
            consent_at=db.func.now(),
        ))
        db.session.commit()
    client.post("/login", data={"email": "student@example.com", "password": "student-password"})
    from routes import face

    monkeypatch.setattr(face.face_detector, "detect", lambda _image: [FaceBox(0, 0, 100, 100)])
    monkeypatch.setattr(face.face_encoder, "encode_sample", lambda _image, _box: FaceEncoding(vector=np.ones(128 * 128, dtype=np.float32)))
    image = np.zeros((120, 120, 3), dtype=np.uint8)
    success, encoded = cv2.imencode(".jpg", image)
    assert success

    response = client.post("/api/attendance/mark", data={"frame": (BytesIO(encoded.tobytes()), "frame.jpg")})

    assert response.status_code == 403
    assert response.get_json()["reason"] == "FORBIDDEN"