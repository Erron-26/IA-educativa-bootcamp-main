# IA Educativa Bootcamp

Plataforma educativa con IA para el aprendizaje de estadística.

## Características

- Autenticación local con SQLite + werkzeug
- Aprendizaje visual con videos de YouTube
- Ejercicios prácticos personalizados con IA (Gemini)
- Seguimiento de progreso del estudiante

## Configuración

### 1. Configurar credenciales

Copia `config_example.env` a `.env` y configura:

```bash
cp config_example.env .env
```

Edita `.env` con tu API key de Gemini:

```
GEMINI_API_KEY=tu_api_key_de_gemini_aqui
FLASK_SECRET_KEY=una_clave_secreta_segura
```

### 2. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 3. Ejecutar la aplicación

```bash
python app.py
```

## Estructura del proyecto

```
├── app.py                 # Aplicación principal Flask
├── db_config.py           # Autenticación y base de datos SQLite
├── gemini_service.py      # Servicio de IA con Google Gemini
├── busquedas.py           # Búsqueda de videos de YouTube
├── temas.py               # Definición de temas educativos
├── ejercicios.py          # Generación de ejercicios
├── templates/             # Plantillas HTML
├── static/                # Archivos CSS
└── requirements.txt       # Dependencias Python
```

## Tecnologías utilizadas

- Python Flask
- SQLite (base de datos local)
- Google Gemini AI
- YouTube (contenido educativo)
- HTML/CSS/JavaScript

## Despliegue en Render.com

1. Conecta tu repositorio a Render.com
2. Configura las variables de entorno en el dashboard:
   - `GEMINI_API_KEY`
   - `FLASK_SECRET_KEY`
   - `DB_PATH=/data/educativa.db`
3. La configuración de despliegue está en `render.yaml`
