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

Attendance also requires an active student-subject enrollment. Admins manage
those relationships from the student detail page. Successful attendance creates
an in-app notification visible at `/notifications`.

Step 9 adds ML attendance-risk prediction at `/ml-risk` and
`/api/ml-risk/<student_id>`. Run `flask --app app train-risk-model` to persist
the Random Forest model. Because this project does not yet contain enough
labeled historical examples, training uses deterministic data labeled
`DEMO_SYNTHETIC`; predictions expose that source and evaluation metrics. ML is
decision support only and does not make detention decisions.

## Step 10: Production Preparation

### Local verification

```bash
python3 -m pytest -q
python3 -m flask --app app routes
```

The application exposes `/healthz` for platform health checks. Production uses
`wsgi:app` behind Gunicorn:

```bash
SECRET_KEY="a-long-random-secret" \
DATABASE_URL="postgresql+psycopg://user:password@host/database" \
TRUST_PROXY=true \
gunicorn --config gunicorn.conf.py wsgi:app
```

Set `SECRET_KEY` and `DATABASE_URL` in the deployment platform's secret
configuration. Never commit `.env`, database credentials, model artifacts, or
uploaded files. The included `Dockerfile` runs as a non-root user, and
`.github/workflows/ci.yml` runs the test suite and Python compilation checks on
pushes and pull requests.

For schema changes, use Flask-Migrate in the deployment environment with
`flask --app app db upgrade`; run migrations before starting new web workers.
Fresh databases use the committed migration in `migrations/`. Existing
development databases created with the older `init-db` command can use
`flask --app app upgrade-db`; it creates missing tables additively and does not
delete attendance data. Set `APP_TIMEZONE` (default `Asia/Kolkata`) consistently
across web workers and migration/maintenance commands.