"""
Script de prueba simple para verificar la configuración de Gemini
"""

import os
from gemini_service import GeminiService

def test_gemini():
    print("Probando configuracion de Gemini...")
    
    # Verificar variable de entorno
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("ERROR: GEMINI_API_KEY no esta configurada")
        print("Configura la variable de entorno:")
        print("   Windows PowerShell: $env:GEMINI_API_KEY='tu_api_key'")
        print("   Windows CMD: set GEMINI_API_KEY=tu_api_key")
        return False
    
    print(f"OK: API Key encontrada: {api_key[:10]}...")
    
    try:
        # Crear servicio
        gemini_service = GeminiService()
        print("OK: Servicio Gemini inicializado correctamente")
        
        # Probar generación de preguntas
        print("Generando preguntas de prueba...")
        preguntas = gemini_service.generar_preguntas(
            tema="Conceptos basicos de estadistica",
            nivel_academico="bachillerato",
            cantidad=2
        )
        
        print(f"OK: Se generaron {len(preguntas)} preguntas")
        
        # Mostrar primera pregunta
        if preguntas:
            primera = preguntas[0]
            print(f"\nPregunta de ejemplo:")
            print(f"   Tipo: {primera['tipo']}")
            print(f"   Pregunta: {primera['pregunta']}")
            if primera['tipo'] in ['opcion_multiple', 'verdadero_falso']:
                print(f"   Opciones: {primera['opciones']}")
            print(f"   Respuesta: {primera['respuesta_correcta']}")
        
        print("\nEXITO: Configuracion exitosa! Gemini esta funcionando correctamente.")
        return True
        
    except Exception as e:
        print(f"ERROR: {e}")
        return False

if __name__ == "__main__":
    test_gemini()
