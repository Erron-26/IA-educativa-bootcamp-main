"""
Servicio para integración con Google Gemini AI
Genera preguntas dinámicas y evalúa respuestas
"""

import os
import json
import google.generativeai as genai
from typing import List, Dict, Any

class GeminiService:
    def __init__(self):
        """Inicializa el servicio de Gemini"""
        self.api_key = os.getenv('GEMINI_API_KEY')
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY no está configurada en las variables de entorno")
        
        genai.configure(api_key=self.api_key)
        # Usar el modelo más reciente disponible
        self.model = genai.GenerativeModel('gemini-2.5-flash')
    
    def generar_preguntas(self, tema: str, nivel_academico: str = "universidad", cantidad: int = 10) -> List[Dict[str, Any]]:
        """
        Genera preguntas dinámicas sobre un tema específico adaptadas al nivel académico
        
        Args:
            tema: El tema de estudio
            nivel_academico: Nivel académico del estudiante (bachillerato, universidad, postgrado)
            cantidad: Número de preguntas a generar
            
        Returns:
            Lista de diccionarios con preguntas, opciones, respuestas correctas y explicaciones
        """
        # Definir nivel de complejidad según nivel académico
        nivel_info = self._obtener_info_nivel(nivel_academico)
        
        prompt = f"""
        Genera {cantidad} preguntas educativas sobre el tema: "{tema}"
        
        NIVEL ACADÉMICO: {nivel_academico.upper()}
        COMPLEJIDAD: {nivel_info['complejidad']}
        ENFOQUE: {nivel_info['enfoque']}
        
        Los tipos de preguntas deben ser variados:
        - Opción múltiple (4 opciones A, B, C, D)
        - Verdadero/Falso
        - Respuesta abierta (para explicaciones conceptuales)
        
        CRITERIOS IMPORTANTES:
        - Adapta la complejidad al nivel {nivel_academico}
        - Usa terminología apropiada para {nivel_info['terminologia']}
        - Enfócate en {nivel_info['enfoque']}
        - Las preguntas deben ser {nivel_info['caracteristicas']}
        
        Responde ÚNICAMENTE en formato JSON válido con esta estructura:
        [
            {{
                "id": 1,
                "tipo": "opcion_multiple",
                "pregunta": "¿Cuál es la definición de...?",
                "opciones": {{
                    "A": "Opción A",
                    "B": "Opción B", 
                    "C": "Opción C",
                    "D": "Opción D"
                }},
                "respuesta_correcta": "A",
                "explicacion": "Explicación detallada de por qué esta es la respuesta correcta"
            }},
            {{
                "id": 2,
                "tipo": "verdadero_falso",
                "pregunta": "Afirmación sobre el tema...",
                "opciones": {{
                    "A": "Verdadero",
                    "B": "Falso"
                }},
                "respuesta_correcta": "A",
                "explicacion": "Explicación de por qué es verdadero/falso"
            }},
            {{
                "id": 3,
                "tipo": "respuesta_abierta",
                "pregunta": "Explica el concepto de...",
                "opciones": null,
                "respuesta_correcta": "Conceptos clave que debe incluir la respuesta",
                "explicacion": "Explicación detallada del concepto"
            }}
        ]
        
        IMPORTANTE:
        - Las preguntas deben ser apropiadas para nivel universitario
        - Incluye conceptos fundamentales del tema
        - Las explicaciones deben ser educativas y claras
        - No incluyas texto adicional fuera del JSON
        """
        
        try:
            print(f"Enviando prompt a Gemini...")
            response = self.model.generate_content(prompt)
            print(f"Respuesta recibida de Gemini")
            
            # Limpiar la respuesta para extraer solo el JSON
            content = response.text.strip()
            print(f"Contenido crudo: {content[:200]}...")
            
            # Buscar el JSON en la respuesta
            if content.startswith('```json'):
                content = content[7:]
            if content.endswith('```'):
                content = content[:-3]
            
            preguntas = json.loads(content)
            print(f"JSON parseado correctamente: {len(preguntas)} preguntas")

            # Deduplicar por enunciado de la pregunta (casefold y strip)
            preguntas_unicas = []
            vistos = set()
            for p in preguntas:
                enunciado = str(p.get("pregunta", "")).strip().casefold()
                if enunciado and enunciado not in vistos:
                    vistos.add(enunciado)
                    preguntas_unicas.append(p)

            # Completar con fallback si faltan preguntas
            if len(preguntas_unicas) < cantidad:
                faltantes = cantidad - len(preguntas_unicas)
                fallback = self._preguntas_fallback(tema, faltantes)
                for p in fallback:
                    enunciado = str(p.get("pregunta", "")).strip().casefold()
                    if enunciado and enunciado not in vistos:
                        vistos.add(enunciado)
                        preguntas_unicas.append(p)
                    if len(preguntas_unicas) >= cantidad:
                        break

            # Limitar a la cantidad solicitada y normalizar ids
            preguntas_unicas = preguntas_unicas[:cantidad]
            for i, p in enumerate(preguntas_unicas, start=1):
                p["id"] = i

            return preguntas_unicas
            
        except Exception as e:
            print(f"Error generando preguntas: {e}")
            print(f"Tipo de error: {type(e).__name__}")
            # Preguntas de fallback en caso de error
            return self._preguntas_fallback(tema, cantidad)
    
    def evaluar_respuesta(self, pregunta: Dict[str, Any], respuesta_usuario: str) -> Dict[str, Any]:
        """
        Evalúa la respuesta del usuario usando Gemini
        
        Args:
            pregunta: Diccionario con la pregunta original
            respuesta_usuario: Respuesta proporcionada por el usuario
            
        Returns:
            Diccionario con el resultado de la evaluación
        """
        if pregunta["tipo"] == "opcion_multiple" or pregunta["tipo"] == "verdadero_falso":
            # Para opciones múltiples y V/F, comparación directa
            es_correcta = respuesta_usuario.strip().upper() == pregunta["respuesta_correcta"].strip().upper()
            return {
                "correcta": es_correcta,
                "puntaje": 1 if es_correcta else 0,
                "explicacion": pregunta["explicacion"]
            }
        
        elif pregunta["tipo"] == "respuesta_abierta":
            # Para respuestas abiertas, usar Gemini para evaluar
            prompt = f"""
            Evalúa la siguiente respuesta a una pregunta educativa:
            
            PREGUNTA: {pregunta['pregunta']}
            RESPUESTA CORRECTA ESPERADA: {pregunta['respuesta_correcta']}
            RESPUESTA DEL USUARIO: {respuesta_usuario}
            
            Evalúa la respuesta del usuario considerando:
            1. Precisión conceptual
            2. Completitud de la respuesta
            3. Uso de terminología apropiada
            
            Responde ÚNICAMENTE en formato JSON:
            {{
                "correcta": true/false,
                "puntaje": 0.0-1.0,
                "explicacion": "Explicación detallada de la evaluación"
            }}
            """
            
            try:
                response = self.model.generate_content(prompt)
                content = response.text.strip()
                
                # Limpiar la respuesta
                if content.startswith('```json'):
                    content = content[7:]
                if content.endswith('```'):
                    content = content[:-3]
                
                evaluacion = json.loads(content)
                return evaluacion
                
            except Exception as e:
                print(f"Error evaluando respuesta: {e}")
                return {
                    "correcta": False,
                    "puntaje": 0,
                    "explicacion": "Error en la evaluación automática"
                }
    
    def _obtener_info_nivel(self, nivel_academico: str) -> Dict[str, str]:
        """Obtiene información específica según el nivel académico"""
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
    
    def _preguntas_fallback(self, tema: str, cantidad: int) -> List[Dict[str, Any]]:
        """Preguntas de fallback en caso de error con Gemini"""
        print("ADVERTENCIA: Usando preguntas de fallback - Gemini no disponible")
        
        # Preguntas estáticas más realistas
        preguntas_base = [
            {
                "id": 1,
                "tipo": "opcion_multiple",
                "pregunta": f"¿Qué es la {tema.lower()} en estadística?",
                "opciones": {
                    "A": "Una medida de tendencia central",
                    "B": "Una medida de dispersión",
                    "C": "Un tipo de gráfico",
                    "D": "Un método de muestreo"
                },
                "respuesta_correcta": "A",
                "explicacion": f"La {tema.lower()} es una medida de tendencia central que representa el valor que divide un conjunto de datos en dos partes iguales."
            },
            {
                "id": 2,
                "tipo": "verdadero_falso",
                "pregunta": f"La {tema.lower()} es menos sensible a valores extremos que la media.",
                "opciones": {
                    "A": "Verdadero",
                    "B": "Falso"
                },
                "respuesta_correcta": "A",
                "explicacion": "Verdadero. La mediana es más robusta ante valores atípicos porque solo considera la posición central de los datos."
            },
            {
                "id": 3,
                "tipo": "respuesta_abierta",
                "pregunta": f"Explica brevemente cuándo es más útil usar la {tema.lower()} en lugar de la media aritmética.",
                "opciones": None,
                "respuesta_correcta": "Cuando hay valores extremos o atípicos en los datos",
                "explicacion": "La mediana es más útil cuando los datos tienen valores extremos porque no se ve afectada por ellos, a diferencia de la media que puede distorsionarse."
            }
        ]
        
        # Repetir preguntas hasta alcanzar la cantidad deseada
        preguntas = []
        for i in range(cantidad):
            pregunta = preguntas_base[i % len(preguntas_base)].copy()
            pregunta["id"] = i + 1
            preguntas.append(pregunta)
        
        return preguntas
