#!/usr/bin/env python3
"""
Genera banco_preguntas.json con preguntas REALES de la API de Gemini.
Genera ~10 preguntas por tema para el nivel 'universidad'.
Ejecutar una sola vez (o cuando se quieran refrescar las preguntas).

Uso: .venv/bin/python generar_banco.py
"""

import json
import os
import sys
import time
import hashlib
import argparse
from pathlib import Path
from typing import Any, List, Optional

from dotenv import load_dotenv

load_dotenv()

from google import genai
from google.genai import types as genai_types

from temas import temas as TEMAS_DICT

# ──────────────────────────────────────────────
# Configuración
# ──────────────────────────────────────────────
API_KEY = os.getenv("GEMINI_API_KEY")
MODEL   = os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest")
BANCO_PATH = Path("data/banco_preguntas.json")

NIVEL_DEFAULT = "universidad"
PREGUNTAS_POR_TEMA_DEFAULT = 20   # número de preguntas a generar por tema
DELAY_ENTRE_TEMAS  = 8    # segundos entre llamadas (evitar rate-limit)
MAX_REINTENTOS     = 3

# ──────────────────────────────────────────────
# Cliente Gemini
# ──────────────────────────────────────────────
client = genai.Client(api_key=API_KEY)

# ──────────────────────────────────────────────
# Prompts
# ──────────────────────────────────────────────
SYSTEM_PROMPT = (
    "Eres un experto en estadística que genera preguntas educativas de alta calidad para "
    "un bootcamp universitario. Crea preguntas específicas, rigurosas y pedagógicamente "
    "sólidas. Las preguntas deben evaluar comprensión real: aplicación, análisis e "
    "interpretación — no solo memorización de definiciones. "
    "Los distractores en opción múltiple deben ser errores conceptuales comunes y verosímiles. "
    "Responde ÚNICAMENTE con un array JSON válido. Sin texto extra, sin markdown, sin bloques ```."
)

def hacer_user_prompt(tema: dict, nivel: str, cantidad: int) -> str:
    conceptos = ", ".join(tema.get("conceptos_clave", [tema["nombre"]]))
    desc = tema.get("descripcion", f"Tema de estadística: {tema['nombre']}")

    nivel_info = {
        "bachillerato": "nivel introductorio, conceptos básicos, ejemplos cotidianos",
        "universidad":  "nivel universitario, fórmulas, cálculo y aplicaciones reales",
        "postgrado":    "nivel avanzado, demostraciones, casos prácticos complejos",
    }.get(nivel, "nivel universitario")

    return f"""Tema: {tema["nombre"]}
Nivel: {nivel.upper()} — {nivel_info}
Descripción: {desc}
Conceptos clave a cubrir: {conceptos}

Genera exactamente {cantidad} preguntas variadas sobre este tema.
Distribución: ~50% opcion_multiple, ~25% verdadero_falso, ~25% respuesta_abierta

REGLAS:
- opcion_multiple: 4 opciones A/B/C/D con distractores que representen errores reales de estudiantes
- verdadero_falso: afirmaciones no triviales (evalúan matices, no definiciones obvias)
- respuesta_abierta: pide cálculo, interpretación o comparación con datos concretos
- explicacion: 2–3 oraciones que enseñen el concepto, no solo indiquen la respuesta correcta
- Cada pregunta debe cubrir al menos uno de los conceptos clave
- opciones = null para respuesta_abierta
- Para verdadero_falso: opciones = {{"A": "Verdadero", "B": "Falso"}}

Devuelve SOLO el array JSON con objetos de este esquema exacto:
[
  {{
    "id": 1,
    "tipo": "opcion_multiple",
    "pregunta": "...",
    "opciones": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
    "respuesta_correcta": "A",
    "explicacion": "..."
  }}
]
"""


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────
def id_estable(pregunta_texto: str, tema: str) -> str:
    raw = f"{tema}::{pregunta_texto}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def parsear_respuesta(texto: str, tema_nombre: str) -> list[dict[str, Any]]:
    """Extrae el array JSON de la respuesta del modelo."""
    texto = texto.strip()

    # quitar bloques markdown si el modelo los incluye
    if texto.startswith("```"):
        lineas = texto.splitlines()
        texto = "\n".join(l for l in lineas if not l.startswith("```"))

    # buscar el primer '[' y el último ']'
    inicio = texto.find("[")
    fin    = texto.rfind("]")
    if inicio == -1 or fin == -1:
        raise ValueError("No se encontró array JSON en la respuesta")

    raw_json = texto[inicio:fin + 1]
    preguntas = json.loads(raw_json)

    resultado = []
    for p in preguntas:
        if not isinstance(p, dict):
            continue
        if not all(k in p for k in ("tipo", "pregunta", "respuesta_correcta", "explicacion")):
            continue
        tipo = p.get("tipo", "")
        if tipo not in ("opcion_multiple", "verdadero_falso", "respuesta_abierta"):
            continue

        # Añadir id_estable
        p["id_estable"] = id_estable(str(p["pregunta"]), tema_nombre)
        p["es_fallback"] = False   # estas son preguntas REALES
        resultado.append(p)

    return resultado


def generar_preguntas_tema(tema: dict, nivel: str, cantidad: int) -> list[dict]:
    """Genera preguntas para un tema y nivel con reintentos."""
    user_prompt = hacer_user_prompt(tema, nivel, cantidad)
    config = genai_types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        temperature=0.7,
        max_output_tokens=8192,
        response_mime_type="application/json",
    )

    for intento in range(MAX_REINTENTOS):
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=user_prompt,
                config=config,
            )
            preguntas = parsear_respuesta(response.text, tema["nombre"])
            print(f"    ✓ {len(preguntas)} preguntas generadas")
            return preguntas

        except Exception as e:
            espera = (intento + 1) * 5
            print(f"    ✗ Intento {intento + 1}/{MAX_REINTENTOS} fallido: {e}")
            if intento < MAX_REINTENTOS - 1:
                print(f"      Reintentando en {espera}s...")
                time.sleep(espera)

    print(f"    ✗ No se pudieron generar preguntas para '{tema['nombre']}'")
    return []


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────
def parsear_argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Genera banco de preguntas para la plataforma IA Educativa.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  python generar_banco.py                          # Genera 20 preguntas para 'universidad'
  python generar_banco.py --nivel postgrado        # Genera 20 preguntas para 'postgrado'
  python generar_banco.py --nivel todos            # Genera para los 3 niveles (~6 min)
  python generar_banco.py --cantidad 5             # Solo 5 preguntas por tema (rápido)
  python generar_banco.py --nivel bachillerato --cantidad 10  # Demo rápida de ~2 min
        """,
    )
    parser.add_argument(
        "--nivel",
        choices=["bachillerato", "universidad", "postgrado", "todos"],
        default="universidad",
        help="Nivel académico para el cual generar preguntas (default: universidad)",
    )
    parser.add_argument(
        "--cantidad",
        type=int,
        default=PREGUNTAS_POR_TEMA_DEFAULT,
        help=f"Número de preguntas por tema (default: {PREGUNTAS_POR_TEMA_DEFAULT})",
    )
    return parser.parse_args()


def main():
    args = parsear_argumentos()
    nivel = args.nivel
    cantidad = args.cantidad

    if not API_KEY:
        print("ERROR: GEMINI_API_KEY no está configurada")
        sys.exit(1)

    # Determinar lista de niveles a procesar
    if nivel == "todos":
        niveles = ["bachillerato", "universidad", "postgrado"]
    else:
        niveles = [nivel]

    # Cargar banco existente (para no perder preguntas anteriores)
    if BANCO_PATH.exists():
        with open(BANCO_PATH) as f:
            banco = json.load(f)
        print(f"Banco existente cargado: {BANCO_PATH}")
    else:
        banco = {"version": "2.0", "temas": {}}
        print("Creando banco nuevo...")

    temas_lista = TEMAS_DICT.get("Estadística", [])
    # Filtrar duplicados por nombre
    vistos = set()
    temas_unicos = []
    for t in temas_lista:
        if t["nombre"] not in vistos:
            vistos.add(t["nombre"])
            temas_unicos.append(t)

    total_temas = len(temas_unicos)
    total_niveles = len(niveles)
    print(f"\nGenerando {cantidad} preguntas para {total_temas} temas × {total_niveles} nivel(es): {', '.join(niveles)}\n")

    inicio = time.time()
    total_agregadas = 0

    for nivel_actual in niveles:
        print(f"{'='*60}")
        print(f" NIVEL: {nivel_actual.upper()}")
        print(f"{'='*60}")

        for i, tema in enumerate(temas_unicos, 1):
            nombre = tema["nombre"]
            print(f"\n[{i:2d}/{total_temas}] {nombre}")

            # Inicializar estructura si no existe
            banco["temas"].setdefault(nombre, {}).setdefault(nivel_actual, [])
            existentes = banco["temas"][nombre][nivel_actual]
            ids_existentes = {p.get("id_estable") for p in existentes if p.get("id_estable")}

            nuevas = generar_preguntas_tema(tema, nivel_actual, cantidad)
            agregadas = 0
            for p in nuevas:
                if p.get("id_estable") not in ids_existentes:
                    existentes.append(p)
                    ids_existentes.add(p["id_estable"])
                    agregadas += 1
            total_agregadas += agregadas

            print(f"    → {agregadas} nuevas agregadas ({len(existentes)} total en banco)")

            # Guardar progreso después de cada tema
            with open(BANCO_PATH, "w", encoding="utf-8") as f:
                json.dump(banco, f, ensure_ascii=False, indent=2)

            if i < total_temas:
                time.sleep(DELAY_ENTRE_TEMAS)

    # Estadísticas finales
    duracion = time.time() - inicio
    minutos = int(duracion // 60)
    segundos = int(duracion % 60)

    print("\n" + "="*60)
    print(" RESUMEN FINAL")
    print("="*60)
    total_preguntas = 0
    for nombre, niveles_dict in banco["temas"].items():
        count = sum(len(ps) for ps in niveles_dict.values())
        total_preguntas += count
        # Mostrar desglose por nivel
        desglose = ", ".join(f"{n}:{len(ps)}" for n, ps in niveles_dict.items())
        print(f"  {nombre}: {count} preguntas ({desglose})")
    print(f"\nTOTAL: {total_preguntas} preguntas en banco")
    print(f"Agregadas en esta ejecución: {total_agregadas}")
    print(f"Tiempo total: {minutos}m {segundos}s")
    print(f"Banco guardado en: {BANCO_PATH.absolute()}")


if __name__ == "__main__":
    main()
