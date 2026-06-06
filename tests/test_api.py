"""
Tests para los endpoints de API: /generar_preguntas y /evaluar_respuestas
Gemini se mockea para evitar llamadas reales.
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
        # Resetear singleton de GeminiService entre tests
        app._gemini_service = None
        yield client
        app._gemini_service = None


def mock_gemini_service():
    """Crea un mock que reemplaza a get_gemini_service() con una instancia falsa."""
    mock = MagicMock()
    return patch("app.get_gemini_service", return_value=mock), mock


def register_and_login(client):
    email = f"user_{uuid.uuid4().hex[:8]}@test.com"
    client.post("/register", data={
        "email": email,
        "password": "password123",
        "confirm_password": "password123",
        "nombre": "Test",
        "edad": "20",
        "nivel_educativo": "universidad",
        "intereses": "estadistica",
    }, follow_redirects=True)
    client.post("/login", data={"email": email, "password": "password123"}, follow_redirects=True)
    return email


def fake_preguntas():
    return [
        {"id": 1, "tipo": "opcion_multiple", "pregunta": "¿Pregunta 1?",
         "opciones": {"A": "A", "B": "B", "C": "C", "D": "D"},
         "respuesta_correcta": "A", "explicacion": "Porque A"},
        {"id": 2, "tipo": "verdadero_falso", "pregunta": "Afirmación 2",
         "opciones": {"A": "Verdadero", "B": "Falso"},
         "respuesta_correcta": "A", "explicacion": "Explicación 2"},
        {"id": 3, "tipo": "respuesta_abierta", "pregunta": "Explica X",
         "opciones": None, "respuesta_correcta": "Concepto X",
         "explicacion": "Detalle de X"},
    ]


# ─────────────────────── /generar_preguntas ───────────────────────

def test_generar_preguntas_requires_auth(client):
    response = client.post("/generar_preguntas", json={"tema": "X"})
    assert response.status_code == 302
    assert "/login" in response.location


def test_generar_preguntas_missing_tema(client):
    register_and_login(client)
    response = client.post("/generar_preguntas", json={})
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is False
    assert "tema" in data["error"].lower()


def test_generar_preguntas_success(client):
    register_and_login(client)
    patcher, mock = mock_gemini_service()
    with patcher:
        mock.generar_preguntas.return_value = fake_preguntas()
        response = client.post("/generar_preguntas", json={"tema": "Probabilidad básica"})
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert len(data["preguntas"]) == 3


def test_generar_preguntas_handles_exception(client):
    register_and_login(client)
    patcher, mock = mock_gemini_service()
    with patcher:
        mock.generar_preguntas.side_effect = Exception("API caída")
        response = client.post("/generar_preguntas", json={"tema": "X"})
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is False
    assert "API" in data["error"]


# ─────────────────────── /evaluar_respuestas ───────────────────────

def test_evaluar_respuestas_requires_auth(client):
    response = client.post("/evaluar_respuestas", json={"tema": "X", "preguntas": [], "respuestas": {}})
    assert response.status_code == 302
    assert "/login" in response.location


def test_evaluar_respuestas_incomplete_data(client):
    register_and_login(client)
    response = client.post("/evaluar_respuestas", json={"tema": "X"})
    data = response.get_json()
    assert data["success"] is False
    assert "incompletos" in data["error"]


def test_evaluar_respuestas_success_multiple_choice(client):
    register_and_login(client)
    preguntas = fake_preguntas()
    respuestas = {"1": "A", "2": "B", "3": "Concepto X"}
    response = client.post("/evaluar_respuestas", json={
        "tema": "Probabilidad", "preguntas": preguntas, "respuestas": respuestas,
    })
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["puntaje_final"] == 50.0  # 1/2 closed questions correct
    assert len(data["respuestas"]) == 3
    assert data["respuestas"][0]["correcta"] is True
    assert data["respuestas"][1]["correcta"] is False
    assert data["respuestas"][2]["correcta"] is None


def test_evaluar_respuestas_saves_history(client):
    register_and_login(client)
    preguntas = fake_preguntas()
    respuestas = {"1": "A", "2": "A", "3": "X"}
    response = client.post("/evaluar_respuestas", json={
        "tema": "Estadística", "preguntas": preguntas, "respuestas": respuestas,
    })
    assert response.status_code == 200

    from db_config import StudentData
    with client.session_transaction() as sess:
        user_id = sess["user"]
    data = StudentData.get_student_data(user_id)["data"]
    assert "Estadística" in data["progreso"]
    assert data["progreso"]["Estadística"]["ejercicios_completados"] == 1
    assert len(data["historial_evaluaciones"]) == 1
    assert data["historial_evaluaciones"][0]["tema"] == "Estadística"


def test_evaluar_respuestas_handles_exception(client):
    register_and_login(client)
    with patch("app.StudentData.update_student_progress", side_effect=Exception("Falla DB")):
        response = client.post("/evaluar_respuestas", json={
            "tema": "X", "preguntas": fake_preguntas(), "respuestas": {"1": "A", "2": "A", "3": "X"},
        })
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is False
    assert "Falla DB" in data["error"]
