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
                "Chrome/110.0 Safari/537.36"
            )
        }

        query = consulta.replace(" ", "+")
        url = f"https://www.youtube.com/results?search_query={query}"
        resp = requests.get(url, headers=headers, timeout=10)
        html = resp.text

        video_ids = list(set(re.findall(r'"videoId":"([a-zA-Z0-9_-]{11})"', html)))

        if not video_ids:
            return [("Sin resultados", "No se encontraron videos.")]

        for vid in video_ids[:num]:
            link = f"https://www.youtube.com/watch?v={vid}"
            resultados.append(("Video educativo encontrado", link))

        return resultados

    except Exception as e:
        return [("Error", str(e))]
