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