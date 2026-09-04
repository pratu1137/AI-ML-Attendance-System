from io import BytesIO, StringIO

import pandas as pd
from flask import Blueprint, abort, current_app, jsonify, make_response, redirect, render_template, request, url_for
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from extensions import db
from models import AttendanceSettings, UserRole
from routes.auth import role_required
from services.analytics_service import analytics_summary, attendance_rows, detain_rows, get_settings

analytics_bp = Blueprint("analytics", __name__)


@analytics_bp.get("/analytics")
@role_required(UserRole.ADMIN.value, UserRole.FACULTY.value, UserRole.STUDENT.value)
def analytics():
    return render_template("analytics/analytics.html", summary=analytics_summary())


@analytics_bp.get("/detain-list")
@role_required(UserRole.ADMIN.value, UserRole.FACULTY.value)
def detain_list():
    rows = detain_rows()
    risk_filter = request.args.get("risk", "").strip().upper()
    search = request.args.get("search", "").strip().lower()
    if risk_filter in {"DETAIN RISK", "WARNING", "SAFE"}:
        rows = [row for row in rows if row["risk_status"] == risk_filter]
    if search:
        rows = [row for row in rows if search in row["student"].full_name.lower() or search in row["roll_number"].lower()]
    rows.sort(key=lambda row: row["percentage"])
    return render_template("analytics/detain_list.html", rows=rows, risk_filter=risk_filter, search=search)


@analytics_bp.route("/settings", methods=["GET", "POST"])
@role_required(UserRole.ADMIN.value)
def settings():
    settings_record = get_settings()
    if request.method == "POST":
        try:
            warning = float(request.form["warning_threshold"])
            detain = float(request.form["detain_threshold"])
            target = float(request.form["target_threshold"])
            if not (0 <= detain < warning <= 100 and 0 <= target <= 100):
                raise ValueError
            settings_record.warning_threshold = warning
            settings_record.detain_threshold = detain
            settings_record.target_threshold = target
            db.session.commit()
        except (KeyError, ValueError):
            db.session.rollback()
            return render_template("analytics/settings.html", settings=settings_record, error="Thresholds must be valid percentages with detain below warning."), 400
        return redirect(url_for("analytics.settings"))
    return render_template("analytics/settings.html", settings=settings_record)


def _report_rows(report_type: str) -> list[dict]:
    if report_type == "attendance":
        return attendance_rows()
    if report_type == "detain":
        return [
            {
                "student_id": row["student"].student_id,
                "student_name": row["student"].full_name,
                "roll_number": row["roll_number"],
                "branch": row["branch"],
                "total_lectures": row["total_lectures"],
                "present": row["present"],
                "absent": row["absent"],
                "attendance_percentage": row["percentage"],
                "risk_status": row["risk_status"],
            }
            for row in detain_rows()
        ]
    abort(404)


@analytics_bp.get("/reports/<report_type>.<file_format>")
@role_required(UserRole.ADMIN.value, UserRole.FACULTY.value)
def report(report_type: str, file_format: str):
    rows = _report_rows(report_type)
    if file_format == "csv":
        output = StringIO()
        pd.DataFrame(rows).to_csv(output, index=False)
        response = make_response(output.getvalue())
        response.headers["Content-Type"] = "text/csv; charset=utf-8"
    elif file_format == "xlsx":
        output = BytesIO()
        pd.DataFrame(rows).to_excel(output, index=False)
        response = make_response(output.getvalue())
        response.headers["Content-Type"] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif file_format == "pdf":
        output = BytesIO()
        pdf = canvas.Canvas(output, pagesize=letter)
        pdf.setFont("Helvetica", 9)
        pdf.drawString(40, 770, f"{report_type.title()} Attendance Report")
        y = 750
        for row in rows:
            line = " | ".join(f"{key}: {value}" for key, value in row.items())[:115]
            pdf.drawString(40, y, line)
            y -= 14
            if y < 40:
                pdf.showPage()
                pdf.setFont("Helvetica", 9)
                y = 770
        pdf.save()
        response = make_response(output.getvalue())
        response.headers["Content-Type"] = "application/pdf"
    else:
        abort(404)
    response.headers["Content-Disposition"] = f"attachment; filename={report_type}-report.{file_format}"
    return response