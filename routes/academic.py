from datetime import time

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError

from extensions import db
from models import Faculty, Student, StudentSubject, Subject, Timetable, User, UserRole
from routes.auth import role_required
from services.timetable_service import get_current_timetable_entry

academic_bp = Blueprint("academic", __name__)


def _required_form_values(*names: str) -> dict[str, str] | None:
    values = {name: request.form.get(name, "").strip() for name in names}
    return values if all(values.values()) else None


def _identifier(value: str) -> str:
    return " ".join(value.split()).casefold()


def _student_identifier_conflict(values: dict[str, str], student_id: int | None = None) -> bool:
    query = db.select(Student).where(
        or_(
            func.lower(Student.student_id) == _identifier(values["student_id"]),
            func.lower(Student.roll_number) == _identifier(values["roll_number"]),
        )
    )
    if student_id is not None:
        query = query.where(Student.id != student_id)
    return db.session.scalar(query) is not None


@academic_bp.get("/students")
@role_required(UserRole.ADMIN.value)
def students():
    search = request.args.get("search", "").strip()
    query = db.select(Student).order_by(Student.full_name)
    if search:
        pattern = f"%{search}%"
        query = query.where(
            or_(Student.full_name.ilike(pattern), Student.student_id.ilike(pattern), Student.roll_number.ilike(pattern))
        )
    return render_template("academic/students.html", students=db.session.scalars(query).all(), search=search)


@academic_bp.post("/students")
@role_required(UserRole.ADMIN.value)
def create_student():
    values = _required_form_values("student_id", "roll_number", "full_name", "branch", "year", "division", "email")
    if not values:
        flash("All required student fields must be provided.", "error")
        return redirect(url_for("academic.students"))
    values["student_id"] = " ".join(values["student_id"].split())
    values["roll_number"] = " ".join(values["roll_number"].split())
    if _student_identifier_conflict(values):
        flash("Student ID or roll number must be unique.", "error")
        return redirect(url_for("academic.students"))
    try:
        student = Student(
            student_id=values["student_id"], roll_number=values["roll_number"], full_name=values["full_name"],
            branch=values["branch"], year=int(values["year"]), division=values["division"], email=values["email"],
            phone=request.form.get("phone", "").strip() or None,
        )
        db.session.add(student)
        db.session.commit()
    except ValueError:
        db.session.rollback()
        flash("Year must be a valid number.", "error")
        return redirect(url_for("academic.students"))
    except IntegrityError:
        db.session.rollback()
        flash("Student ID or roll number must be unique.", "error")
        return redirect(url_for("academic.students"))
    flash("Student created.", "success")
    return redirect(url_for("academic.students"))


@academic_bp.get("/students/<int:student_id>")
@role_required(UserRole.ADMIN.value, UserRole.FACULTY.value)
def student_detail(student_id: int):
    student = db.get_or_404(Student, student_id)
    subjects = db.session.scalars(db.select(Subject).where(Subject.is_active.is_(True)).order_by(Subject.subject_name)).all()
    enrolled_subject_ids = {enrollment.subject_id for enrollment in student.subject_enrollments if enrollment.is_active}
    return render_template("academic/student_detail.html", student=student, subjects=subjects, enrolled_subject_ids=enrolled_subject_ids)


@academic_bp.post("/students/<int:student_id>/subjects")
@role_required(UserRole.ADMIN.value)
def update_student_subjects(student_id: int):
    student = db.get_or_404(Student, student_id)
    selected_ids = {int(value) for value in request.form.getlist("subject_ids")}
    existing = {enrollment.subject_id: enrollment for enrollment in student.subject_enrollments}
    for subject_id, enrollment in existing.items():
        enrollment.is_active = subject_id in selected_ids
    for subject_id in selected_ids - existing.keys():
        if db.session.get(Subject, subject_id):
            db.session.add(StudentSubject(student_id=student.id, subject_id=subject_id))
    db.session.commit()
    flash("Student subjects updated.", "success")
    return redirect(url_for("academic.student_detail", student_id=student.id))


@academic_bp.post("/students/<int:student_id>/deactivate")
@role_required(UserRole.ADMIN.value)
def deactivate_student(student_id: int):
    student = db.get_or_404(Student, student_id)
    student.is_active = False
    if student.user:
        student.user.is_active = False
    db.session.commit()
    flash("Student deactivated.", "success")
    return redirect(url_for("academic.students"))


@academic_bp.post("/students/<int:student_id>/activate")
@role_required(UserRole.ADMIN.value)
def activate_student(student_id: int):
    student = db.get_or_404(Student, student_id)
    student.is_active = True
    if student.user:
        student.user.is_active = True
    db.session.commit()
    flash("Student activated.", "success")
    return redirect(url_for("academic.students"))


@academic_bp.post("/students/<int:student_id>/edit")
@role_required(UserRole.ADMIN.value)
def edit_student(student_id: int):
    student = db.get_or_404(Student, student_id)
    values = _required_form_values("student_id", "roll_number", "full_name", "branch", "year", "division", "email")
    if not values:
        flash("All required student fields must be provided.", "error")
        return redirect(url_for("academic.student_detail", student_id=student.id))
    values["student_id"] = " ".join(values["student_id"].split())
    values["roll_number"] = " ".join(values["roll_number"].split())
    if _student_identifier_conflict(values, student.id):
        flash("Student ID or roll number must be unique.", "error")
        return redirect(url_for("academic.student_detail", student_id=student.id))
    try:
        student.student_id = values["student_id"]
        student.roll_number = values["roll_number"]
        student.full_name = values["full_name"]
        student.branch = values["branch"]
        student.year = int(values["year"])
        student.division = values["division"]
        student.email = values["email"]
        student.phone = request.form.get("phone", "").strip() or None
        db.session.commit()
    except ValueError:
        db.session.rollback()
        flash("Year must be a valid number.", "error")
    except IntegrityError:
        db.session.rollback()
        flash("Student ID or roll number must be unique.", "error")
    return redirect(url_for("academic.student_detail", student_id=student.id))


@academic_bp.get("/subjects")
@role_required(UserRole.ADMIN.value)
def subjects():
    return render_template("academic/subjects.html", subjects=db.session.scalars(db.select(Subject).order_by(Subject.subject_name)).all())


@academic_bp.get("/faculty")
@role_required(UserRole.ADMIN.value)
def faculty():
    people = db.session.scalars(db.select(Faculty).order_by(Faculty.full_name)).all()
    return render_template("academic/faculty.html", faculty=people)


@academic_bp.post("/faculty")
@role_required(UserRole.ADMIN.value)
def create_faculty():
    values = _required_form_values("email", "password", "full_name", "department")
    if not values or len(values["password"]) < 8:
        flash("Faculty email, name, department, and a password of at least 8 characters are required.", "error")
        return redirect(url_for("academic.faculty"))
    try:
        user = User(email=values["email"].lower(), role=UserRole.FACULTY.value)
        user.set_password(values["password"])
        db.session.add(user)
        db.session.flush()
        db.session.add(Faculty(user_id=user.id, full_name=values["full_name"], department=values["department"]))
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash("A user with that email already exists.", "error")
        return redirect(url_for("academic.faculty"))
    flash("Faculty created.", "success")
    return redirect(url_for("academic.faculty"))


@academic_bp.post("/faculty/<int:faculty_id>/edit")
@role_required(UserRole.ADMIN.value)
def edit_faculty(faculty_id: int):
    person = db.get_or_404(Faculty, faculty_id)
    values = _required_form_values("email", "full_name", "department")
    if not values:
        flash("Faculty email, name, and department are required.", "error")
        return redirect(url_for("academic.faculty"))
    person.full_name = values["full_name"]
    person.department = values["department"]
    person.user.email = values["email"].lower()
    password = request.form.get("password", "")
    if password:
        if len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
            db.session.rollback()
            return redirect(url_for("academic.faculty"))
        person.user.set_password(password)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash("A user with that email already exists.", "error")
        return redirect(url_for("academic.faculty"))
    flash("Faculty updated.", "success")
    return redirect(url_for("academic.faculty"))


@academic_bp.post("/faculty/<int:faculty_id>/deactivate")
@role_required(UserRole.ADMIN.value)
def deactivate_faculty(faculty_id: int):
    person = db.get_or_404(Faculty, faculty_id)
    person.is_active = False
    person.user.is_active = False
    db.session.commit()
    flash("Faculty deactivated.", "success")
    return redirect(url_for("academic.faculty"))


@academic_bp.post("/faculty/<int:faculty_id>/activate")
@role_required(UserRole.ADMIN.value)
def activate_faculty(faculty_id: int):
    person = db.get_or_404(Faculty, faculty_id)
    person.is_active = True
    person.user.is_active = True
    db.session.commit()
    flash("Faculty activated.", "success")
    return redirect(url_for("academic.faculty"))


@academic_bp.post("/subjects")
@role_required(UserRole.ADMIN.value)
def create_subject():
    values = _required_form_values("subject_id", "subject_code", "subject_name", "semester", "department")
    if not values:
        flash("All required subject fields must be provided.", "error")
        return redirect(url_for("academic.subjects"))
    try:
        subject = Subject(
            subject_id=values["subject_id"], subject_code=values["subject_code"], subject_name=values["subject_name"],
            semester=int(values["semester"]), department=values["department"],
        )
        if subject.semester <= 0:
            raise ValueError
        db.session.add(subject)
        db.session.commit()
    except ValueError:
        db.session.rollback()
        flash("Semester must be a valid number.", "error")
        return redirect(url_for("academic.subjects"))
    except IntegrityError:
        db.session.rollback()
        flash("Subject ID and subject code must be unique.", "error")
        return redirect(url_for("academic.subjects"))
    flash("Subject created.", "success")
    return redirect(url_for("academic.subjects"))


@academic_bp.post("/subjects/<int:subject_id>/edit")
@role_required(UserRole.ADMIN.value)
def edit_subject(subject_id: int):
    subject = db.get_or_404(Subject, subject_id)
    values = _required_form_values("subject_id", "subject_code", "subject_name", "semester", "department")
    if not values:
        flash("All required subject fields must be provided.", "error")
        return redirect(url_for("academic.subjects"))
    try:
        subject.subject_id = values["subject_id"]
        subject.subject_code = values["subject_code"]
        subject.subject_name = values["subject_name"]
        subject.semester = int(values["semester"])
        if subject.semester <= 0:
            raise ValueError
        subject.department = values["department"]
        db.session.commit()
    except ValueError:
        db.session.rollback()
        flash("Semester must be a valid number.", "error")
    except IntegrityError:
        db.session.rollback()
        flash("Subject ID and subject code must be unique.", "error")
    return redirect(url_for("academic.subjects"))


@academic_bp.post("/subjects/<int:subject_id>/toggle-active")
@role_required(UserRole.ADMIN.value)
def toggle_subject_active(subject_id: int):
    subject = db.get_or_404(Subject, subject_id)
    subject.is_active = not subject.is_active
    db.session.commit()
    flash(f"Subject {'activated' if subject.is_active else 'deactivated'}.", "success")
    return redirect(url_for("academic.subjects"))


@academic_bp.get("/timetable")
@role_required(UserRole.ADMIN.value)
def timetable():
    entries = db.session.scalars(db.select(Timetable).order_by(Timetable.day_of_week, Timetable.start_time)).all()
    subjects = db.session.scalars(db.select(Subject).where(Subject.is_active.is_(True)).order_by(Subject.subject_name)).all()
    faculty = db.session.scalars(db.select(Faculty).where(Faculty.is_active.is_(True)).order_by(Faculty.full_name)).all()
    return render_template("academic/timetable.html", entries=entries, subjects=subjects, faculty=faculty)


@academic_bp.post("/timetable")
@role_required(UserRole.ADMIN.value)
def create_timetable_entry():
    values = _required_form_values("day_of_week", "subject_id", "faculty_id", "room", "start_time", "end_time")
    if not values:
        flash("All timetable fields must be provided.", "error")
        return redirect(url_for("academic.timetable"))
    try:
        entry = Timetable(
            day_of_week=int(values["day_of_week"]), subject_id=int(values["subject_id"]), faculty_id=int(values["faculty_id"]),
            room=values["room"], start_time=time.fromisoformat(values["start_time"]), end_time=time.fromisoformat(values["end_time"]),
        )
        if entry.start_time >= entry.end_time:
            raise ValueError
        overlap = db.session.scalar(
            db.select(Timetable).where(
                Timetable.is_active.is_(True),
                Timetable.day_of_week == entry.day_of_week,
                or_(Timetable.faculty_id == entry.faculty_id, Timetable.room == entry.room),
                Timetable.start_time < entry.end_time,
                Timetable.end_time > entry.start_time,
            )
        )
        if overlap:
            raise ValueError("The faculty or room is already scheduled during this time.")
        db.session.add(entry)
        db.session.commit()
    except (ValueError, IntegrityError):
        db.session.rollback()
        flash("Timetable values are invalid.", "error")
        return redirect(url_for("academic.timetable"))
    flash("Timetable entry created.", "success")
    return redirect(url_for("academic.timetable"))


@academic_bp.post("/timetable/<int:entry_id>/deactivate")
@role_required(UserRole.ADMIN.value)
def deactivate_timetable_entry(entry_id: int):
    entry = db.get_or_404(Timetable, entry_id)
    entry.is_active = False
    db.session.commit()
    flash("Timetable entry deactivated.", "success")
    return redirect(url_for("academic.timetable"))


@academic_bp.get("/api/current-lecture")
@role_required(UserRole.ADMIN.value, UserRole.FACULTY.value, UserRole.STUDENT.value)
def current_lecture():
    entry = get_current_timetable_entry()
    if not entry:
        return jsonify({"active": False, "message": "NO ACTIVE LECTURE"})
    return jsonify({
        "active": True, "timetable_id": entry.id, "subject": entry.subject.subject_name,
        "subject_code": entry.subject.subject_code, "faculty": entry.faculty.full_name,
        "room": entry.room, "start_time": entry.start_time.isoformat(), "end_time": entry.end_time.isoformat(),
    })