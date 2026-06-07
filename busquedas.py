"""
busquedas.py
============
Búsqueda de videos educativos en YouTube con verificación de disponibilidad.

Flujo:
  1. Scraping de la página de resultados de YouTube → lista de videoIds
  2. Verificación en paralelo de cada ID contra la API oEmbed de YouTube
     (gratuita, sin API key — retorna 200 si el video es embeddable,
      401/404 si es privado, eliminado o no disponible)
  3. Se devuelven solo los videos confirmados disponibles

De esta forma el usuario nunca verá "Video unavailable" ni "Content not available"
en el modo Visual.
"""

import requests
import re
from typing import List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── Constantes ──────────────────────────────────────────────────────────────
_OEMBED_URL   = "https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={vid}&format=json"
_SEARCH_URL   = "https://www.youtube.com/results?search_query={query}"
_WATCH_URL    = "https://www.youtube.com/watch?v={vid}"

# Cuántos candidatos revisar por cada video que necesitamos
# (margen para absorber los no disponibles)
_CANDIDATOS_FACTOR = 4
_MAX_CANDIDATOS    = 24
_VERIFY_TIMEOUT    = 5   # segundos por verificación oEmbed
_SEARCH_TIMEOUT    = 10  # segundos para la búsqueda inicial
_MAX_WORKERS       = 10  # hilos paralelos para verificación

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# ── Función principal ────────────────────────────────────────────────────────

def buscar_videos_youtube(consulta: str, num: int = 5) -> List[Tuple[str, str]]:
    """
    Busca videos educativos en YouTube y devuelve solo los disponibles.

    Args:
        consulta: Término de búsqueda (ej. "Distribución normal Estadística")
        num:      Número de videos a devolver

    Returns:
        Lista de tuplas (título, url_watch) verificados como disponibles.
        Si no se encuentran suficientes, devuelve los que haya o el fallback.
    """
    try:
        # ── 1. Obtener IDs de la página de resultados ────────────────────
        video_ids = _scrape_video_ids(consulta)
        if not video_ids:
            print(f"[YouTube] Sin resultados para '{consulta}' — usando fallback")
            return _videos_fallback(consulta)

        # ── 2. Tomar candidatos suficientes para filtrar los no disponibles ─
        candidatos = video_ids[:min(num * _CANDIDATOS_FACTOR, _MAX_CANDIDATOS)]
        print(f"[YouTube] {len(candidatos)} candidatos para '{consulta}' → verificando disponibilidad…")

        # ── 3. Verificar en paralelo ──────────────────────────────────────
        disponibles = _verificar_en_paralelo(candidatos, necesarios=num)
        print(f"[YouTube] {len(disponibles)}/{len(candidatos)} videos disponibles")

        if not disponibles:
            print(f"[YouTube] Ningún video disponible — usando fallback")
            return _videos_fallback(consulta)

        # ── 4. Construir resultado final ──────────────────────────────────
        return [
            (f"Video sobre {consulta}", _WATCH_URL.format(vid=vid))
            for vid in disponibles[:num]
        ]

    except Exception as exc:
        print(f"[YouTube] Error en búsqueda: {exc}")
        return _videos_fallback(consulta)


# ── Helpers privados ────────────────────────────────────────────────────────

def _scrape_video_ids(consulta: str) -> List[str]:
    """Extrae IDs únicos de la página de resultados de YouTube."""
    query = consulta.replace(" ", "+")
    url   = _SEARCH_URL.format(query=query)
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=_SEARCH_TIMEOUT)
        html = resp.text
    except Exception as exc:
        print(f"[YouTube] Error al buscar: {exc}")
        return []

    # Dos patrones distintos para mayor robustez
    ids = list(dict.fromkeys(re.findall(r'"videoId":"([a-zA-Z0-9_-]{11})"', html)))
    if not ids:
        ids = list(dict.fromkeys(re.findall(r'videoId\":\"([a-zA-Z0-9_-]{11})', html)))
    return ids


def _verificar_video_disponible(video_id: str) -> bool:
    """
    Consulta la API oEmbed de YouTube para saber si el video es embeddable.

    Respuestas posibles:
      200 → video disponible y embeddable              ✅
      401 → video privado o con embedding desactivado  ❌
      404 → video eliminado o inexistente              ❌
      otros → tratar como no disponible por seguridad  ❌
    """
    try:
        url  = _OEMBED_URL.format(vid=video_id)
        resp = requests.get(url, timeout=_VERIFY_TIMEOUT)
        disponible = resp.status_code == 200
        if not disponible:
            print(f"[YouTube] Video {video_id} no disponible (HTTP {resp.status_code})")
        return disponible
    except Exception:
        # Timeout u otro error de red → descartar por seguridad
        print(f"[YouTube] Video {video_id} descartado (timeout/error de red)")
        return False


def _verificar_en_paralelo(video_ids: List[str], necesarios: int) -> List[str]:
    """
    Verifica todos los IDs candidatos en paralelo y devuelve
    los disponibles en el mismo orden en que aparecían originalmente.
    """
    resultados: dict[str, bool] = {}

    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as executor:
        futuros = {
            executor.submit(_verificar_video_disponible, vid): vid
            for vid in video_ids
        }
        for futuro in as_completed(futuros):
            vid = futuros[futuro]
            try:
                resultados[vid] = futuro.result()
            except Exception:
                resultados[vid] = False

    # Preservar el orden original de scraping
    return [vid for vid in video_ids if resultados.get(vid, False)]


def _videos_fallback(consulta: str) -> List[Tuple[str, str]]:
    """Mensaje de fallback cuando no se encuentran videos disponibles."""
    return [
        ("No se pudieron cargar videos en este momento", ""),
        ("Intenta buscar manualmente en YouTube", ""),
    ]