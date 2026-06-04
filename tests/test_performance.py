import pytest
import time
import sys
import os
import uuid
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import app
from db_config import initialize_db, get_db


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        with app.app_context():
            initialize_db()
            with get_db() as conn:
                conn.execute("DELETE FROM students")
                conn.execute("DELETE FROM users")
                conn.commit()
        yield client


def authed_session(client):
    email = f"perf_{uuid.uuid4().hex[:8]}@test.com"
    client.post("/register", data={
        "email": email, "password": "password123", "confirm_password": "password123",
        "nombre": "Perf", "edad": "20", "nivel_educativo": "universidad", "intereses": "m",
    }, follow_redirects=True)
    client.post("/login", data={"email": email, "password": "password123"}, follow_redirects=True)
    return email


def measure(label, threshold):
    def decorator(func):
        def wrapper(client, *args, **kwargs):
            start = time.time()
            result = func(client, *args, **kwargs)
            elapsed = time.time() - start
            assert elapsed < threshold, f"{label} tardó {elapsed:.3f}s (>{threshold}s)"
            return result
        return wrapper
    return decorator


def test_login_page_load_time(client):
    """Login debe ser < 500ms"""
    start = time.time()
    response = client.get('/login')
    elapsed = time.time() - start

    assert response.status_code == 200
    assert elapsed < 0.5, f"Login tardó {elapsed:.3f}s"


def test_register_page_load_time(client):
    """Register debe ser < 500ms"""
    start = time.time()
    response = client.get('/register')
    elapsed = time.time() - start

    assert response.status_code == 200
    assert elapsed < 0.5, f"Register tardó {elapsed:.3f}s"


def test_api_protection_speed(client):
    """Redirección a login debe ser < 200ms"""
    start = time.time()
    response = client.get('/')
    elapsed = time.time() - start

    assert response.status_code == 302
    assert elapsed < 0.2, f"Protección tardó {elapsed:.3f}s"


def test_index_authenticated_performance(client):
    """Index autenticado debe ser < 500ms"""
    authed_session(client)
    start = time.time()
    response = client.get('/')
    elapsed = time.time() - start
    assert response.status_code == 200
    assert elapsed < 0.5, f"Index tardó {elapsed:.3f}s"


def test_perfil_performance(client):
    """Perfil debe ser < 500ms"""
    authed_session(client)
    start = time.time()
    response = client.get('/perfil')
    elapsed = time.time() - start
    assert response.status_code == 200
    assert elapsed < 0.5, f"Perfil tardó {elapsed:.3f}s"


def test_visual_performance_with_mock(client):
    """Visual debe ser < 500ms con YouTube mockeado"""
    authed_session(client)
    with patch("app.buscar_videos_youtube", return_value=[]):
        start = time.time()
        response = client.get('/visual?tema=Probabilidad%20b%C3%A1sica')
        elapsed = time.time() - start
    assert response.status_code == 200
    assert elapsed < 0.5, f"Visual tardó {elapsed:.3f}s"


def test_practico_performance(client):
    """Practico debe ser < 500ms"""
    authed_session(client)
    start = time.time()
    response = client.get('/practico?tema=Probabilidad%20b%C3%A1sica')
    elapsed = time.time() - start
    assert response.status_code == 200
    assert elapsed < 0.5, f"Practico tardó {elapsed:.3f}s"


def test_logout_performance(client):
    """Logout debe ser < 200ms"""
    authed_session(client)
    start = time.time()
    response = client.get('/logout')
    elapsed = time.time() - start
    assert response.status_code == 302
    assert elapsed < 0.2, f"Logout tardó {elapsed:.3f}s"
