"""
Tests para las rutas Flask: auth, index, visual, practico
"""
import sys
import os
import uuid
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
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


def register_user(client, email=None, password="password123"):
    email = email or f"user_{uuid.uuid4().hex[:8]}@test.com"
    client.post("/register", data={
        "email": email,
        "password": password,
        "confirm_password": password,
        "nombre": "Test User",
        "edad": "20",
        "nivel_educativo": "universidad",
        "intereses": "estadistica",
    }, follow_redirects=True)
    return email


def login_user(client, email, password="password123"):
    return client.post("/login", data={"email": email, "password": password}, follow_redirects=True)


# ─────────────────────── Register ───────────────────────

def test_register_get_renders(client):
    response = client.get("/register")
    assert response.status_code == 200
    assert b"Registrarse" in response.data or b"registr" in response.data.lower()


def test_register_success_redirects_to_login(client):
    response = client.post("/register", data={
        "email": "newuser@test.com",
        "password": "password123",
        "confirm_password": "password123",
        "nombre": "Test",
        "edad": "20",
        "nivel_educativo": "universidad",
        "intereses": "math",
    })
    assert response.status_code == 302
    assert "/login" in response.location


def test_register_password_mismatch(client):
    response = client.post("/register", data={
        "email": "x@x.com", "password": "pass123", "confirm_password": "different",
        "nombre": "T", "edad": "20", "nivel_educativo": "universidad", "intereses": "m",
    }, follow_redirects=True)
    assert b"no coinciden" in response.data


def test_register_password_too_short(client):
    response = client.post("/register", data={
        "email": "x@x.com", "password": "123", "confirm_password": "123",
        "nombre": "T", "edad": "20", "nivel_educativo": "universidad", "intereses": "m",
    }, follow_redirects=True)
    assert b"6 caracteres" in response.data


def test_register_missing_fields(client):
    response = client.post("/register", data={
        "email": "", "password": "", "confirm_password": "",
        "nombre": "", "edad": "", "nivel_educativo": "", "intereses": "",
    }, follow_redirects=True)
    assert b"completa todos" in response.data


def test_register_duplicate_email(client):
    email = register_user(client)
    response = client.post("/register", data={
        "email": email, "password": "newpass123", "confirm_password": "newpass123",
        "nombre": "T2", "edad": "20", "nivel_educativo": "universidad", "intereses": "m",
    }, follow_redirects=True)
    assert b"ya est" in response.data


# ─────────────────────── Login ───────────────────────

def test_login_get_renders(client):
    response = client.get("/login")
    assert response.status_code == 200


def test_login_success(client):
    email = register_user(client)
    response = login_user(client, email)
    assert response.status_code == 200


def test_login_wrong_password(client):
    email = register_user(client)
    response = login_user(client, email, password="wrong")
    assert b"Contrase" in response.data or b"Error" in response.data


def test_login_user_not_found(client):
    response = login_user(client, "noexiste@test.com")
    assert b"no encontrado" in response.data.lower() or b"Error" in response.data


def test_login_missing_fields(client):
    response = client.post("/login", data={"email": "", "password": ""}, follow_redirects=True)
    assert b"completa" in response.data


# ─────────────────────── Logout ───────────────────────

def test_logout_clears_session(client):
    email = register_user(client)
    login_user(client, email)
    with client.session_transaction() as sess:
        assert "user" in sess
    response = client.get("/logout")
    assert response.status_code == 302
    assert "/login" in response.location


# ─────────────────────── Index ───────────────────────

def test_index_redirects_to_visual(client):
    email = register_user(client)
    login_user(client, email)
    response = client.post("/", data={
        "tema": "Media aritmética y ponderada",
        "estilo": "Visual",
    })
    assert response.status_code == 302
    assert "/visual" in response.location


def test_index_redirects_to_practico(client):
    email = register_user(client)
    login_user(client, email)
    response = client.post("/", data={
        "tema": "Probabilidad básica",
        "estilo": "Práctico",
    })
    assert response.status_code == 302
    assert "/practico" in response.location


def test_index_rejects_invalid_tema(client):
    email = register_user(client)
    login_user(client, email)
    response = client.post("/", data={
        "tema": "Tema inventado que no existe",
        "estilo": "Visual",
    }, follow_redirects=True)
    assert b"no es v" in response.data or b"v" in response.data


def test_index_rejects_missing_fields(client):
    email = register_user(client)
    login_user(client, email)
    response = client.post("/", data={"tema": "", "estilo": ""}, follow_redirects=True)
    assert b"completa" in response.data


def test_index_renders_for_authenticated(client):
    email = register_user(client)
    login_user(client, email)
    response = client.get("/")
    assert response.status_code == 200
    assert b"Estad" in response.data or b"tema" in response.data.lower()


# ─────────────────────── Visual ───────────────────────

def test_visual_renders(client):
    email = register_user(client)
    login_user(client, email)
    with patch("app.buscar_videos_youtube", return_value=[("Video A", "https://youtube.com/watch?v=abc123")]):
        response = client.get("/visual?tema=Media%20aritm%C3%A9tica%20y%20ponderada")
    assert response.status_code == 200


def test_visual_without_tema_uses_default(client):
    email = register_user(client)
    login_user(client, email)
    with patch("app.buscar_videos_youtube", return_value=[]):
        response = client.get("/visual")
    assert response.status_code == 200
    assert b"Tema no especificado" in response.data


# ─────────────────────── Practico ───────────────────────

def test_practico_renders(client):
    email = register_user(client)
    login_user(client, email)
    response = client.get("/practico?tema=Probabilidad%20b%C3%A1sica")
    assert response.status_code == 200


def test_practico_without_tema_redirects(client):
    email = register_user(client)
    login_user(client, email)
    response = client.get("/practico", follow_redirects=True)
    assert response.status_code == 200


# ─────────────────────── Perfil ───────────────────────

def test_perfil_renders_authenticated(client):
    email = register_user(client)
    login_user(client, email)
    response = client.get("/perfil")
    assert response.status_code == 200
    assert b"Test User" in response.data
