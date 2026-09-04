from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.exc import IntegrityError

from extensions import db
from models import Attendance, Lecture, Student, StudentSubject
from services.notification_service import create_attendance_notification
from services.timetable_service import get_attendance_timetable_entry
from services.timezone_service import localize, local_now


@dataclass(frozen=True)
class AttendanceResult:
    success: bool
    code: str
    message: str
    attendance: Attendance | None = None


def _lecture_for_timetable(timetable_entry, current_datetime: datetime) -> Lecture:
    lecture = db.session.scalar(
        db.select(Lecture).where(
            Lecture.subject_id == timetable_entry.subject_id,
            Lecture.faculty_id == timetable_entry.faculty_id,
            Lecture.lecture_date == current_datetime.date(),
            Lecture.start_time == timetable_entry.start_time,
            Lecture.end_time == timetable_entry.end_time,
        )
    )
    if lecture:
        return lecture
    lecture = Lecture(
        subject_id=timetable_entry.subject_id,
        faculty_id=timetable_entry.faculty_id,
        lecture_date=current_datetime.date(),
        start_time=timetable_entry.start_time,
        end_time=timetable_entry.end_time,
        status="ONGOING",
    )
    db.session.add(lecture)
    db.session.flush()
    return lecture


def mark_attendance(
    student: Student,
    recognition_distance: float | None,
    current_datetime: datetime | None = None,
    window_before_minutes: int = 0,
    window_after_minutes: int = 0,
    late_after_minutes: int = 10,
) -> AttendanceResult:
    current_datetime = localize(current_datetime) if current_datetime else local_now()
    if not student.is_active:
        return AttendanceResult(False, "INACTIVE_STUDENT", "Student account is inactive.")
    timetable_entry = get_attendance_timetable_entry(current_datetime, window_before_minutes, window_after_minutes)
    if not timetable_entry:
        return AttendanceResult(False, "NO_ACTIVE_LECTURE", "NO ACTIVE LECTURE")
    enrolled = db.session.scalar(db.select(StudentSubject).where(
        StudentSubject.student_id == student.id,
        StudentSubject.subject_id == timetable_entry.subject_id,
        StudentSubject.is_active.is_(True),
    ))
    if not enrolled:
        return AttendanceResult(False, "NOT_ENROLLED", "Student is not enrolled in this subject.")

    lecture_start = datetime.combine(current_datetime.date(), timetable_entry.start_time)

    lecture = _lecture_for_timetable(timetable_entry, current_datetime)
    existing = db.session.scalar(
        db.select(Attendance).where(Attendance.student_id == student.id, Attendance.lecture_id == lecture.id)
    )
    if existing:
        return AttendanceResult(False, "ALREADY_RECORDED", "ATTENDANCE ALREADY RECORDED FOR THIS LECTURE", existing)

    status = "LATE" if current_datetime >= lecture_start + timedelta(minutes=late_after_minutes) else "PRESENT"
    attendance = Attendance(
        student_id=student.id,
        lecture_id=lecture.id,
        attendance_date=current_datetime.date(),
        check_in_time=current_datetime,
        status=status,
        recognition_distance=recognition_distance,
    )
    db.session.add(attendance)
    create_attendance_notification(student, attendance, lecture)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        existing = db.session.scalar(
            db.select(Attendance).where(Attendance.student_id == student.id, Attendance.lecture_id == lecture.id)
        )
        return AttendanceResult(False, "ALREADY_RECORDED", "ATTENDANCE ALREADY RECORDED FOR THIS LECTURE", existing)
    return AttendanceResult(True, "RECORDED", "Attendance recorded.", attendance)