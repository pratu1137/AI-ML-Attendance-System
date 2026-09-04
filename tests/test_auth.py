from extensions import db
from models import User, UserRole


def create_user(app, email="admin@example.com", password="correct-password"):
    with app.app_context():
        user = User(email=email, role=UserRole.ADMIN.value)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()


def test_anonymous_user_is_redirected_to_login(client):
    response = client.get("/dashboard")

    assert response.status_code == 302
    assert "/login?next=%2Fdashboard" in response.headers["Location"]


def test_user_can_log_in_and_access_dashboard(app, client):
    create_user(app)

    response = client.post(
        "/login",
        data={"email": "ADMIN@example.com", "password": "correct-password"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Welcome, admin@example.com." in response.data
    assert b"Your role is ADMIN." in response.data


def test_invalid_password_does_not_authenticate(app, client):
    create_user(app)

    response = client.post("/login", data={"email": "admin@example.com", "password": "wrong"})

    assert response.status_code == 200
    assert b"Invalid email or password." in response.data
    assert b"Welcome" not in response.data


def test_inactive_user_cannot_log_in(app, client):
    create_user(app)
    with app.app_context():
        user = db.session.scalar(db.select(User).where(User.email == "admin@example.com"))
        user.is_active = False
        db.session.commit()

    response = client.post("/login", data={"email": "admin@example.com", "password": "correct-password"})

    assert response.status_code == 200
    assert b"Invalid email or password." in response.data


def test_logout_requires_post_and_ends_session(app, client):
    create_user(app)
    client.post("/login", data={"email": "admin@example.com", "password": "correct-password"})

    response = client.post("/logout", follow_redirects=True)

    assert response.status_code == 200
    assert b"You have been signed out." in response.data
    assert b"Sign in" in response.data


def test_admin_area_rejects_non_admin_users(app, client):
    create_user(app, email="student@example.com")
    with app.app_context():
        user = db.session.scalar(db.select(User).where(User.email == "student@example.com"))
        user.role = UserRole.STUDENT.value
        db.session.commit()

    client.post("/login", data={"email": "student@example.com", "password": "correct-password"})

    response = client.get("/admin")

    assert response.status_code == 403


def test_admin_area_allows_admin_users(app, client):
    create_user(app)
    client.post("/login", data={"email": "admin@example.com", "password": "correct-password"})

    response = client.get("/admin")

    assert response.status_code == 200