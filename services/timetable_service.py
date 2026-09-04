from datetime import datetime

from sqlalchemy import and_, or_

from extensions import db
from models import Timetable


def get_current_timetable_entry(current_datetime: datetime | None = None) -> Timetable | None:
    """Return the recurring timetable entry active at the supplied local time."""
    current_datetime = current_datetime or datetime.now()
    current_time = current_datetime.time().replace(tzinfo=None)
    return db.session.scalar(
        db.select(Timetable)
        .where(
            and_(
                Timetable.is_active.is_(True),
                Timetable.day_of_week == current_datetime.weekday(),
                Timetable.start_time <= current_time,
                Timetable.end_time > current_time,
            )
        )
        .order_by(Timetable.start_time)
    )