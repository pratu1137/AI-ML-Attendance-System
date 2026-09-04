from datetime import datetime, timezone

from flask import Blueprint, redirect, render_template, url_for
from flask_login import current_user

from extensions import db
from models import Notification, UserRole
from routes.auth import role_required

notifications_bp = Blueprint("notifications", __name__)


@notifications_bp.get("/notifications")
@role_required(UserRole.STUDENT.value)
def notifications():
    student = current_user.student_profile
    records = []
    if student:
        records = db.session.scalars(
            db.select(Notification).where(Notification.student_id == student.id).order_by(Notification.created_at.desc())
        ).all()
    return render_template("notifications/list.html", notifications=records)


@notifications_bp.post("/notifications/<int:notification_id>/read")
@role_required(UserRole.STUDENT.value)
def mark_read(notification_id: int):
    notification = db.get_or_404(Notification, notification_id)
    if not current_user.student_profile or notification.student_id != current_user.student_profile.id:
        return {"error": "Forbidden"}, 403
    notification.read_at = datetime.now(timezone.utc)
    db.session.commit()
    return redirect(url_for("notifications.notifications"))