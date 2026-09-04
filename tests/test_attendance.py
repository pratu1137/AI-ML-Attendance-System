from datetime import datetime, time

from extensions import db
from models import Attendance, Faculty, Student, Subject, Timetable, User, UserRole
from services.attendance_service import mark_attendance


def setup_schedule(app):
    with app.app_context():
        faculty_user = User(email="faculty@example.com", role=UserRole.FACULTY.value)
        faculty_user.set_password("faculty-password")
        student = Student(student_id="STU-001", roll_number="R-001", full_name="Ada Student", branch="CS", year=2, division="A", email="ada@example.com")
        faculty = Faculty(user=faculty_user, full_name="Dr. Ada", department="CS")
        subject = Subject(subject_id="SUB-1", subject_code="CS101", subject_name="Algorithms", semester=2, department="CS")
        db.session.add_all([faculty_user, student, faculty, subject])
        db.session.flush()
        db.session.add(Timetable(day_of_week=0, subject_id=subject.id, faculty_id=faculty.id, room="A-1", start_time=time(10), end_time=time(11)))
        db.session.commit()
        return student.id


def test_attendance_is_recorded_once_with_late_status(app):
    student_id = setup_schedule(app)
    with app.app_context():
        student = db.session.get(Student, student_id)
        now = datetime(2024, 1, 1, 10, 15)
        first = mark_attendance(student, 0.12, now, late_after_minutes=10)
        duplicate = mark_attendance(student, 0.11, now, late_after_minutes=10)

        assert first.success is True
        assert first.attendance.status == "LATE"
        assert duplicate.code == "ALREADY_RECORDED"
        assert db.session.scalar(db.select(db.func.count(Attendance.id))) == 1


def test_attendance_is_present_before_late_cutoff(app):
    student_id = setup_schedule(app)
    with app.app_context():
        result = mark_attendance(db.session.get(Student, student_id), 0.1, datetime(2024, 1, 1, 10, 9), late_after_minutes=10)
        assert result.success is True
        assert result.attendance.status == "PRESENT"


def test_attendance_rejects_no_active_lecture(app):
    with app.app_context():
        student = Student(student_id="STU-001", roll_number="R-001", full_name="Ada Student", branch="CS", year=2, division="A", email="ada@example.com")
        db.session.add(student)
        db.session.commit()
        result = mark_attendance(student, 0.1, datetime(2024, 1, 1, 10, 0))
        assert result.code == "NO_ACTIVE_LECTURE"


def test_attendance_rejects_inactive_student(app):
    with app.app_context():
        student = Student(student_id="STU-001", roll_number="R-001", full_name="Ada Student", branch="CS", year=2, division="A", email="ada@example.com", is_active=False)
        db.session.add(student)
        db.session.commit()
        result = mark_attendance(student, 0.1, datetime(2024, 1, 1, 10, 0))
        assert result.code == "INACTIVE_STUDENT"


def test_configured_after_window_allows_late_check_in(app):
    student_id = setup_schedule(app)
    with app.app_context():
        result = mark_attendance(
            db.session.get(Student, student_id), 0.1, datetime(2024, 1, 1, 11, 5),
            window_after_minutes=10, late_after_minutes=10,
        )
        assert result.success is True
        assert result.attendance.status == "LATE"