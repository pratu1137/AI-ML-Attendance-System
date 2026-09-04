from datetime import datetime
from zoneinfo import ZoneInfo

from flask import current_app


def application_timezone() -> ZoneInfo:
    return ZoneInfo(current_app.config["APP_TIMEZONE"])


def local_now() -> datetime:
    return datetime.now(application_timezone()).replace(tzinfo=None)


def localize(value: datetime | None = None) -> datetime:
    if value is None:
        return local_now()
    if value.tzinfo is None:
        return value
    return value.astimezone(application_timezone()).replace(tzinfo=None)