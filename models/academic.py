from datetime import date, datetime, time, timezone

from extensions import db


class Student(db.Model):
    __tablename__ = "students"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=True)
    student_id = db.Column(db.String(50), unique=True, nullable=False, index=True)
    roll_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    full_name = db.Column(db.String(150), nullable=False)
    branch = db.Column(db.String(100), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    division = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(30), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    user = db.relationship("User", backref=db.backref("student_profile", uselist=False))


class Faculty(db.Model):
    __tablename__ = "faculty"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)
    full_name = db.Column(db.String(150), nullable=False)
    department = db.Column(db.String(100), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    user = db.relationship("User", backref=db.backref("faculty_profile", uselist=False))


class Subject(db.Model):
    __tablename__ = "subjects"

    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.String(50), unique=True, nullable=False, index=True)
    subject_code = db.Column(db.String(30), unique=True, nullable=False, index=True)
    subject_name = db.Column(db.String(150), nullable=False)
    semester = db.Column(db.Integer, nullable=False)
    department = db.Column(db.String(100), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)


class Timetable(db.Model):
    __tablename__ = "timetable"
    __table_args__ = (
        db.CheckConstraint("day_of_week BETWEEN 0 AND 6", name="ck_timetable_day_of_week"),
        db.CheckConstraint("start_time < end_time", name="ck_timetable_time_order"),
        db.Index("ix_timetable_day_time", "day_of_week", "start_time", "end_time"),
    )

    id = db.Column(db.Integer, primary_key=True)
    day_of_week = db.Column(db.Integer, nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id"), nullable=False)
    faculty_id = db.Column(db.Integer, db.ForeignKey("faculty.id"), nullable=False)
    room = db.Column(db.String(50), nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    subject = db.relationship("Subject", backref="timetable_entries")
    faculty = db.relationship("Faculty", backref="timetable_entries")

    def is_active_at(self, current_datetime: datetime) -> bool:
        current_time = current_datetime.time().replace(tzinfo=None)
        return (
            self.is_active
            and self.day_of_week == current_datetime.weekday()
            and self.start_time <= current_time < self.end_time
        )


class Lecture(db.Model):
    __tablename__ = "lectures"

    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id"), nullable=False)
    faculty_id = db.Column(db.Integer, db.ForeignKey("faculty.id"), nullable=False)
    lecture_date = db.Column(db.Date, nullable=False, default=date.today, index=True)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="SCHEDULED")

    subject = db.relationship("Subject", backref="lectures")
    faculty = db.relationship("Faculty", backref="lectures")


class FaceEnrollment(db.Model):
    __tablename__ = "face_enrollments"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), unique=True, nullable=False, index=True)
    representation = db.Column(db.LargeBinary, nullable=False)
    representation_version = db.Column(db.String(30), nullable=False, default="gray128-l2-v1")
    sample_count = db.Column(db.Integer, nullable=False)
    consent_at = db.Column(db.DateTime(timezone=True), nullable=False)
    enrolled_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    student = db.relationship("Student", backref=db.backref("face_enrollment", uselist=False))


class Attendance(db.Model):
    __tablename__ = "attendance"
    __table_args__ = (
        db.UniqueConstraint("student_id", "lecture_id", name="uq_attendance_student_lecture"),
        db.Index("ix_attendance_lecture_status", "lecture_id", "status"),
    )

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    lecture_id = db.Column(db.Integer, db.ForeignKey("lectures.id"), nullable=False)
    attendance_date = db.Column(db.Date, nullable=False, index=True)
    check_in_time = db.Column(db.DateTime(timezone=True), nullable=False)
    status = db.Column(db.String(20), nullable=False)
    recognition_distance = db.Column(db.Float, nullable=True)

    student = db.relationship("Student", backref="attendance_records")
    lecture = db.relationship("Lecture", backref="attendance_records")