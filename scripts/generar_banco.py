"""
Genera el banco de preguntas estático.

Uso: python3 scripts/generar_banco.py

Genera 20 preguntas por cada tema (nivel universidad) y las guarda en
data/banco_preguntas.json. Si Gemini falla para un tema, usa el fallback
inteligente con conceptos_clave para completarlo. Todos los 25 temas
quedan siempre cubiertos.
"""

import os
import sys
import json
import hashlib
import time
from datetime import datetime
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
load_dotenv()

from temas import temas
from gemini_service import GeminiService


CANTIDAD_POR_TEMA = 20
NIVEL = "universidad"
RUTA_SALIDA = "data/banco_preguntas.json"


def id_estable(pregunta: dict) -> str:
    return hashlib.md5(
        str(pregunta.get("pregunta", "")).encode()
    ).hexdigest()[:12]


def main():
    print("=" * 60)
    print("Generador de banco de preguntas")
    print(f"  Temas: {len(temas['Estadística'])}")
    print(f"  Preguntas por tema: {CANTIDAD_POR_TEMA}")
    print(f"  Nivel: {NIVEL}")
    print(f"  Salida: {RUTA_SALIDA}")
    print("=" * 60)

    try:
        gemini = GeminiService()
        puede_usar_gemini = True
    except ValueError as e:
        print(f"\n⚠️  {e}")
        print("   El banco se generará con fallbacks por tema (sin API).")
        puede_usar_gemini = False
        gemini = None

    banco = {"temas": {}}
    exitos = 0
    fallos_live = 0
    fallos_total = 0

    for idx, tema in enumerate(temas["Estadística"], start=1):
        nombre = tema["nombre"]
        descripcion = tema.get("descripcion", "")
        conceptos_clave = tema.get("conceptos_clave", [])

        print(f"\n[{idx}/{len(temas['Estadística'])}] {nombre}...", end=" ", flush=True)

        preguntas = []

        if puede_usar_gemini and gemini:
            try:
                preguntas = gemini.generar_preguntas(
                    tema_nombre=nombre,
                    nivel_academico=NIVEL,
                    cantidad=CANTIDAD_POR_TEMA,
                    descripcion=descripcion,
                    conceptos_clave=conceptos_clave,
                    solo_banco=True,
                )

                if preguntas and not preguntas[0].get("es_fallback"):
                    print(f"✅ {len(preguntas)} preguntas de Gemini")
                    exitos += 1
                else:
                    raise ValueError("Gemini devolvió fallback")
            except Exception as e:
                print(f"\n     ⚠️  Gemini falló: {e}")
                fallos_live += 1
                preguntas = []

        if not preguntas:
            print("   → generando fallback con conceptos_clave...", end=" ", flush=True)
            if gemini:
                preguntas = gemini._preguntas_fallback(
                    nombre, CANTIDAD_POR_TEMA, conceptos_clave, descripcion
                )
            else:
                from gemini_service import GeminiService as _GS
                _gs = _GS.__new__(_GS)
                preguntas = _gs._preguntas_fallback(
                    nombre, CANTIDAD_POR_TEMA, conceptos_clave, descripcion
                )
            fallos_total += 1
            print(f"✅ {len(preguntas)} preguntas (fallback)")

        for p in preguntas:
            p["id_estable"] = id_estable(p)

        banco["temas"][nombre] = {NIVEL: preguntas}

        time.sleep(1.5)

    banco["meta"] = {
        "version": 1,
        "generated_at": datetime.now().isoformat(),
        "model": "gemini-2.5-flash / fallback",
        "total_temas": len(temas["Estadística"]),
        "preguntas_por_tema": CANTIDAD_POR_TEMA,
    }

    os.makedirs(os.path.dirname(RUTA_SALIDA), exist_ok=True)
    with open(RUTA_SALIDA, "w", encoding="utf-8") as f:
        json.dump(banco, f, ensure_ascii=False, indent=2)

    total_preguntas = sum(
        len(v.get(NIVEL, [])) for v in banco["temas"].values()
    )

    print("\n" + "=" * 60)
    print("RESUMEN:")
    print(f"  Temas con Gemini:  {exitos}/{len(temas['Estadística'])}")
    print(f"  Fallos en Gemini:  {fallos_live}")
    print(f"  Fallbacks usados:  {fallos_total}")
    print(f"  Total preguntas:   {total_preguntas}")
    print(f"  Archivo:           {RUTA_SALIDA}")
    print(f"  Tamaño:            {os.path.getsize(RUTA_SALIDA) / 1024:.1f} KB")
    print("=" * 60)


if __name__ == "__main__":
    main()
