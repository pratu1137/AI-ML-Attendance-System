from datetime import date, datetime, time

from extensions import db
from models import Attendance, Faculty, Lecture, Student, Subject, User, UserRole
from services.analytics_service import analytics_summary, detain_rows


def setup_admin_data(app):
    with app.app_context():
        admin = User(email="admin@example.com", role=UserRole.ADMIN.value)
        admin.set_password("admin-password")
        faculty_user = User(email="faculty@example.com", role=UserRole.FACULTY.value)
        faculty_user.set_password("faculty-password")
        faculty = Faculty(user=faculty_user, full_name="Dr. Ada", department="CS")
        student = Student(student_id="STU-001", roll_number="R-001", full_name="Ada Student", branch="CS", year=2, division="A", email="ada@example.com")
        subject = Subject(subject_id="SUB-1", subject_code="CS101", subject_name="Algorithms", semester=2, department="CS")
        db.session.add_all([admin, faculty_user, faculty, student, subject])
        db.session.flush()
        lecture = Lecture(subject_id=subject.id, faculty_id=faculty.id, lecture_date=date.today(), start_time=time(9), end_time=time(10), status="COMPLETED")
        db.session.add(lecture)
        db.session.flush()
        db.session.add(Attendance(student_id=student.id, lecture_id=lecture.id, attendance_date=date.today(), check_in_time=datetime.now(), status="PRESENT"))
        db.session.commit()


def login_admin(app, client):
    setup_admin_data(app)
    client.post("/login", data={"email": "admin@example.com", "password": "admin-password"})


def test_analytics_and_detain_rows_use_real_records(app):
    setup_admin_data(app)
    with app.app_context():
        summary = analytics_summary()
        rows = detain_rows()

        assert summary["total_lectures"] == 1
        assert summary["present"] == 1
        assert summary["overall_percentage"] == 100.0
        assert rows[0]["percentage"] == 100.0
        assert rows[0]["risk_status"] == "SAFE"


def test_analytics_page_contains_chart_data(app, client):
    setup_admin_data(app)
    client.post("/login", data={"email": "admin@example.com", "password": "admin-password"})

    response = client.get("/analytics")

    assert response.status_code == 200
    assert b"daily-attendance-chart" in response.data
    assert b"analytics.js" in response.data
    assert b"CS101" in response.data


def test_admin_can_update_thresholds_and_filter_detain_list(app, client):
    login_admin(app, client)

    response = client.post("/settings", data={"warning_threshold": "80", "detain_threshold": "60", "target_threshold": "80"}, follow_redirects=True)
    assert response.status_code == 200
    response = client.get("/detain-list?risk=SAFE&search=R-001")
    assert response.status_code == 200
    assert b"Ada Student" in response.data

    invalid = client.post("/settings", data={"warning_threshold": "50", "detain_threshold": "60", "target_threshold": "75"})
    assert invalid.status_code == 400


def test_reports_return_csv_xlsx_and_pdf(app, client):
    login_admin(app, client)

    csv_response = client.get("/reports/attendance.csv")
    xlsx_response = client.get("/reports/attendance.xlsx")
    pdf_response = client.get("/reports/detain.pdf")

    assert csv_response.status_code == 200
    assert b"student_id" in csv_response.data
    assert xlsx_response.status_code == 200
    assert xlsx_response.data[:2] == b"PK"
    assert pdf_response.status_code == 200
    assert pdf_response.data.startswith(b"%PDF")