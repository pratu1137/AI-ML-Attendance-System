from datetime import date

from sqlalchemy import func

from extensions import db
from models import Attendance, AttendanceSettings, Lecture, Student, Subject
from services.timezone_service import local_now


def get_settings() -> AttendanceSettings:
    settings = db.session.get(AttendanceSettings, 1)
    if settings is None:
        settings = AttendanceSettings(id=1)
        db.session.add(settings)
        db.session.flush()
    return settings


def percentage(present: int, total: int) -> float:
    return round((present / total) * 100, 2) if total else 0.0


def attendance_rows(student_id: int | None = None, faculty_id: int | None = None, start_date: date | None = None, end_date: date | None = None) -> list[dict]:
    query = db.select(Attendance).join(Attendance.lecture).order_by(Attendance.attendance_date, Attendance.check_in_time)
    if student_id:
        query = query.where(Attendance.student_id == student_id)
    if faculty_id:
        query = query.where(Lecture.faculty_id == faculty_id)
    if start_date:
        query = query.where(Attendance.attendance_date >= start_date)
    if end_date:
        query = query.where(Attendance.attendance_date <= end_date)
    return [
        {
            "student_id": record.student.student_id,
            "student_name": record.student.full_name,
            "roll_number": record.student.roll_number,
            "subject_code": record.lecture.subject.subject_code,
            "subject_name": record.lecture.subject.subject_name,
            "lecture_date": record.attendance_date.isoformat(),
            "status": record.status,
            "check_in_time": record.check_in_time.isoformat(),
        }
        for record in db.session.scalars(query).all()
    ]


def student_summary(student: Student, conducted_lectures: list[Lecture] | None = None) -> dict:
    lectures = conducted_lectures or db.session.scalars(
        db.select(Lecture).where(Lecture.lecture_date <= local_now().date(), Lecture.status != "SCHEDULED")
    ).all()
    present = db.session.scalar(
        db.select(func.count(Attendance.id)).where(
            Attendance.student_id == student.id, Attendance.status.in_(["PRESENT", "LATE"])
        )
    ) or 0
    return {
        "student": student,
        "total_lectures": len(lectures),
        "present": present,
        "absent": max(len(lectures) - present, 0),
        "percentage": percentage(present, len(lectures)),
    }


def detain_rows(faculty_id: int | None = None) -> list[dict]:
    settings = get_settings()
    students = db.session.scalars(db.select(Student).where(Student.is_active.is_(True)).order_by(Student.full_name)).all()
    lecture_query = db.select(Lecture).where(Lecture.lecture_date <= local_now().date(), Lecture.status != "SCHEDULED")
    if faculty_id:
        lecture_query = lecture_query.where(Lecture.faculty_id == faculty_id)
    lectures = db.session.scalars(lecture_query).all()
    rows = []
    for student in students:
        summary = student_summary(student, lectures)
        current = summary["percentage"]
        risk = "DETAIN RISK" if current < settings.detain_threshold else "WARNING" if current < settings.warning_threshold else "SAFE"
        rows.append({**summary, "roll_number": student.roll_number, "branch": student.branch, "risk_status": risk})
    return rows


def analytics_summary(student_id: int | None = None, faculty_id: int | None = None) -> dict:
    lecture_query = db.select(Lecture).where(Lecture.status != "SCHEDULED").order_by(Lecture.lecture_date)
    if faculty_id:
        lecture_query = lecture_query.where(Lecture.faculty_id == faculty_id)
    lectures = db.session.scalars(lecture_query).all()
    attendance_query = db.select(func.count(Attendance.id)).where(Attendance.status.in_(["PRESENT", "LATE"]))
    if student_id:
        attendance_query = attendance_query.where(Attendance.student_id == student_id)
    if faculty_id:
        attendance_query = attendance_query.join(Attendance.lecture).where(Lecture.faculty_id == faculty_id)
    present = db.session.scalar(attendance_query) or 0
    active_students = db.session.scalar(db.select(func.count(Student.id)).where(Student.is_active.is_(True))) or 0
    daily = {}
    for lecture in lectures:
        key = lecture.lecture_date.isoformat()
        daily.setdefault(key, {"present": 0, "total": 0})
        daily[key]["total"] += 1 if student_id else active_students
        daily[key]["present"] += sum(1 for record in lecture.attendance_records if record.status in {"PRESENT", "LATE"} and (not student_id or record.student_id == student_id))
    subjects = {}
    for lecture in lectures:
        item = subjects.setdefault(lecture.subject.subject_code, {"subject": lecture.subject.subject_name, "present": 0, "total": 0})
        item["total"] += 1 if student_id else active_students
        item["present"] += sum(1 for record in lecture.attendance_records if record.status in {"PRESENT", "LATE"} and (not student_id or record.student_id == student_id))
    monthly = {}
    for lecture in lectures:
        key = lecture.lecture_date.strftime("%Y-%m")
        monthly.setdefault(key, {"present": 0, "total": 0})
        monthly[key]["total"] += 1 if student_id else active_students
        monthly[key]["present"] += sum(1 for record in lecture.attendance_records if record.status in {"PRESENT", "LATE"} and (not student_id or record.student_id == student_id))
    return {
        "total_lectures": len(lectures),
        "present": present,
        "overall_percentage": percentage(present, len(lectures) if student_id else active_students * len(lectures)),
        "daily": [{"date": key, **value, "percentage": percentage(value["present"], value["total"])} for key, value in daily.items()],
        "monthly": [{"month": key, **value, "percentage": percentage(value["present"], value["total"])} for key, value in monthly.items()],
        "subjects": [{"subject_code": key, **value, "percentage": percentage(value["present"], value["total"])} for key, value in subjects.items()],
    }