from extensions import db
from models import Notification, Student


def create_attendance_notification(student: Student, attendance, lecture) -> Notification:
    notification = Notification(
        student_id=student.id,
        notification_type="ATTENDANCE_MARKED",
        title="Attendance marked",
        message=f"Your attendance was marked {attendance.status.lower()} for {lecture.subject.subject_name}.",
    )
    db.session.add(notification)
    return notification