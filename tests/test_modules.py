"""
Tests para módulos de soporte: busquedas, temas, gemini_service (mockeado)
"""
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from unittest.mock import patch


# ─────────────────────── busquedas ───────────────────────

def test_buscar_videos_youtube_returns_list():
    from busquedas import buscar_videos_youtube
    with patch("busquedas.requests.get") as mock_get:
        mock_get.return_value.text = (
            '"videoId":"abc123def45"'
            '"videoId":"xyz987uvw65"'
        )
        mock_get.return_value.status_code = 200
        resultados = buscar_videos_youtube("estadística", num=2)
    assert isinstance(resultados, list)
    assert len(resultados) <= 2
    for titulo, link in resultados:
        assert isinstance(titulo, str)
        assert isinstance(link, str)
        if link:
            assert "v=" in link


def test_buscar_videos_youtube_no_results():
    from busquedas import buscar_videos_youtube, _videos_fallback
    with patch("busquedas.requests.get") as mock_get:
        mock_get.return_value.text = "<html>no videos here</html>"
        resultados = buscar_videos_youtube("xyz_no_match")
    assert isinstance(resultados, list)
    assert len(resultados) >= 1


def test_buscar_videos_youtube_handles_request_exception():
    from busquedas import buscar_videos_youtube
    with patch("busquedas.requests.get", side_effect=Exception("network down")):
        resultados = buscar_videos_youtube("test")
    assert isinstance(resultados, list)


# ─────────────────────── temas ───────────────────────

def test_temas_has_estadistica():
    from temas import temas
    assert "Estadística" in temas
    assert isinstance(temas["Estadística"], list)
    assert len(temas["Estadística"]) > 0


def test_temas_contains_basic_concepts():
    from temas import temas
    lista = temas["Estadística"]
    nombres = [t["nombre"] for t in lista]
    assert "Fundamentos y Análisis Descriptivo" in nombres
    assert "Medidas Estadísticas" in nombres
    assert "Fundamentos de Probabilidad" in nombres


# ─────────────────────── gemini_service ───────────────────────

def test_gemini_service_requires_api_key(monkeypatch):
    from gemini_service import GeminiService
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        GeminiService()


def test_gemini_service_uses_default_model(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake_key_for_test")
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    with patch("gemini_service.genai.Client") as MockClient:
        from gemini_service import GeminiService
        service = GeminiService()
    assert service.model_name == "gemini-flash-lite-latest"


def test_gemini_service_respects_custom_model(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake_key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-pro")
    with patch("gemini_service.genai.Client"):
        from gemini_service import GeminiService
        service = GeminiService()
    assert service.model_name == "gemini-2.5-pro"


def test_gemini_evaluar_respuesta_multiple_choice(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake_key")
    with patch("gemini_service.genai.Client"):
        from gemini_service import GeminiService
        service = GeminiService()
    pregunta = {
        "tipo": "opcion_multiple",
        "pregunta": "¿Cuál es X?",
        "opciones": {"A": "1", "B": "2", "C": "3", "D": "4"},
        "respuesta_correcta": "B",
        "explicacion": "Es B",
    }
    res_correcta = service.evaluar_respuesta(pregunta, "B")
    assert res_correcta["correcta"] is True
    assert res_correcta["puntaje"] == 1

    res_incorrecta = service.evaluar_respuesta(pregunta, "A")
    assert res_incorrecta["correcta"] is False
    assert res_incorrecta["puntaje"] == 0


def test_gemini_evaluar_respuesta_true_false(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake_key")
    with patch("gemini_service.genai.Client"):
        from gemini_service import GeminiService
        service = GeminiService()
    pregunta = {
        "tipo": "verdadero_falso",
        "pregunta": "Afirmación",
        "opciones": {"A": "Verdadero", "B": "Falso"},
        "respuesta_correcta": "A",
        "explicacion": "Es verdadero",
    }
    assert service.evaluar_respuesta(pregunta, "A")["correcta"] is True
    assert service.evaluar_respuesta(pregunta, "B")["correcta"] is False


def test_gemini_obtener_info_nivel_fallback(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake_key")
    with patch("gemini_service.genai.Client"):
        from gemini_service import GeminiService
        service = GeminiService()
    info = service._obtener_info_nivel("nivel_inexistente")
    assert info == service._obtener_info_nivel("universidad")
