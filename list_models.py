"""
Script para listar modelos disponibles en Gemini
"""

import google.generativeai as genai
import os

def list_models():
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("ERROR: GEMINI_API_KEY no configurada")
        return
    
    genai.configure(api_key=api_key)
    
    print("Modelos disponibles:")
    for model in genai.list_models():
        print(f"- {model.name}")
        if hasattr(model, 'supported_generation_methods'):
            print(f"  Metodos soportados: {model.supported_generation_methods}")
        print()

if __name__ == "__main__":
    list_models()
