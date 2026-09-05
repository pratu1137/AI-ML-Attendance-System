from extensions import db
from models import User, UserRole


def test_shared_layout_references_existing_static_assets(client):
    response = client.get("/login")

    assert response.status_code == 200
    assert b"/static/css/app.css?v=2" in response.data
    assert b"/static/js/app.js?v=2" in response.data


def test_static_css_and_javascript_are_served(client):
    css = client.get("/static/css/app.css")
    app_js = client.get("/static/js/app.js")
    camera_js = client.get("/static/js/live-attendance.js")
    analytics_js = client.get("/static/js/analytics.js")

    assert css.status_code == 200
    assert b".sidebar" in css.data
    assert app_js.status_code == 200
    assert b"data-menu-toggle" in app_js.data
    assert camera_js.status_code == 200
    assert b"getUserMedia" in camera_js.data
    assert analytics_js.status_code == 200


def test_live_attendance_uses_transparent_overlay_and_compact_status_panel(client):
    with client.application.app_context():
        user = User(email="frontend@example.com", role=UserRole.ADMIN.value)
        user.set_password("frontend-password")
        db.session.add(user)
        db.session.commit()
        user_id = user.id
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True

    response = client.get("/live-attendance")
    css = client.get("/static/css/app.css")
    javascript = client.get("/static/js/live-attendance.js")

    assert response.status_code == 200
    assert b"camera-stage" in response.data
    assert b"camera-status-panel" in response.data
    assert b"faces-detected" in response.data
    assert b".camera-stage canvas" in css.data
    assert b".camera-stage video{transform:none}" in css.data
    assert b"background:transparent" in css.data
    assert b"Multiple faces detected" in javascript.data


def test_enrollment_supports_uploaded_samples(client):
    with client.application.app_context():
        user = User(email="frontend-admin@example.com", role=UserRole.ADMIN.value)
        user.set_password("frontend-password")
        db.session.add(user)
        db.session.commit()
        user_id = user.id
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True

    response = client.get("/face-enrollment")
    script = client.get("/static/js/face-enrollment.js")

    assert response.status_code == 200
    assert b'type="file"' in response.data
    assert b"fileInput.files" in script.data
