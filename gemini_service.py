import os
import json
import re
import random as random_module
import hashlib
import threading
from google import genai
from google.genai import errors, types as genai_types
from typing import List, Dict, Any, Optional, Tuple, Set


_TERMINOS_ESTADISTICOS_GENERALES: Set[str] = {
    "dato", "datos", "muestra", "muestreo", "variable", "variables",
    "probabilidad", "probabilidades", "frecuencia", "gráfico", "grafico", "histograma",
    "media", "mediana", "moda", "varianza", "desviación", "desviacion", "distribución",
    "distribucion", "población", "poblacion", "parámetro", "parametro",
    "hipótesis", "hipotesis", "intervalo", "regresión", "regresion", "correlación",
    "correlacion", "anova", "binomial", "normal", "gauss", "tendencia",
    "dispersión", "dispersion", "rango", "cuartil", "outlier", "atípico", "atipico",
    "promedio", "suma", "sumatoria", "tendencia central", "sesgo", "asimetría", "asimetria",
    "curtosis", "poisson", "chi-cuadrado", "chi cuadrado", "t-student", "t student",
    "estadístico", "estadistico", "estadística", "estadistica", "inferencia", "descriptiva",
    "media muestral", "media poblacional", "error", "margen", "significancia", "valor p",
    "p-value", "p value", "gráfico de barras", "grafico de barras", "polígono", "poligono",
    "ojiva", "diagrama", "tabla", "frecuencia absoluta", "frecuencia relativa",
    "frecuencia acumulada", "marca de clase", "amplitud", "rango intercuartílico",
    "rango intercuartilico", "iqr", "coeficiente", "correlación de pearson",
    "correlacion de pearson", "mínimos cuadrados", "minimos cuadrados",
    "coeficiente de determinación", "coeficiente de determinacion", "residuo", "residuos",
    "serie temporal", "series temporales", "estacionalidad", "ruido", "promedio móvil",
    "promedio movil", "suma de cuadrados", "estadístico f", "estadistico f",
    "factor", "teorema del límite central", "teorema del limite central",
    "distribución muestral", "distribucion muestral", "eventos independientes",
    "eventos dependientes", "probabilidad condicional", "teorema de bayes", "bayes",
    "ensayo de bernoulli", "ensayos de bernoulli", "éxito", "exito", "fracaso",
    "coeficiente de variación", "coeficiente de variacion", "cv", "c(n,k)",
}

_cache_lock = threading.Lock()


class BancoPreguntas:
    RUTA_BANCO = "data/banco_preguntas.json"
    RUTA_CACHE = "data/banco_cache.json"
    MAX_POR_TEMA = 20

    _instancia = None
    _banco = None
    _cache = None

    def __new__(cls):
        if cls._instancia is None:
            cls._instancia = super().__new__(cls)
        return cls._instancia

    def __init__(self):
        if type(self)._banco is None:
            type(self)._banco = self._cargar(self.RUTA_BANCO)
            type(self)._cache = self._cargar(self.RUTA_CACHE)

    def _cargar(self, ruta: str) -> dict:
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {"temas": {}}

    # Mapeo de temas con nombres alternativos → categorías canónicas.
    # Permite aprovechar mejor el banco cuando el usuario escribe el tema
    # con un nombre distinto al que está guardado en el JSON.
    _ALIAS_TEMAS: Dict[str, List[str]] = {
        "conceptos básicos de estadística": [
            "Conceptos básicos de estadística",
            "Fundamentos y Análisis Descriptivo",
        ],
        "tipos de variables y escalas de medición": [
            "Tipos de variables y escalas de medición",
            "Fundamentos y Análisis Descriptivo",
        ],
        "tablas de frecuencia": [
            "Tablas de frecuencia",
            "Fundamentos y Análisis Descriptivo",
        ],
        "histogramas y polígonos de frecuencia": [
            "Histogramas y polígonos de frecuencia",
            "Fundamentos y Análisis Descriptivo",
        ],
        "medidas de tendencia central": [
            "Medidas de tendencia central",
            "Medidas Estadísticas",
        ],
        "media aritmética y ponderada": [
            "Medidas Estadísticas",
            "Medidas de tendencia central",
        ],
        "mediana y moda": [
            "Medidas Estadísticas",
            "Medidas de tendencia central",
        ],
        "medidas de dispersión": ["Medidas Estadísticas"],
        "varianza y desviación estándar": ["Medidas Estadísticas"],
        "probabilidad básica": ["Fundamentos de Probabilidad"],
        "distribución normal": ["Distribuciones de Probabilidad"],
        "distribuciones de probabilidad": ["Distribuciones de Probabilidad"],
        "muestreo y poblaciones": ["Inferencia Estadística"],
        "intervalos de confianza": ["Inferencia Estadística"],
        "pruebas de hipótesis": ["Inferencia Estadística"],
        "error tipo i y tipo ii": ["Inferencia Estadística"],
        "regresión lineal simple": ["Modelado y Análisis de Relaciones"],
        "correlación y coeficiente de pearson": [
            "Modelado y Análisis de Relaciones",
        ],
        "series temporales": ["Modelado y Análisis de Relaciones"],
        "análisis de varianza (anova)": [
            "Inferencia Estadística",
            "Modelado y Análisis de Relaciones",
        ],
        "teorema del límite central": [
            "Inferencia Estadística",
            "Distribuciones de Probabilidad",
        ],
        "eventos independientes y dependientes": ["Fundamentos de Probabilidad"],
        "diagramas de caja y bigotes": [
            "Fundamentos y Análisis Descriptivo",
            "Medidas Estadísticas",
        ],
        "coeficiente de variación": ["Medidas Estadísticas"],
        "distribución binomial": ["Distribuciones de Probabilidad"],
    }

    @classmethod
    def _expandir_alias(cls, tema: str) -> List[str]:
        """Devuelve la lista de nombres canónicos a probar para un tema dado."""
        nombre = (tema or "").strip()
        if not nombre:
            return []
        candidatos = [nombre]
        key = nombre.casefold()
        if key in cls._ALIAS_TEMAS:
            for alias in cls._ALIAS_TEMAS[key]:
                if alias not in candidatos:
                    candidatos.append(alias)
        return candidatos

    def _salvar_cache(self) -> None:
        with _cache_lock:
            try:
                os.makedirs(os.path.dirname(self.RUTA_CACHE), exist_ok=True)
                with open(self.RUTA_CACHE, "w", encoding="utf-8") as f:
                    json.dump(self._cache, f, ensure_ascii=False, indent=2)
            except Exception as e:
                print(f"[BancoPreguntas] Error salvando cache: {e}")

    def obtener_preguntas(
        self, tema: str, nivel: str, cantidad: int = 10, excluir_ids: Optional[Set[str]] = None
    ) -> Optional[List[Dict[str, Any]]]:
        excluir = set(excluir_ids or [])

        # Expandir alias: si el tema ingresado tiene un mapeo a nombres
        # canónicos del banco, probar cada uno.
        temas_a_intentar = self._expandir_alias(tema) or [tema]

        # Fallback de nivel: si no hay preguntas para el nivel exacto,
        # buscar en el nivel más cercano disponible
        _orden_niveles = ["bachillerato", "universidad", "postgrado"]
        niveles_a_intentar = [nivel]
        if nivel in _orden_niveles:
            idx = _orden_niveles.index(nivel)
            if idx > 0:
                niveles_a_intentar.append(_orden_niveles[idx - 1])
            if idx < len(_orden_niveles) - 1:
                niveles_a_intentar.append(_orden_niveles[idx + 1])

        for tema_intento in temas_a_intentar:
            for nivel_intento in niveles_a_intentar:
                banco_tema = self._banco.get("temas", {}).get(tema_intento, {}).get(nivel_intento, [])
                cache_tema = self._cache.get("temas", {}).get(tema_intento, {}).get(nivel_intento, [])
                todas = banco_tema + cache_tema
                no_fallback = [p for p in todas if not p.get("es_fallback") and p.get("id_estable") not in excluir]
                fallback_ps = [p for p in todas if p.get("es_fallback") and p.get("id_estable") not in excluir]

                if len(no_fallback) >= cantidad:
                    return random_module.sample(no_fallback, cantidad)
                if len(no_fallback) + len(fallback_ps) >= cantidad:
                    pool = no_fallback + fallback_ps
                    return random_module.sample(pool, cantidad)

        return None

    def total_disponibles(self, tema: str, nivel: str) -> int:
        return len(self._banco.get("temas", {}).get(tema, {}).get(nivel, []))

    def total_en_cache(self, tema: str, nivel: str) -> int:
        return len(self._cache.get("temas", {}).get(tema, {}).get(nivel, []))

    def todos_ids(self, tema: str, nivel: str) -> Set[str]:
        banco = self._banco.get("temas", {}).get(tema, {}).get(nivel, [])
        cache = self._cache.get("temas", {}).get(tema, {}).get(nivel, [])
        return {p.get("id_estable") for p in (banco + cache) if p.get("id_estable")}

    def agregar_a_cache(self, tema: str, nivel: str, preguntas: List[Dict[str, Any]]) -> None:
        for p in preguntas:
            if "id_estable" not in p:
                p["id_estable"] = hashlib.md5(
                    str(p.get("pregunta", "")).encode()
                ).hexdigest()[:12]

        self._cache.setdefault("temas", {}).setdefault(tema, {}).setdefault(nivel, [])
        existentes = self._cache["temas"][tema][nivel]
        ids_existentes = {p.get("id_estable") for p in existentes if p.get("id_estable")}

        nuevas = [p for p in preguntas if p.get("id_estable") not in ids_existentes]
        if not nuevas:
            return

        existentes.extend(nuevas)

        if len(existentes) > self.MAX_POR_TEMA:
            self._cache["temas"][tema][nivel] = existentes[-self.MAX_POR_TEMA:]

        self._salvar_cache()

    def hay_banco_para_tema(self, tema: str, nivel: str) -> bool:
        return tema in self._banco.get("temas", {}) and nivel in self._banco["temas"].get(tema, {})

    def hay_cache_para_tema(self, tema: str, nivel: str) -> bool:
        return tema in self._cache.get("temas", {}) and nivel in self._cache["temas"].get(tema, {})


class GeminiService:
    def __init__(self):
        self.api_key = os.getenv('GEMINI_API_KEY')
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY no está configurada en las variables de entorno")

        self.client = genai.Client(api_key=self.api_key)
        self.model_name = os.getenv('GEMINI_MODEL', 'gemini-flash-lite-latest')

    def generar_preguntas(
        self,
        tema_nombre: str,
        nivel_academico: str = "universidad",
        cantidad: int = 10,
        descripcion: Optional[str] = None,
        conceptos_clave: Optional[List[str]] = None,
        intereses: Optional[str] = None,
        excluir_ids: Optional[Set[str]] = None,
        solo_banco: bool = False,
    ) -> List[Dict[str, Any]]:
        """Intenta banco y cache primero, luego genera en vivo si no hay suficientes."""

        if not solo_banco:
            banco = BancoPreguntas()
            preguntas = banco.obtener_preguntas(
                tema_nombre, nivel_academico, cantidad, excluir_ids
            )
            if preguntas is not None:
                return self._asegurar_id_estable(preguntas)

            print(f"[generar_preguntas] Banco+cache insuficiente para '{tema_nombre}' — generando en vivo")

        preguntas = self._generar_en_vivo(
            tema_nombre, nivel_academico, cantidad, descripcion, conceptos_clave, intereses
        )

        if not solo_banco:
            validas = [p for p in preguntas if not p.get("es_fallback")]
            if validas:
                BancoPreguntas().agregar_a_cache(tema_nombre, nivel_academico, validas)

        return self._asegurar_id_estable(preguntas)

    def _asegurar_id_estable(self, preguntas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        for p in preguntas:
            if "id_estable" not in p:
                texto = str(p.get("pregunta", ""))
                p["id_estable"] = hashlib.md5(texto.encode()).hexdigest()[:12]
        return preguntas

    def _generar_en_vivo(
        self,
        tema_nombre: str,
        nivel_academico: str = "universidad",
        cantidad: int = 10,
        descripcion: Optional[str] = None,
        conceptos_clave: Optional[List[str]] = None,
        intereses: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        nivel_info = self._obtener_info_nivel(nivel_academico)
        terminos_especificos = self._obtener_terminos_especificos(tema_nombre, conceptos_clave)

        system_prompt = (
            "Eres un experto en estadística que genera preguntas educativas de alta calidad. "
            "Crea preguntas específicas, rigurosas y pedagógicamente sólidas sobre el tema indicado. "
            "Las preguntas deben evaluar comprensión real, no solo memorización de definiciones. "
            "Incluye preguntas de aplicación, análisis e interpretación de resultados. "
            "Los distractores en opción múltiple deben representar errores conceptuales comunes reales. "
            "Responde ÚNICAMENTE con un array JSON de objetos con los campos exactos: "
            "id (int), tipo (str: opcion_multiple|verdadero_falso|respuesta_abierta), "
            "pregunta (str), opciones (dict|null), respuesta_correcta (str), explicacion (str)."
        )

        conceptos_str = ", ".join(conceptos_clave) if conceptos_clave else tema_nombre
        intereses_str = f"El estudiante tiene intereses en: {intereses}." if intereses else ""

        user_prompt = f"""Tema: {tema_nombre}
Nivel académico: {nivel_academico.upper()} — {nivel_info['complejidad']}
Audiencia: {nivel_info['terminologia']}
Descripción del tema: {descripcion or 'Tema de estadística'}
Conceptos clave: {conceptos_str}
{intereses_str}

Genera {cantidad} preguntas variadas. Distribución sugerida:
- ~50% opción múltiple (4 opciones A-D con distractores verosímiles)
- ~25% verdadero/falso (con afirmaciones no triviales)
- ~25% respuesta abierta (que requieran cálculo o interpretación)

REGLAS CRÍTICAS:
- Preguntas de opción múltiple: los distractores deben ser errores que estudiantes reales cometen
  (ej: confundir varianza con desviación estándar, aplicar fórmulas incorrectamente, etc.)
- Preguntas de V/F: deben evaluar matices conceptuales, no definiciones obvias
- Preguntas abiertas: pide interpretaciones, comparaciones o cálculos con datos concretos
- Explicaciones: 2-3 oraciones que enseñen el concepto, no solo digan 'la respuesta es X'
- Cada pregunta debe mencionar explícitamente al menos uno de los conceptos clave
- opciones debe ser null para respuesta_abierta
- Para opcion_multiple, opciones = {{"A": "...", "B": "...", "C": "...", "D": "..."}}
- Para verdadero_falso, opciones = {{"A": "Verdadero", "B": "Falso"}}
"""

        for intento in range(3):
            try:
                config = genai_types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.75 if intento == 0 else 0.9,
                    max_output_tokens=8192,
                    response_mime_type="application/json",
                )

                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=user_prompt,
                    config=config,
                )

                content = response.text.strip()
                print(f"[_generar_en_vivo] Intento {intento + 1}: respuesta recibida ({len(content)} chars)")

                preguntas = self._parsear_json_preguntas(content)
                print(f"[_generar_en_vivo] Intento {intento + 1}: {len(preguntas)} preguntas extraídas")

                preguntas_unicas = self._deduplicar(preguntas)

                validas, invalidas = self._filtrar_validas(
                    preguntas_unicas, terminos_especificos, tema_nombre
                )

                print(f"[_generar_en_vivo] Intento {intento + 1}: {len(validas)}/{len(preguntas_unicas)} válidas")
                for p, razon in invalidas[:3]:
                    print(f"  ❌ Rechazada: '{p.get('pregunta', '')[:80]}' — {razon}")

                if len(validas) >= cantidad:
                    validas = validas[:cantidad]
                    for i, p in enumerate(validas, start=1):
                        p["id"] = i
                    return validas

                if intento == 0 and invalidas:
                    ejemplos_rechazados = ", ".join(
                        f"'{p.get('pregunta', '')[:50]}'" for p, _ in invalidas[:2]
                    )
                    user_prompt += (
                        f"\n\nIMPORTANTE: Las preguntas anteriores eran demasiado genéricas. "
                        f"Cada pregunta DEBE incluir explícitamente al menos uno de los conceptos clave del tema: "
                        f"{conceptos_str}. Ejemplos rechazados: {ejemplos_rechazados}."
                    )

            except Exception as e:
                print(f"[_generar_en_vivo] Intento {intento + 1} excepción: {type(e).__name__}: {e}")

        if conceptos_clave and len(conceptos_clave) > 0:
            print(f"[_generar_en_vivo] Usando fallback inteligente con {len(conceptos_clave)} conceptos clave")
            return self._preguntas_fallback(tema_nombre, cantidad, conceptos_clave, descripcion)

        return self._preguntas_fallback_generico(tema_nombre, cantidad, descripcion)

    def _obtener_terminos_especificos(
        self, tema_nombre: str, conceptos_clave: Optional[List[str]]
    ) -> Set[str]:
        terminos: Set[str] = set()
        if conceptos_clave:
            terminos.update(c.lower().strip() for c in conceptos_clave if c)
        palabras = re.findall(r"[a-záéíóúñü]{4,}", tema_nombre.lower())
        terminos.update(palabras)
        return terminos

    def _filtrar_validas(
        self,
        preguntas: List[Dict[str, Any]],
        terminos_especificos: Set[str],
        tema_nombre: str,
    ) -> Tuple[List[Dict[str, Any]], List[Tuple[Dict[str, Any], str]]]:
        validas: List[Dict[str, Any]] = []
        invalidas: List[Tuple[Dict[str, Any], str]] = []
        for p in preguntas:
            ok, razon = self._es_pregunta_valida(p, terminos_especificos, tema_nombre)
            if ok:
                validas.append(p)
            else:
                invalidas.append((p, razon))
        return validas, invalidas

    def _es_pregunta_valida(
        self,
        pregunta: Dict[str, Any],
        terminos_especificos: Set[str],
        tema_nombre: str,
    ) -> Tuple[bool, str]:
        pregunta_texto = str(pregunta.get("pregunta", "")).lower().strip()
        if not pregunta_texto:
            return False, "pregunta vacía"
        if len(pregunta_texto) < 20:
            return False, f"pregunta demasiado corta ({len(pregunta_texto)} chars)"
        if pregunta.get("tipo") not in ("opcion_multiple", "verdadero_falso", "respuesta_abierta"):
            return False, f"tipo inválido '{pregunta.get('tipo')}'"

        plantillas_rechazadas = [
            f"qué es la {tema_nombre.lower()}",
            f"qué es {tema_nombre.lower()}",
            "explica brevemente",
            "explica en tus palabras",
            "qué entiendes por",
        ]
        for plantilla in plantillas_rechazadas:
            if plantilla in pregunta_texto:
                return False, f"plantilla genérica '{plantilla}'"

        if terminos_especificos and any(t in pregunta_texto for t in terminos_especificos):
            return True, "ok"
        if any(t in pregunta_texto for t in _TERMINOS_ESTADISTICOS_GENERALES):
            return True, "ok (término estadístico)"
        return False, "no menciona ningún término del tema ni estadístico"

    def _parsear_json_preguntas(self, content: str) -> List[Dict[str, Any]]:
        cleaned = content.strip()
        if cleaned.startswith("```"):
            primera_salto = cleaned.find("\n")
            if primera_salto != -1:
                cleaned = cleaned[primera_salto + 1:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

        try:
            data = json.loads(cleaned)
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                for key in ("preguntas", "questions", "items", "data"):
                    if key in data and isinstance(data[key], list):
                        return data[key]
        except json.JSONDecodeError:
            pass

        match = re.search(r"\[.*\]", content, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
                if isinstance(data, list):
                    return data
            except json.JSONDecodeError:
                pass

        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
                if isinstance(data, dict):
                    for key in ("preguntas", "questions", "items", "data"):
                        if key in data and isinstance(data[key], list):
                            return data[key]
            except json.JSONDecodeError:
                pass

        raise ValueError(f"No se pudo parsear JSON de la respuesta: {content[:200]}...")

    def _deduplicar(self, preguntas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        unicas: List[Dict[str, Any]] = []
        vistos: Set[str] = set()
        for p in preguntas:
            enunciado = str(p.get("pregunta", "")).strip().casefold()
            if enunciado and enunciado not in vistos:
                vistos.add(enunciado)
                unicas.append(p)
        return unicas

    def evaluar_respuesta(self, pregunta: Dict[str, Any], respuesta_usuario: str) -> Dict[str, Any]:
        if pregunta["tipo"] in ("opcion_multiple", "verdadero_falso"):
            es_correcta = respuesta_usuario.strip().upper() == pregunta["respuesta_correcta"].strip().upper()
            return {
                "correcta": es_correcta,
                "puntaje": 1 if es_correcta else 0,
                "explicacion": pregunta["explicacion"]
            }

        elif pregunta["tipo"] == "respuesta_abierta":
            prompt = f"""
            Evalúa la siguiente respuesta a una pregunta educativa:

            PREGUNTA: {pregunta['pregunta']}
            RESPUESTA CORRECTA ESPERADA: {pregunta['respuesta_correcta']}
            RESPUESTA DEL USUARIO: {respuesta_usuario}

            Evalúa considerando: precisión conceptual, completitud y terminología.

            Responde ÚNICAMENTE en formato JSON:
            {{"correcta": true/false, "puntaje": 0.0-1.0, "explicacion": "..."}}
            """

            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                )
                content = response.text.strip()
                if content.startswith('```json'):
                    content = content[7:]
                if content.endswith('```'):
                    content = content[:-3]
                return json.loads(content)
            except Exception as e:
                print(f"Error evaluando respuesta: {e}")
                return {"correcta": False, "puntaje": 0, "explicacion": "Error en la evaluación automática"}

    def _obtener_info_nivel(self, nivel_academico: str) -> Dict[str, str]:
        niveles = {
            "bachillerato": {
                "complejidad": "Básica a intermedia",
                "enfoque": "conceptos fundamentales y aplicaciones básicas",
                "terminologia": "estudiantes de bachillerato (16-18 años)",
                "caracteristicas": "claras, directas y con ejemplos prácticos"
            },
            "universidad": {
                "complejidad": "Intermedia a avanzada",
                "enfoque": "comprensión profunda y análisis crítico",
                "terminologia": "estudiantes universitarios",
                "caracteristicas": "analíticas, con múltiples aspectos y casos de estudio"
            },
            "postgrado": {
                "complejidad": "Avanzada a experta",
                "enfoque": "análisis crítico, investigación y aplicación profesional",
                "terminologia": "estudiantes de postgrado y profesionales",
                "caracteristicas": "complejas, con múltiples variables y enfoques interdisciplinarios"
            }
        }
        return niveles.get(nivel_academico.lower(), niveles["universidad"])

    def _preguntas_fallback(
        self,
        tema_nombre: str,
        cantidad: int,
        conceptos_clave: List[str],
        descripcion: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        print(f"[fallback] Generando {cantidad} preguntas con conceptos clave del tema")
        conceptos = list(conceptos_clave) if conceptos_clave else []
        if not conceptos:
            return self._preguntas_fallback_generico(tema_nombre, cantidad, descripcion)

        variantes = [
            "afirmaciones",
            "definicion",
            "aplicacion",
            "importancia",
        ]
        tipos = ["opcion_multiple", "verdadero_falso", "respuesta_abierta"]
        preguntas: List[Dict[str, Any]] = []
        usados = set()
        idx = 1

        for c_idx in range(999):
            if len(preguntas) >= cantidad:
                break
            concepto = conceptos[c_idx % len(conceptos)]
            tipo = tipos[(c_idx // len(conceptos)) % len(tipos)]
            variante = variantes[(c_idx // (len(conceptos) * len(tipos))) % len(variantes)]

            pregunta = self._generar_pregunta_plantilla(
                idx=idx, tipo=tipo, tema_nombre=tema_nombre,
                concepto=concepto, variante=variante,
            )
            pregunta_texto = str(pregunta.get("pregunta", ""))
            pregunta_hash = hashlib.md5(pregunta_texto.encode()).hexdigest()[:12]

            if pregunta_hash not in usados:
                usados.add(pregunta_hash)
                pregunta["id_estable"] = pregunta_hash
                pregunta["id"] = idx
                idx += 1
                preguntas.append(pregunta)

        return preguntas

    def _preguntas_fallback_generico(
        self, tema_nombre: str, cantidad: int, descripcion: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        return [
            {
                "id": 1,
                "tipo": "respuesta_abierta",
                "pregunta": (
                    f"No pudimos generar preguntas automáticas sobre '{tema_nombre}' en este momento. "
                    f"¿Podrías explicar con tus palabras los conceptos principales de este tema?"
                ),
                "opciones": None,
                "respuesta_correcta": "Respuesta libre del estudiante",
                "explicacion": f"El tema '{tema_nombre}' se centra en los conceptos fundamentales. Reintenta en unos segundos.",
                "es_fallback": True,
            }
        ]

    def _generar_pregunta_plantilla(
        self, idx: int, tipo: str, tema_nombre: str, concepto: str,
        variante: str = "afirmaciones",
    ) -> Dict[str, Any]:
        plantilla_om = {
            "afirmaciones": {
                "pregunta": f"En el contexto de '{tema_nombre}', ¿cuál de las siguientes "
                            f"afirmaciones sobre '{concepto}' es la más precisa?",
                "opciones": {
                    "A": f"'{concepto}' es un concepto central de {tema_nombre.lower()}",
                    "B": f"'{concepto}' solo se aplica a datos cualitativos",
                    "C": f"'{concepto}' no tiene relación con {tema_nombre.lower()}",
                    "D": f"'{concepto}' es exactamente lo mismo que la media aritmética",
                },
                "razon": f"'{concepto}' es efectivamente un concepto clave de {tema_nombre.lower()}",
            },
            "definicion": {
                "pregunta": f"¿Cuál de las siguientes definiciones describe mejor "
                            f"el concepto '{concepto}' dentro de '{tema_nombre}'?",
                "opciones": {
                    "A": f"'{concepto}' se refiere a un aspecto fundamental de {tema_nombre.lower()}",
                    "B": f"'{concepto}' es un sinónimo exacto de la media aritmética",
                    "C": f"'{concepto}' no se utiliza en estadística",
                    "D": f"'{concepto}' es solo aplicable a variables cualitativas",
                },
                "razon": f"'{concepto}' es efectivamente un aspecto central de {tema_nombre.lower()}",
            },
            "aplicacion": {
                "pregunta": f"En la práctica de '{tema_nombre}', ¿para qué se utiliza "
                            f"principalmente '{concepto}'?",
                "opciones": {
                    "A": f"Para comprender mejor los fundamentos de {tema_nombre.lower()}",
                    "B": f"Solo para datos numéricos sin orden específico",
                    "C": f"No tiene aplicaciones prácticas en {tema_nombre.lower()}",
                    "D": f"Es una técnica obsoleta que ya no se usa",
                },
                "razon": f"'{concepto}' es fundamental en la práctica de {tema_nombre.lower()}",
            },
            "importancia": {
                "pregunta": f"¿Por qué es importante entender '{concepto}' "
                            f"al estudiar '{tema_nombre}'?",
                "opciones": {
                    "A": f"Porque '{concepto}' es una base conceptual clave en {tema_nombre.lower()}",
                    "B": f"Porque '{concepto}' es el único concepto relevante de {tema_nombre.lower()}",
                    "C": f"Porque '{concepto}' reemplaza a todos los demás conceptos del tema",
                    "D": f"En realidad, '{concepto}' no es importante en {tema_nombre.lower()}",
                },
                "razon": f"'{concepto}' es efectivamente una base conceptual importante",
            },
        }

        plantilla_vf = {
            "afirmaciones": {
                "pregunta": f"Verdadero o falso: '{concepto}' es un concepto relevante "
                            f"dentro de '{tema_nombre}'.",
                "razon": f"Verdadero. '{concepto}' es fundamental en {tema_nombre.lower()}.",
            },
            "definicion": {
                "pregunta": f"Verdadero o falso: '{concepto}' es un sinónimo "
                            f"de {tema_nombre.lower()}.",
                "razon": f"Falso. '{concepto}' es un concepto específico dentro de {tema_nombre.lower()}, no un sinónimo.",
            },
            "aplicacion": {
                "pregunta": f"Verdadero o falso: '{concepto}' se aplica exclusivamente "
                            f"en estudios de laboratorio.",
                "razon": f"Falso. '{concepto}' tiene aplicaciones en diversos contextos de {tema_nombre.lower()}.",
            },
            "importancia": {
                "pregunta": f"Verdadero o falso: comprender '{concepto}' es prescindible "
                            f"para dominar '{tema_nombre}'.",
                "razon": f"Falso. '{concepto}' es esencial para el estudio de {tema_nombre.lower()}.",
            },
        }

        plantilla_abierta = {
            "afirmaciones": {
                "pregunta": f"Explica con tus palabras qué es '{concepto}' y por qué es "
                            f"importante dentro de '{tema_nombre}'.",
                "respuesta": f"'{concepto}' es un concepto fundamental de {tema_nombre.lower()}",
                "razon": f"'{concepto}' es central en {tema_nombre.lower()}.",
            },
            "definicion": {
                "pregunta": f"Define '{concepto}' en el contexto de '{tema_nombre}' "
                            f"y da un ejemplo concreto.",
                "respuesta": f"Una definición que describa '{concepto}' dentro de {tema_nombre.lower()}",
                "razon": f"'{concepto}' es un concepto clave en {tema_nombre.lower()}.",
            },
            "aplicacion": {
                "pregunta": f"Describe una situación práctica donde se aplique "
                            f"'{concepto}' en '{tema_nombre}'.",
                "respuesta": f"'{concepto}' se aplica en {tema_nombre.lower()}",
                "razon": f"'{concepto}' tiene múltiples aplicaciones en {tema_nombre.lower()}.",
            },
            "importancia": {
                "pregunta": f"¿Por qué crees que '{concepto}' es relevante "
                            f"dentro de '{tema_nombre}'? Justifica tu respuesta.",
                "respuesta": f"'{concepto}' es relevante en {tema_nombre.lower()} porque",
                "razon": f"'{concepto}' tiene importancia conceptual en {tema_nombre.lower()}.",
            },
        }

        if tipo == "opcion_multiple":
            data = plantilla_om.get(variante, plantilla_om["afirmaciones"])
            return {
                "id": idx, "tipo": "opcion_multiple",
                "pregunta": data["pregunta"], "opciones": data["opciones"],
                "respuesta_correcta": "A",
                "explicacion": data["razon"],
                "es_fallback": True,
            }
        elif tipo == "verdadero_falso":
            es_afirmacion = variante == "afirmaciones"
            respuesta = "A" if es_afirmacion else "B"
            data = plantilla_vf.get(variante, plantilla_vf["afirmaciones"])
            return {
                "id": idx, "tipo": "verdadero_falso",
                "pregunta": data["pregunta"],
                "opciones": {"A": "Verdadero", "B": "Falso"},
                "respuesta_correcta": respuesta,
                "explicacion": data["razon"],
                "es_fallback": True,
            }
        else:
            data = plantilla_abierta.get(variante, plantilla_abierta["afirmaciones"])
            return {
                "id": idx, "tipo": "respuesta_abierta",
                "pregunta": data["pregunta"],
                "opciones": None,
                "respuesta_correcta": data["respuesta"],
                "explicacion": data["razon"],
                "es_fallback": True,
            }
