"""
Tests para db_config: LocalAuth y StudentData
"""
import sys
import os
import uuid

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from db_config import LocalAuth, StudentData, get_db, initialize_db


@pytest.fixture(autouse=True)
def clean_db():
    initialize_db()
    with get_db() as conn:
        conn.execute("DELETE FROM students")
        conn.execute("DELETE FROM users")
        conn.commit()
    yield


def unique_email():
    return f"user_{uuid.uuid4().hex[:8]}@test.com"


def test_register_user_success():
    email = unique_email()
    result = LocalAuth.register_user(email, "password123")
    assert result["success"] is True
    assert result["user"]["email"] == email
    assert "localId" in result["user"]


def test_register_user_duplicate_email():
    email = unique_email()
    LocalAuth.register_user(email, "password123")
    result = LocalAuth.register_user(email, "password456")
    assert result["success"] is False
    assert "ya está registrado" in result["error"]


def test_register_user_normalizes_email():
    email = unique_email()
    result1 = LocalAuth.register_user(email.upper(), "password123")
    result2 = LocalAuth.register_user(email.lower(), "password456")
    assert result1["success"] is True
    assert result2["success"] is False


def test_login_user_success():
    email = unique_email()
    LocalAuth.register_user(email, "password123")
    result = LocalAuth.login_user(email, "password123")
    assert result["success"] is True
    assert "localId" in result["user"]


def test_login_user_wrong_password():
    email = unique_email()
    LocalAuth.register_user(email, "password123")
    result = LocalAuth.login_user(email, "wrong_password")
    assert result["success"] is False
    assert "Contraseña incorrecta" in result["error"]


def test_login_user_not_found():
    result = LocalAuth.login_user("noexiste@test.com", "any")
    assert result["success"] is False
    assert "no encontrado" in result["error"].lower()


def test_login_strips_whitespace():
    email = unique_email()
    LocalAuth.register_user(email, "password123")
    result = LocalAuth.login_user(f"  {email}  ", "password123")
    assert result["success"] is True


def test_password_is_hashed_not_plain():
    email = unique_email()
    LocalAuth.register_user(email, "supersecret")
    with get_db() as conn:
        row = conn.execute("SELECT password_hash FROM users WHERE email = ?", (email,)).fetchone()
    assert "supersecret" not in row["password_hash"]
    assert row["password_hash"].startswith("scrypt:") or row["password_hash"].startswith("pbkdf2:")


def test_save_and_get_student_data():
    user_id = str(uuid.uuid4())
    with get_db() as conn:
        conn.execute(
            "INSERT INTO users (id, email, password_hash) VALUES (?, ?, ?)",
            (user_id, f"{user_id}@x.com", "scrypt:hash")
        )
        conn.commit()
    data = {"nombre": "Test User", "email": "test@test.com", "edad": 25, "progreso": {}}
    save = StudentData.save_student_data(user_id, data)
    assert save["success"] is True

    get = StudentData.get_student_data(user_id)
    assert get["success"] is True
    assert get["data"]["nombre"] == "Test User"
    assert get["data"]["edad"] == 25


def test_get_student_data_not_found():
    get = StudentData.get_student_data(str(uuid.uuid4()))
    assert get["success"] is False


def _create_user(user_id=None):
    user_id = user_id or str(uuid.uuid4())
    with get_db() as conn:
        conn.execute(
            "INSERT INTO users (id, email, password_hash) VALUES (?, ?, ?)",
            (user_id, f"{user_id}@x.com", "scrypt:hash")
        )
        conn.commit()
    return user_id


def test_update_student_progress_creates_entry():
    user_id = _create_user()
    StudentData.save_student_data(user_id, {"nombre": "Test", "progreso": {}})
    result = StudentData.update_student_progress(user_id, "Estadística", ejercicio_completado=False)
    assert result["success"] is True

    data = StudentData.get_student_data(user_id)["data"]
    assert "Estadística" in data["progreso"]
    assert data["progreso"]["Estadística"]["ultimo_acceso"]["tipo"] == "visualizacion"


def test_update_student_progress_increments_exercises():
    user_id = _create_user()
    StudentData.save_student_data(user_id, {"nombre": "Test", "progreso": {}})
    StudentData.update_student_progress(user_id, "Probabilidad", ejercicio_completado=True)
    StudentData.update_student_progress(user_id, "Probabilidad", ejercicio_completado=True)

    data = StudentData.get_student_data(user_id)["data"]
    assert data["progreso"]["Probabilidad"]["ejercicios_completados"] == 2
    assert data["progreso"]["Probabilidad"]["ultimo_acceso"]["tipo"] == "ejercicio"


def test_save_evaluation_history_caps_at_50():
    user_id = _create_user()
    StudentData.save_student_data(user_id, {"nombre": "Test", "progreso": {}})

    for i in range(60):
        StudentData.save_evaluation_history(user_id, {"tema": "X", "puntaje": i, "fecha": str(i)})

    data = StudentData.get_student_data(user_id)["data"]
    assert len(data["historial_evaluaciones"]) == 50
    assert data["historial_evaluaciones"][-1]["puntaje"] == 59
    assert data["historial_evaluaciones"][0]["puntaje"] == 10
