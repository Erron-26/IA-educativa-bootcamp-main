import requests
import re
from typing import List, Tuple

def buscar_videos_youtube(consulta: str, num: int = 5) -> List[Tuple[str, str]]:
    """Busca videos educativos en YouTube sin API."""
    resultados = []
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }

        query = consulta.replace(" ", "+")
        url = f"https://www.youtube.com/results?search_query={query}"
        resp = requests.get(url, headers=headers, timeout=10)
        html = resp.text

        # Intentar extraer IDs con dos patrones distintos
        video_ids = list(set(re.findall(r'"videoId":"([a-zA-Z0-9_-]{11})"', html)))
        if not video_ids:
            video_ids = list(set(re.findall(r'videoId\":\"([a-zA-Z0-9_-]{11})', html)))

        if not video_ids:
            return _videos_fallback(consulta)

        for vid in video_ids[:num]:
            link = f"https://www.youtube.com/watch?v={vid}"
            resultados.append((f"Video sobre {consulta}", link))

        return resultados

    except Exception as e:
        print(f"Error en búsqueda YouTube: {e}")
        return _videos_fallback(consulta)


def _videos_fallback(consulta: str) -> List[Tuple[str, str]]:
    """Videos de respaldo cuando falla el scraping."""
    return [
        ("No se pudieron cargar videos automáticos", ""),
        ("Intenta buscar manualmente en YouTube", "")
    ]