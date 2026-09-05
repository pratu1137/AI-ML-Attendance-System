from datetime import datetime, time

from extensions import db
from models import Faculty, Student, Subject, Timetable, User, UserRole
from services.timetable_service import get_current_timetable_entry


def create_admin(app):
    with app.app_context():
        user = User(email="admin@example.com", role=UserRole.ADMIN.value)
        user.set_password("correct-password")
        db.session.add(user)
        db.session.commit()


def login_admin(app, client):
    create_admin(app)
    return client.post("/login", data={"email": "admin@example.com", "password": "correct-password"})


def create_timetable_data(app):
    with app.app_context():
        faculty_user = User(email="faculty@example.com", role=UserRole.FACULTY.value)
        faculty_user.set_password("faculty-password")
        db.session.add(faculty_user)
        db.session.flush()
        faculty = Faculty(user_id=faculty_user.id, full_name="Dr. Ada Lovelace", department="Computer Science")
        subject = Subject(subject_id="SUB-1", subject_code="CS101", subject_name="Algorithms", semester=2, department="Computer Science")
        db.session.add_all([faculty, subject])
        db.session.flush()
        entry = Timetable(day_of_week=0, subject_id=subject.id, faculty_id=faculty.id, room="A-101", start_time=time(10), end_time=time(11))
        db.session.add(entry)
        db.session.commit()
        return entry.id


def test_admin_can_create_and_search_student(app, client):
    login_admin(app, client)

    response = client.post("/students", data={
        "student_id": "STU-001", "roll_number": "R-01", "full_name": "Ada Student",
        "branch": "Computer Science", "year": "2", "division": "A", "email": "ada@example.com",
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b"STU-001" in response.data
    with app.app_context():
        assert db.session.scalar(db.select(Student).where(Student.student_id == "STU-001")).full_name == "Ada Student"

    response = client.get("/students?search=R-01")
    assert b"Ada Student" in response.data


def test_student_identifiers_are_unique_ignoring_case_and_whitespace(app, client):
    login_admin(app, client)
    data = {
        "student_id": "STU-001", "roll_number": "R-01", "full_name": "Ada Student",
        "branch": "Computer Science", "year": "2", "division": "A", "email": "ada@example.com",
    }
    assert client.post("/students", data=data).status_code == 302
    duplicate = client.post("/students", data={**data, "student_id": " stu-001 ", "roll_number": "R-02", "email": "other@example.com"}, follow_redirects=True)
    assert b"must be unique" in duplicate.data
    with app.app_context():
        assert db.session.scalar(db.select(db.func.count(Student.id))) == 1


def test_admin_can_create_and_deactivate_faculty(app, client):
    login_admin(app, client)
    response = client.post("/faculty", data={
        "email": "faculty@example.com", "password": "faculty-password",
        "full_name": "Dr. Ada", "department": "Computer Science",
    }, follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        faculty = db.session.scalar(db.select(Faculty))
        faculty_id = faculty.id
        user_id = faculty.user_id
    response = client.post(f"/faculty/{faculty_id}/deactivate", follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        assert db.session.get(Faculty, faculty_id).is_active is False
        assert db.session.get(User, user_id).is_active is False


def test_non_admin_cannot_manage_students(app, client):
    with app.app_context():
        user = User(email="faculty@example.com", role=UserRole.FACULTY.value)
        user.set_password("faculty-password")
        db.session.add(user)
        db.session.commit()
    client.post("/login", data={"email": "faculty@example.com", "password": "faculty-password"})

    response = client.get("/students")

    assert response.status_code == 403


def test_current_lecture_uses_half_open_time_window(app):
    create_timetable_data(app)

    with app.app_context():
        active = get_current_timetable_entry(datetime(2024, 1, 1, 10, 30))
        at_end = get_current_timetable_entry(datetime(2024, 1, 1, 11, 0))

        assert active is not None
        assert active.subject.subject_code == "CS101"
        assert at_end is None


def test_current_lecture_api_returns_no_active_lecture_for_empty_schedule(app, client):
    with app.app_context():
        user = User(email="student@example.com", role=UserRole.STUDENT.value)
        user.set_password("student-password")
        db.session.add(user)
        db.session.commit()
    client.post("/login", data={"email": "student@example.com", "password": "student-password"})

    response = client.get("/api/current-lecture")

    assert response.status_code == 200
    assert response.get_json() == {"active": False, "message": "NO ACTIVE LECTURE"}