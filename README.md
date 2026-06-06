# IA Educativa Bootcamp

Plataforma educativa con IA para el aprendizaje de estadística. Genera ejercicios prácticos personalizados usando Google Gemini AI, con un banco de preguntas curado para minimizar el uso de la API.

## Características

- **Autenticación local** con SQLite + werkzeug
- **Aprendizaje visual** con videos de YouTube contextualizados
- **Ejercicios prácticos** con preguntas de opción múltiple, verdadero/falso y reflexión
- **Evaluación automática** de preguntas cerradas; las abiertas se comparan con respuestas sugeridas
- **Banco de preguntas curado** (~120 preguntas para nivel universidad) que evita llamadas a la API
- **Cache inteligente** que acumula preguntas generadas en vivo para reutilizarlas
- **Nivel educativo adaptable** según la edad del estudiante (secundaria, bachillerato, universidad, posgrado)
- **Seguimiento de progreso** por estudiante con historial de evaluaciones

## Configuración

### 1. Clonar y configurar credenciales

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

### 3. Generar banco de preguntas (opcional, pero recomendado)

El banco precargado tiene 120 preguntas para nivel universidad. Si quieres generarlo desde cero o para otros niveles:

```bash
# Genera 20 preguntas por tema para 'universidad' (~2 min)
python generar_banco.py

# Genera para 'bachillerato' (banco vacío para ese nivel)
python generar_banco.py --nivel bachillerato

# Demo rápida para presentación: 5 preguntas por tema
python generar_banco.py --cantidad 5

# Genera para los 3 niveles (~6 min)
python generar_banco.py --nivel todos

# Ver todas las opciones
python generar_banco.py --help
```

### 4. Ejecutar la aplicación

```bash
python app.py
```

## Estructura del proyecto

```
├── app.py                    # Aplicación principal Flask
├── db_config.py              # Autenticación y base de datos SQLite
├── gemini_service.py         # Servicio de IA con Google Gemini (generación + banco + cache)
├── busquedas.py              # Búsqueda de videos de YouTube
├── temas.py                  # Definición de 6 temas educativos con conceptos clave
├── ejercicios.py             # Generación de ejercicios de práctica
├── generar_banco.py          # Script CLI para curar/regenerar el banco de preguntas
├── banco_preguntas.json      # Banco de preguntas curado (120+ preguntas)
├── data/
│   ├── banco_cache.json      # Cache de preguntas generadas en vivo
│   └── educativa.db          # Base de datos SQLite (estudiantes, progreso)
├── templates/                 # Plantillas HTML
│   ├── index.html             # Landing con selección de tema y estilo
│   ├── register.html          # Registro con detección automática de nivel
│   ├── login.html             # Inicio de sesión
│   ├── perfil.html            # Perfil del estudiante con progreso
│   ├── visual.html            # Modo visual (videos)
│   └── practico.html          # Modo práctico (ejercicios interactivos)
├── static/
│   └── modern-style.css       # Estilo CSS editorial/científico
└── requirements.txt           # Dependencias Python
```

## Flujo de uso

1. **Registro**: El usuario se registra y según su edad se le asigna un nivel educativo automáticamente (12-15: secundaria, 16-17: bachillerato, 18+: selección manual entre universidad/posgrado/otro)
2. **Selección**: Elige un tema de estadística y un estilo (visual con videos o práctico con ejercicios)
3. **Ejercicios**: En modo práctico se generan 10 preguntas variadas (opción múltiple, verdadero/falso, reflexión)
4. **Evaluación**: Las preguntas cerradas se califican automáticamente; las abiertas muestran la respuesta sugerida para que el estudiante compare

## Gestión de la API de Gemini

El sistema está diseñado para minimizar el uso de la API gratuita de Gemini (1,500 requests/día en Flash-Lite):

1. **Banco curado**: Las preguntas en `banco_preguntas.json` se cargan sin llamar a la API
2. **Cache persistente**: Las preguntas generadas en vivo se guardan en `data/banco_cache.json` para reutilizarse
3. **Fallback local**: Si la API falla o se agota la cuota, usa plantillas locales para generar preguntas
4. **Máximo 1 llamada por tema**: Cada tema solo genera preguntas una vez; las siguientes sesiones usan el cache

Si durante la exposición prefieres no depender de la API, usa un usuario con **nivel universidad** (18+ años), ya que el banco tiene 120 preguntas precargadas para ese nivel.

## Tecnologías utilizadas

- **Python Flask** (backend)
- **SQLite** (base de datos local)
- **Google Gemini 2.5 Flash-Lite** (generación de preguntas)
- **YouTube Data API** (contenido educativo visual)
- **HTML/CSS/JavaScript** (frontend con diseño editorial/científico)

## Despliegue en Render.com

1. Conecta tu repositorio a Render.com
2. Configura las variables de entorno en el dashboard:
   - `GEMINI_API_KEY`
   - `FLASK_SECRET_KEY`
   - `DB_PATH=/data/educativa.db`
3. La configuración de despliegue está en `render.yaml`
