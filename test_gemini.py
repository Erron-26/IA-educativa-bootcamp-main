"""
Script de prueba para verificar la configuración de Gemini
Ejecutar: python test_gemini.py
"""

import os
from gemini_service import GeminiService

def test_gemini():
    print("🧪 Probando configuración de Gemini...")
    
    # Verificar variable de entorno
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("❌ Error: GEMINI_API_KEY no está configurada")
        print("📝 Configura la variable de entorno:")
        print("   Windows: set GEMINI_API_KEY=tu_api_key")
        print("   Linux/Mac: export GEMINI_API_KEY=tu_api_key")
        return False
    
    print(f"✅ API Key encontrada: {api_key[:10]}...")
    
    try:
        # Crear servicio
        gemini_service = GeminiService()
        print("✅ Servicio Gemini inicializado correctamente")
        
        # Probar generación de preguntas
        print("🔄 Generando preguntas de prueba...")
        preguntas = gemini_service.generar_preguntas(
            tema="Conceptos básicos de estadística",
            nivel_academico="bachillerato",
            cantidad=2
        )
        
        print(f"✅ Se generaron {len(preguntas)} preguntas")
        
        # Mostrar primera pregunta
        if preguntas:
            primera = preguntas[0]
            print(f"\n📋 Pregunta de ejemplo:")
            print(f"   Tipo: {primera['tipo']}")
            print(f"   Pregunta: {primera['pregunta']}")
            if primera['tipo'] in ['opcion_multiple', 'verdadero_falso']:
                print(f"   Opciones: {primera['opciones']}")
            print(f"   Respuesta: {primera['respuesta_correcta']}")
        
        print("\n🎉 ¡Configuración exitosa! Gemini está funcionando correctamente.")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    test_gemini()
