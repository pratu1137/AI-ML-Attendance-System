from datetime import date, datetime

from sqlalchemy import and_, func

from extensions import db
from models import Attendance, Faculty, Lecture, Student, Subject, Timetable, User
from services.timetable_service import get_current_timetable_entry


def _active_lecture(now: datetime):
    timetable_entry = get_current_timetable_entry(now)
    if not timetable_entry:
        return None
    return db.session.scalar(
        db.select(Lecture).where(
            Lecture.subject_id == timetable_entry.subject_id,
            Lecture.faculty_id == timetable_entry.faculty_id,
            Lecture.lecture_date == now.date(),
            Lecture.start_time == timetable_entry.start_time,
            Lecture.end_time == timetable_entry.end_time,
        )
    )


def admin_dashboard(now: datetime | None = None) -> dict:
    now = now or datetime.now()
    active_lecture = _active_lecture(now)
    total_students = db.session.scalar(db.select(func.count(Student.id)).where(Student.is_active.is_(True))) or 0
    present_today = db.session.scalar(
        db.select(func.count(Attendance.id)).where(
            Attendance.attendance_date == now.date(), Attendance.status.in_(["PRESENT", "LATE"])
        )
    ) or 0
    conducted_lectures = db.session.scalar(
        db.select(func.count(Lecture.id)).where(Lecture.lecture_date <= now.date(), Lecture.status != "SCHEDULED")
    ) or 0
    total_present = db.session.scalar(
        db.select(func.count(Attendance.id)).where(Attendance.status.in_(["PRESENT", "LATE"]))
    ) or 0
    denominator = total_students * conducted_lectures
    overall_percentage = round((total_present / denominator) * 100, 2) if denominator else 0.0
    lecture_present = 0
    if active_lecture:
        lecture_present = db.session.scalar(
            db.select(func.count(Attendance.id)).where(Attendance.lecture_id == active_lecture.id)
        ) or 0
    return {
        "total_students": total_students,
        "present_today": present_today,
        "absent_today": max(total_students - present_today, 0),
        "active_lecture": active_lecture,
        "lecture_present": lecture_present,
        "overall_percentage": overall_percentage,
    }


def faculty_dashboard(user: User, now: datetime | None = None) -> dict:
    now = now or datetime.now()
    faculty = user.faculty_profile
    if not faculty:
        return {"faculty": None, "assigned_subjects": [], "todays_lectures": [], "current_lecture": None, "present_students": []}
    assigned_subjects = db.session.scalars(
        db.select(Subject)
        .join(Timetable, Timetable.subject_id == Subject.id)
        .where(Timetable.faculty_id == faculty.id, Timetable.is_active.is_(True))
        .distinct()
    ).all()
    todays_lectures = db.session.scalars(
        db.select(Lecture).where(Lecture.faculty_id == faculty.id, Lecture.lecture_date == now.date()).order_by(Lecture.start_time)
    ).all()
    current_lecture = _active_lecture(now)
    present_students = []
    if current_lecture and current_lecture.faculty_id == faculty.id:
        present_students = db.session.scalars(
            db.select(Student).join(Attendance).where(Attendance.lecture_id == current_lecture.id).order_by(Student.full_name)
        ).all()
    return {
        "faculty": faculty,
        "assigned_subjects": assigned_subjects,
        "todays_lectures": todays_lectures,
        "current_lecture": current_lecture if current_lecture and current_lecture.faculty_id == faculty.id else None,
        "present_students": present_students,
    }


def student_dashboard(user: User, now: datetime | None = None) -> dict:
    now = now or datetime.now()
    student = user.student_profile
    if not student:
        return {"student": None, "today_records": [], "total_lectures": 0, "attended_lectures": 0, "attendance_percentage": 0.0}
    total_lectures = db.session.scalar(
        db.select(func.count(Lecture.id)).where(Lecture.lecture_date <= now.date(), Lecture.status != "SCHEDULED")
    ) or 0
    attended_lectures = db.session.scalar(
        db.select(func.count(Attendance.id)).where(
            Attendance.student_id == student.id, Attendance.status.in_(["PRESENT", "LATE"])
        )
    ) or 0
    today_records = db.session.scalars(
        db.select(Attendance).join(Attendance.lecture).where(
            Attendance.student_id == student.id, Attendance.attendance_date == now.date()
        ).order_by(Attendance.check_in_time.desc())
    ).all()
    percentage = round((attended_lectures / total_lectures) * 100, 2) if total_lectures else 0.0
    return {
        "student": student,
        "today_records": today_records,
        "total_lectures": total_lectures,
        "attended_lectures": attended_lectures,
        "attendance_percentage": percentage,
    }