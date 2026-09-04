# AI-ML-Attendance-System

Flask foundation for the AI-Based Smart Face Recognition Attendance and Student
Attendance Risk Management System.

## Step 1: Foundation and Authentication

### Requirements

- Python 3.12 or newer
- SQLite for local development

### Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
flask --app app init-db
flask --app app seed-admin
flask --app app run --debug
```

Open `http://127.0.0.1:5000/login` and use the credentials configured by
`ADMIN_EMAIL` and `ADMIN_PASSWORD` in `.env`.

Run the Step 1 tests with:

```bash
pytest
```

Step 2 adds database-backed student, subject, and timetable management. Admins
can create, search, view, edit, and deactivate academic records. The
`/api/current-lecture` endpoint resolves the active recurring timetable entry
from the local weekday and time, using a half-open interval where the start is
included and the end is excluded.

Step 3 adds browser webcam face detection at `/live-attendance`. Step 4 adds
admin-only enrollment at `/face-enrollment`; it requires consent and three
quality-checked samples, stores only a derived representation, and supports
deactivation of an enrollment.

Step 5 adds `/api/face/recognize`. It compares one detected face against active
enrollments for active students using a configurable Euclidean-distance
threshold (`FACE_RECOGNITION_THRESHOLD`, default `0.75`). The API reports a
distance and match reason, not a calibrated probability, and never exposes the
stored representation.

Step 6 adds `/api/attendance/mark`. It records attendance only after a reliable
recognition, active-student check, open attendance window, and lecture lookup.
Attendance is classified as `PRESENT` or `LATE`, and a database uniqueness
constraint prevents a student from being recorded twice for one lecture.