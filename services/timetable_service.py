from datetime import datetime, timedelta

from sqlalchemy import and_, or_

from extensions import db
from models import Faculty, Subject, Timetable
from services.timezone_service import localize, local_now


def get_current_timetable_entry(current_datetime: datetime | None = None) -> Timetable | None:
    """Return the recurring timetable entry active at the supplied local time."""
    current_datetime = localize(current_datetime) if current_datetime else local_now()
    current_time = current_datetime.time().replace(tzinfo=None)
    return db.session.scalar(
        db.select(Timetable)
        .join(Timetable.faculty)
        .join(Timetable.subject)
        .where(
            and_(
                Timetable.is_active.is_(True), Faculty.is_active.is_(True), Subject.is_active.is_(True),
                Timetable.day_of_week == current_datetime.weekday(),
                Timetable.start_time <= current_time,
                Timetable.end_time > current_time,
            )
        )
        .order_by(Timetable.start_time)
    )


def get_attendance_timetable_entry(
    current_datetime: datetime,
    window_before_minutes: int = 0,
    window_after_minutes: int = 0,
) -> Timetable | None:
    """Return a timetable entry whose configurable attendance window is open."""
    current_datetime = localize(current_datetime)
    entries = db.session.scalars(
        db.select(Timetable).join(Timetable.faculty).join(Timetable.subject).where(
            Timetable.is_active.is_(True), Faculty.is_active.is_(True), Subject.is_active.is_(True),
            Timetable.day_of_week == current_datetime.weekday()
        )
        .order_by(Timetable.start_time)
    ).all()
    for entry in entries:
        start = datetime.combine(current_datetime.date(), entry.start_time) - timedelta(minutes=window_before_minutes)
        end = datetime.combine(current_datetime.date(), entry.end_time) + timedelta(minutes=window_after_minutes)
        if start <= current_datetime < end:
            return entry
    return None