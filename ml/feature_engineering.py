from datetime import date, timedelta

from sqlalchemy import func

from extensions import db
from models import Attendance, Lecture, Student, StudentSubject
from services.timezone_service import local_now

FEATURE_NAMES = [
    "attendance_percentage",
    "previous_month_percentage",
    "recent_percentage",
    "consecutive_absences",
    "total_lectures",
    "attended_lectures",
    "subject_average_percentage",
]


def features_for_student(student: Student, as_of: date | None = None) -> dict[str, float]:
    as_of = as_of or local_now().date()
    lectures = db.session.scalars(
        db.select(Lecture)
        .join(StudentSubject, StudentSubject.subject_id == Lecture.subject_id)
        .where(
            StudentSubject.student_id == student.id,
            StudentSubject.is_active.is_(True),
            Lecture.lecture_date <= as_of,
            Lecture.status != "SCHEDULED",
        )
        .order_by(Lecture.lecture_date)
    ).unique().all()
    records = db.session.scalars(
        db.select(Attendance).where(Attendance.student_id == student.id, Attendance.attendance_date <= as_of).order_by(Attendance.attendance_date)
    ).all()
    present_records = [record for record in records if record.status in {"PRESENT", "LATE"}]
    total = len(lectures)
    attended = len(present_records)
    month_start = as_of.replace(day=1)
    previous_month_end = month_start - timedelta(days=1)
    previous_month_start = previous_month_end.replace(day=1)
    previous_lectures = [lecture for lecture in lectures if previous_month_start <= lecture.lecture_date <= previous_month_end]
    previous_present = sum(1 for record in present_records if previous_month_start <= record.attendance_date <= previous_month_end)
    recent_lectures = lectures[-5:]
    recent_ids = {lecture.id for lecture in recent_lectures}
    recent_present = sum(1 for record in present_records if record.lecture_id in recent_ids)
    consecutive_absences = 0
    for lecture in reversed(lectures):
        if any(record.lecture_id == lecture.id for record in present_records):
            break
        consecutive_absences += 1
    subject_percentages = []
    for subject_id in {lecture.subject_id for lecture in lectures}:
        subject_lectures = [lecture for lecture in lectures if lecture.subject_id == subject_id]
        subject_ids = {lecture.id for lecture in subject_lectures}
        subject_present = sum(1 for record in present_records if record.lecture_id in subject_ids)
        subject_percentages.append(subject_present / len(subject_lectures) * 100 if subject_lectures else 0)
    return {
        "attendance_percentage": attended / total * 100 if total else 0.0,
        "previous_month_percentage": previous_present / len(previous_lectures) * 100 if previous_lectures else 0.0,
        "recent_percentage": recent_present / len(recent_lectures) * 100 if recent_lectures else 0.0,
        "consecutive_absences": float(consecutive_absences),
        "total_lectures": float(total),
        "attended_lectures": float(attended),
        "subject_average_percentage": sum(subject_percentages) / len(subject_percentages) if subject_percentages else 0.0,
    }