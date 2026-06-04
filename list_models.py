import os
from google import genai

def list_models():
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("ERROR: GEMINI_API_KEY no configurada")
        return

    client = genai.Client(api_key=api_key)

    print("Modelos disponibles:")
    for model in client.models.list():
        print(f"- {model.name}")
        if hasattr(model, 'supported_actions'):
            print(f"  Acciones soportadas: {model.supported_actions}")
        print()

if __name__ == "__main__":
    list_models()
