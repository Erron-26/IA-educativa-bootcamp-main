# 🧠 IA Educativa Bootcamp

> *Plataforma educativa inteligente para el aprendizaje de Estadística*

![Python](https://img.shields.io/badge/Python-3.8+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-2.3-000000?style=for-the-badge&logo=flask&logoColor=white)
![Gemini](https://img.shields.io/badge/Google_Gemini-Flash--Lite-4285F4?style=for-the-badge&logo=google&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white)

---

## ✨ ¿Qué es?

Una aplicación web que combina **Inteligencia Artificial** con **pedagogía adaptativa** para enseñar estadística de forma personalizada. Usa **Google Gemini** para generar ejercicios prácticos en tiempo real, complementados con un banco de preguntas curado que minimiza el consumo de la API.

> **Diseñada para ser resiliente**: funciona incluso sin conexión a internet gracias a un banco de 120+ preguntas precargadas y un sistema de fallback multinivel.

---

## 🎯 Características principales

| Característica | Descripción |
|---|---|
| 🎓 **Nivel adaptativo** | Detecta automáticamente el nivel educativo según la edad del estudiante |
| 🎬 **Modo visual** | Videos de YouTube contextualizados + recursos curados de Khan Academy, Wikipedia y más |
| ✏️ **Modo práctico** | Ejercicios interactivos generados por IA: opción múltiple, verdadero/falso y reflexión |
| 📊 **Evaluación inteligente** | Las preguntas cerradas se califican automáticamente; las abiertas muestran una respuesta sugerida |
| 💾 **Caché persistente** | Las preguntas generadas se reutilizan en futuras sesiones sin llamar a la API |
| 🔒 **Seguridad** | Contraseñas hasheadas con `pbkdf2:sha256`, sesiones firmadas y validación server-side |
| 📈 **Seguimiento del progreso** | Historial de evaluaciones y progreso por tema almacenado en SQLite |

---

## 🏗️ Arquitectura del sistema

```text
FLUJO DE LA APLICACIÓN

Registro (edad) → Login (sesión) → Menú principal → Tema + estilo
                                              ├→ Modo visual → YouTube + recursos
                                              └→ Modo práctico → Gemini API
```

---

## 📂 Estructura del proyecto

```text
IA-educativa-bootcamp/
├── app.py                 # Rutas Flask, autenticación, APIs REST
├── db_config.py           # SQLite: usuarios, estudiantes, progreso
├── gemini_service.py      # Servicio Gemini + banco y caché
├── busquedas.py           # Búsqueda de YouTube + verificación oEmbed
├── temas.py               # 6 temas de estadística con subtemas
├── ejercicios.py          # Ejercicios estáticos (legacy)
├── generar_banco.py       # Script CLI para generar banco de preguntas
├── banco_preguntas.json   # Banco curado: ~120 preguntas
│
├── data/
│   ├── banco_cache.json   # Caché de preguntas generadas en vivo
│   └── educativa.db       # Base de datos SQLite (se crea automáticamente)
│
├── templates/
│   ├── index.html         # Landing: selección de tema y estilo
│   ├── register.html      # Registro con detección de nivel por edad
│   ├── login.html         # Inicio de sesión
│   ├── perfil.html        # Perfil del estudiante con progreso
│   ├── visual.html        # Modo visual: videos y recursos
│   └── practico.html      # Modo práctico: ejercicios interactivos
│
├── static/
│   └── modern-style.css   # Diseño editorial / científico
│
├── tests/
│   ├── test_api.py        # Tests de endpoints
│   ├── test_db.py         # Tests de base de datos
│   ├── test_modules.py    # Tests de módulos
│   ├── test_performance.py# Tests de rendimiento
│   ├── test_routes.py     # Tests de rutas
│   └── test_security.py   # Tests de seguridad
│
├── requirements.txt       # Dependencias Python
├── render.yaml            # Configuración Render.com
├── config_example.env     # Plantilla de variables de entorno
└── .gitignore
```

---

## 🚀 Inicialización paso a paso

### 1. Clonar el repositorio

```bash
git clone https://github.com/tu-usuario/IA-educativa-bootcamp.git
cd IA-educativa-bootcamp
```

### 2. Configurar variables de entorno

```bash
cp config_example.env .env
```

Edita el archivo `.env` con tus credenciales:

```env
# API Key de Google Gemini
GEMINI_API_KEY=tu_api_key_de_gemini_aqui

# Clave secreta para sesiones Flask
FLASK_SECRET_KEY=una_clave_secreta_segura

# Modelo de Gemini a usar (opcional)
GEMINI_MODEL=gemini-flash-lite-latest

# Puerto del servidor (opcional; valor por defecto: 5000)
PORT=5000
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 4. Generar el banco de preguntas (opcional)

El banco incluido tiene 120 preguntas para nivel universidad. Para generar más preguntas o cubrir otros niveles:

```bash
# Generar 20 preguntas por tema para universidad (~2 min)
python generar_banco.py

# Generar para bachillerato
python generar_banco.py --nivel bachillerato

# Demo rápida: 5 preguntas por tema
python generar_banco.py --cantidad 5

# Generar para todos los niveles (~6 min)
python generar_banco.py --nivel todos

# Ver opciones disponibles
python generar_banco.py --help
```

### 5. Ejecutar la aplicación

```bash
python app.py
```

La aplicación estará disponible en `http://localhost:5000`.

---

## 🔄 Flujo completo de uso

### Registro y autenticación

```text
Usuario ingresa:
- Email
- Contraseña (hasheada con pbkdf2:sha256)
- Nombre completo
- Edad

Clasificación por edad:
- 12–15 años → Secundaria
- 16–17 años → Bachillerato
- 18+ años   → Selección manual:
  - Universidad
  - Posgrado
  - Otro

Resultado:
Usuario creado en SQLite con nivel asignado
```

### Selección de aprendizaje

Una vez autenticado, el estudiante elige:

| Opción | Descripción | Resultado |
|---|---|---|
| 🎬 **Modo visual** | Videos de YouTube + recursos educativos | Página con subtemas navegables, videos verificados y enlaces a Khan Academy / Wikipedia |
| ✏️ **Modo práctico** | Ejercicios generados por IA | 10 preguntas variadas con evaluación automática |

### Generación de preguntas (cascada multinivel)

```text
Se solicitan 10 preguntas para el tema elegido

Nivel 1: Banco curado (banco_preguntas.json)
   └─ Si no alcanza, pasa a:

Nivel 2: Caché (data/banco_cache.json)
   └─ Si no alcanza, pasa a:

Nivel 3: Gemini (generación en vivo)
   └─ Si falla, pasa a:

Nivel 4: Plantillas locales (fallback)
```

### Evaluación de respuestas

| Tipo de pregunta | Evaluación | Resultado |
|---|---|---|
| **Opción múltiple** | Comparación directa (sin API) | ✅ Correcto / ❌ Incorrecto + explicación |
| **Verdadero/Falso** | Comparación directa (sin API) | ✅ Correcto / ❌ Incorrecto + explicación |
| **Respuesta abierta** | Sin evaluación automática | 📝 Respuesta del estudiante vs. respuesta sugerida del experto |

---

## 🔧 Gestión de la API de Gemini

El sistema está optimizado para minimizar el consumo de la API gratuita de Gemini.

### Estrategia de ahorro

1. **Banco curado**: las preguntas de `banco_preguntas.json` se cargan sin llamadas a la API.
2. **Caché persistente**: las preguntas generadas en vivo se guardan en `data/banco_cache.json`.
3. **Máximo 1 llamada por tema**: cada tema solo genera preguntas una vez por sesión.
4. **Fallback local**: si la API falla, usa plantillas predefinidas con conceptos clave.

### 💡 Tip para demostraciones

Si necesitas presentar la aplicación sin depender de internet, usa un usuario con nivel universidad. El banco tiene 120 preguntas precargadas que se cargan instantáneamente.

---

## 🛡️ Seguridad

| Medida | Implementación |
|---|---|
| **Hasheo de contraseñas** | `werkzeug.security.generate_password_hash` (`pbkdf2:sha256`) |
| **Sesiones firmadas** | Cookies HTTP firmadas con `FLASK_SECRET_KEY` |
| **Protección XSS** | Función `escHtml()` en JavaScript del cliente |
| **Validación server-side** | Edad y nivel educativo se validan en el backend |
| **Archivos sensibles** | `.env`, `*.db` y `*.json` excluidos del repositorio |

---

## 📊 Contenido educativo

### 6 temas de estadística

| # | Tema | Subtemas |
|---|---|---|
| 1 | Fundamentos y análisis descriptivo | 8 subtemas |
| 2 | Medidas estadísticas | 13 subtemas |
| 3 | Fundamentos de probabilidad | 12 subtemas |
| 4 | Distribuciones de probabilidad | 12 subtemas |
| 5 | Inferencia estadística | 10 subtemas |
| 6 | Modelado y análisis de relaciones | 10 subtemas |

### Recursos curados

- ~120 subtemas con 2–3 recursos cada uno
- Fuentes: Khan Academy, Wikipedia, ejemplos.co, universoformulas.com, questionpro.com
- Búsqueda complementaria: Wikipedia API para contenido adicional

---

## 🧪 Tests

```bash
# Ejecutar todos los tests
python -m pytest tests/

# Tests específicos
python -m pytest tests/test_api.py
python -m pytest tests/test_db.py
python -m pytest tests/test_security.py
python -m pytest tests/test_performance.py
```

---

## 🚀 Despliegue en Render.com

### Configuración automática

El archivo `render.yaml` configura automáticamente:

- Disco persistente de 1 GB en `/data` para SQLite
- Variables de entorno necesarias
- Comandos de build e inicio

### Pasos manuales

1. Conecta tu repositorio a [Render.com](https://render.com).
2. Configura las variables de entorno en el dashboard:
   - `GEMINI_API_KEY` → API key de Google Gemini
   - `FLASK_SECRET_KEY` → Se genera automáticamente
   - `DB_PATH=/data/educativa.db` → Ruta al disco persistente
3. Render detectará `render.yaml` y configurará el servicio automáticamente.

---

## 🛠️ Tecnologías utilizadas

| Capa | Tecnología | Propósito |
|---|---|---|
| **Backend** | Python Flask 2.3 | Servidor web, rutas, autenticación |
| **Base de datos** | SQLite | Almacenamiento local (usuarios, progreso) |
| **IA** | Google Gemini 2.5 Flash-Lite | Generación de preguntas personalizadas |
| **Frontend** | HTML / CSS / JavaScript | Interfaz editorial/científica |
| **Fuentes** | Playfair Display, Plus Jakarta Sans, Space Mono | Tipografías del diseño |
| **Despliegue** | Render.com | Hosting con disco persistente |
| **Servidor WSGI** | Waitress (Windows) / Flask dev (Linux) | Servidor de producción |

---

## 📝 Licencia

Este proyecto es educativo y de código abierto. Úsalo, modifícalo y compártelo.

---

<p align="center"><em>Desarrollado con ❤️ para el aprendizaje de Estadística</em></p>
