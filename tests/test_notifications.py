from datetime import datetime, time

from extensions import db
from models import Attendance, Faculty, Notification, Student, StudentSubject, Subject, Timetable, User, UserRole
from services.attendance_service import mark_attendance


def test_student_can_read_and_mark_own_notification(app, client):
    with app.app_context():
        user = User(email="student@example.com", role=UserRole.STUDENT.value)
        user.set_password("student-password")
        student = Student(user=user, student_id="STU-001", roll_number="R-001", full_name="Ada", branch="CS", year=2, division="A", email="ada@example.com")
        notification = Notification(student=student, notification_type="ATTENDANCE_MARKED", title="Attendance marked", message="Present.")
        db.session.add_all([user, student, notification])
        db.session.commit()
        notification_id = notification.id
    client.post("/login", data={"email": "student@example.com", "password": "student-password"})

    listing = client.get("/notifications")
    marked = client.post(f"/notifications/{notification_id}/read", follow_redirects=True)

    assert listing.status_code == 200
    assert b"Attendance marked" in listing.data
    assert marked.status_code == 200
    with app.app_context():
        assert db.session.get(Notification, notification_id).read_at is not None