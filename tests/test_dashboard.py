from datetime import date, datetime, time

from extensions import db
from models import Attendance, Faculty, Lecture, Student, Subject, Timetable, User, UserRole
from services.dashboard_service import admin_dashboard, faculty_dashboard, student_dashboard


def test_admin_dashboard_uses_database_values(app, client):
    with app.app_context():
        admin = User(email="admin@example.com", role=UserRole.ADMIN.value)
        admin.set_password("admin-password")
        db.session.add(admin)
        db.session.add(Student(student_id="STU-001", roll_number="R-001", full_name="Ada Student", branch="CS", year=2, division="A", email="ada@example.com"))
        db.session.commit()
    client.post("/login", data={"email": "admin@example.com", "password": "admin-password"})

    response = client.get("/dashboard")

    assert response.status_code == 200
    assert b"Total active students" in response.data
    assert b">1<" in response.data
    assert b"NO ACTIVE LECTURE" in response.data


def test_student_dashboard_calculates_attendance(app):
    with app.app_context():
        user = User(email="student@example.com", role=UserRole.STUDENT.value)
        user.set_password("student-password")
        student = Student(user=user, student_id="STU-001", roll_number="R-001", full_name="Ada Student", branch="CS", year=2, division="A", email="ada@example.com")
        faculty_user = User(email="faculty@example.com", role=UserRole.FACULTY.value)
        faculty_user.set_password("faculty-password")
        faculty = Faculty(user=faculty_user, full_name="Dr. Ada", department="CS")
        subject = Subject(subject_id="SUB-1", subject_code="CS101", subject_name="Algorithms", semester=2, department="CS")
        db.session.add_all([user, student, faculty_user, faculty, subject])
        db.session.flush()
        first = Lecture(subject_id=subject.id, faculty_id=faculty.id, lecture_date=date.today(), start_time=time(9), end_time=time(10), status="COMPLETED")
        second = Lecture(subject_id=subject.id, faculty_id=faculty.id, lecture_date=date.today(), start_time=time(10), end_time=time(11), status="COMPLETED")
        db.session.add_all([first, second])
        db.session.flush()
        db.session.add(Attendance(student_id=student.id, lecture_id=first.id, attendance_date=date.today(), check_in_time=datetime.now(), status="PRESENT"))
        db.session.commit()

        dashboard = student_dashboard(user, datetime.combine(date.today(), time(12)))

        assert dashboard["total_lectures"] == 2
        assert dashboard["attended_lectures"] == 1
        assert dashboard["attendance_percentage"] == 50.0
        assert len(dashboard["today_records"]) == 1


def test_faculty_dashboard_scopes_current_students_to_faculty(app):
    with app.app_context():
        faculty_user = User(email="faculty@example.com", role=UserRole.FACULTY.value)
        faculty_user.set_password("faculty-password")
        faculty = Faculty(user=faculty_user, full_name="Dr. Ada", department="CS")
        subject = Subject(subject_id="SUB-1", subject_code="CS101", subject_name="Algorithms", semester=2, department="CS")
        db.session.add_all([faculty_user, faculty, subject])
        db.session.flush()
        db.session.add(Timetable(day_of_week=0, subject_id=subject.id, faculty_id=faculty.id, room="A-1", start_time=time(10), end_time=time(11)))
        db.session.commit()

        dashboard = faculty_dashboard(faculty_user, datetime(2024, 1, 1, 10, 30))

        assert [item.subject_code for item in dashboard["assigned_subjects"]] == ["CS101"]
        assert dashboard["current_lecture"] is None