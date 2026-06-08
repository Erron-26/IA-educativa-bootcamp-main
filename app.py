import os
import sys
import random
import time
import functools
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv
load_dotenv()

# ── Fix de encoding para la consola de Windows (CMD/PowerShell) ──────────────
# Sin esto, los caracteres en español (tildes, ñ) se ven como símbolos raros.
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
# ─────────────────────────────────────────────────────────────────────────────

# pyrefly: ignore [missing-import]
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from busquedas import buscar_videos_youtube
from temas import temas
from db_config import LocalAuth, StudentData
from gemini_service import GeminiService
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ["FLASK_SECRET_KEY"]

_gemini_service = None
_youtube_cache = {}
_recursos_cache = {}

_temas_lista = temas["Estadística"]  # list[dict]
_temas_por_nombre = {t["nombre"]: t for t in _temas_lista}

# ── Estructura académica de subtemas por categoría ────────────────────────────
TEMAS_ESTADISTICA = {
    "Fundamentos y Análisis Descriptivo": [
        "Conceptos básicos de estadística",
        "Tipos de variables",
        "Escalas de medición",
        "Población y muestra",
        "Recolección de datos",
        "Organización de datos",
        "Tablas de frecuencia",
        "Distribución de frecuencias",
    ],
    "Medidas Estadísticas": [
        "Media",
        "Mediana",
        "Moda",
        "Cuartiles",
        "Deciles",
        "Percentiles",
        "Rango",
        "Varianza",
        "Desviación estándar",
        "Coeficiente de variación",
        "Asimetría",
        "Curtosis",
        "Interpretación de resultados",
    ],
    "Fundamentos de Probabilidad": [
        "Experimentos aleatorios",
        "Espacio muestral",
        "Eventos y sucesos",
        "Principio multiplicativo",
        "Permutaciones",
        "Combinaciones",
        "Probabilidad clásica",
        "Probabilidad frecuencial",
        "Probabilidad subjetiva",
        "Probabilidad condicional",
        "Teorema de Bayes",
        "Eventos independientes y dependientes",
    ],
    "Distribuciones de Probabilidad": [
        "Bernoulli",
        "Binomial",
        "Poisson",
        "Hipergeométrica",
        "Uniforme",
        "Normal",
        "Exponencial",
        "t de Student",
        "Chi-cuadrado",
        "Cálculo de probabilidades",
        "Uso de tablas estadísticas",
        "Interpretación de distribuciones",
    ],
    "Inferencia Estadística": [
        "Muestreo",
        "Distribuciones muestrales",
        "Estimación puntual",
        "Intervalos de confianza",
        "Pruebas de hipótesis",
        "Errores tipo I y II",
        "Pruebas para medias",
        "Pruebas para proporciones",
        "Comparación de grupos",
        "Interpretación de resultados",
    ],
    "Modelado y Análisis de Relaciones": [
        "Covarianza",
        "Correlación Pearson",
        "Correlación Spearman",
        "Regresión lineal simple",
        "Regresión lineal múltiple",
        "Coeficiente de determinación R²",
        "Predicción de valores",
        "Análisis de residuos",
        "Interpretación de modelos",
        "Aplicaciones en negocios e investigación",
    ],
}


def obtener_info_tema(tema_nombre: str) -> dict | None:
    return _temas_por_nombre.get(tema_nombre)


def get_gemini_service() -> GeminiService:
    global _gemini_service
    if _gemini_service is None:
        _gemini_service = GeminiService()
    return _gemini_service


def get_youtube_videos(query: str, num: int, ttl: int = 600):
    """Cache de videos de YouTube con TTL (segundos)."""
    ahora = time.time()
    if query in _youtube_cache:
        resultados, ts = _youtube_cache[query]
        if ahora - ts < ttl:
            return resultados
    resultados = buscar_videos_youtube(query, num)
    _youtube_cache[query] = (resultados, ahora)
    return resultados


# Decorador para verificar autenticación
def login_required(f):
    @functools.wraps(f)          # ← preserva nombre y docstring de la función
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


# ---------------------- AUTENTICACIÓN ------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        if not email or not password:
            flash("Por favor completa todos los campos.", "error")
            return redirect(url_for("login"))

        result = LocalAuth.login_user(email, password)

        if result["success"]:
            user_id = result['user']['localId']
            session['user'] = user_id
            session['email'] = email

            student_data = StudentData.get_student_data(user_id)
            if student_data["success"]:
                session['student_data'] = student_data["data"]

            flash("¡Bienvenido de vuelta! Sesión iniciada exitosamente.", "success")
            return redirect(url_for("index"))
        else:
            flash(f"Error al iniciar sesión: {result['error']}", "error")

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    # Restaurar datos del formulario de un intento anterior (si hubo error)
    form_data = session.pop("register_form_data", {})

    if request.method == "POST":
        email            = request.form.get("email", "").strip()
        password         = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        nombre           = request.form.get("nombre", "").strip()
        edad_str         = request.form.get("edad", "").strip()
        nivel_educativo  = request.form.get("nivel_educativo", "").strip()
        intereses        = request.form.get("intereses", "estadistica").strip()

        # Guardar datos no-sensibles para repoblar si hay error
        form_data = {
            "email":           email,
            "nombre":          nombre,
            "edad":            edad_str,
            "nivel_educativo": nivel_educativo,
        }

        # ── Validar campos básicos ────────────────────────────────
        if not all([email, password, confirm_password, nombre, edad_str]):
            flash("Por favor completa todos los campos.", "error")
            session["register_form_data"] = form_data
            return redirect(url_for("register"))

        if password != confirm_password:
            flash("Las contraseñas no coinciden.", "error")
            session["register_form_data"] = form_data
            return redirect(url_for("register"))

        if len(password) < 6:
            flash("La contraseña debe tener al menos 6 caracteres.", "error")
            session["register_form_data"] = form_data
            return redirect(url_for("register"))

        # ── Validar edad y asignar nivel según criterios ──────────
        try:
            edad = int(edad_str)
        except ValueError:
            flash("La edad debe ser un número válido.", "error")
            session["register_form_data"] = form_data
            return redirect(url_for("register"))

        if edad < 12:
            flash("La edad mínima para registrarse es 12 años.", "error")
            session["register_form_data"] = form_data
            return redirect(url_for("register"))

        # Clasificación automática por edad (validación del lado del servidor)
        # Esto evita que alguien manipule el formulario desde el navegador.
        if 12 <= edad <= 15:
            nivel_educativo = "secundaria"        # fijo, se ignora lo enviado
        elif 16 <= edad <= 17:
            nivel_educativo = "bachillerato"      # fijo, se ignora lo enviado
        else:
            # 18+ → el usuario elige; validar que llegó un valor permitido
            opciones_validas = {"universidad", "posgrado", "otro"}
            if nivel_educativo not in opciones_validas:
                flash("Por favor selecciona tu nivel educativo.", "warning")
                session["register_form_data"] = form_data
                return redirect(url_for("register"))

        # ── Mapear nivel_educativo → nivel_academico (usado por Gemini) ──
        nivel_mapping = {
            "secundaria":   "bachillerato",   # preguntas de nivel básico
            "bachillerato": "bachillerato",
            "universidad":  "universidad",
            "posgrado":     "postgrado",
            "otro":         "universidad",
        }
        nivel_academico = nivel_mapping[nivel_educativo]

        # ── Crear usuario y guardar datos ─────────────────────────
        result = LocalAuth.register_user(email, password)

        if result["success"]:
            user_id = result["user"]["localId"]

            student_data = {
                "email":           email,
                "nombre":          nombre,
                "edad":            edad,
                "nivel_educativo": nivel_educativo,
                "nivel_academico": nivel_academico,
                "intereses":       intereses,
                "fecha_registro":  datetime.now().isoformat(),
                "progreso":        {},
                "activo":          True,
            }

            save_result = StudentData.save_student_data(user_id, student_data)

            if save_result["success"]:
                flash("¡Cuenta creada exitosamente! Ahora puedes iniciar sesión.", "success")
                return redirect(url_for("login"))
            else:
                flash(f"Error al guardar datos del estudiante: {save_result['error']}", "error")
        else:
            flash(f"Error al crear la cuenta: {result['error']}", "error")

    return render_template("register.html", form_data=form_data)


@app.route("/perfil")
@login_required
def perfil():
    user_id      = session.get('user')
    student_data = session.get('student_data')

    if not student_data:
        result = StudentData.get_student_data(user_id)
        if result["success"]:
            student_data = result["data"]
            session['student_data'] = student_data
        else:
            flash("Error al cargar datos del perfil.", "error")
            return redirect(url_for("index"))

    return render_template("perfil.html", student_data=student_data)


@app.route("/logout")
def logout():
    LocalAuth.logout_user()
    flash("Sesión cerrada exitosamente.", "success")
    return redirect(url_for("login"))


@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    user_id      = session.get("user")
    student_data = session.get("student_data")

    if not student_data:
        result = StudentData.get_student_data(user_id)
        if result["success"]:
            student_data = result["data"]
            session["student_data"] = student_data
        else:
            student_data = {"nombre": "Estudiante"}

    nombre_estudiante = student_data.get("nombre", "Estudiante")

    if request.method == "POST":
        tema  = request.form.get("tema")
        estilo = request.form.get("estilo")

        if not tema or not estilo:
            flash("⚠️ Por favor completa todos los campos.", "warning")
            return redirect(url_for("index"))

        if tema not in _temas_por_nombre:
            flash("El tema seleccionado no es válido. Selecciona uno de la lista.", "error")
            return redirect(url_for("index"))

        if estilo == "Visual":
            return redirect(url_for("visual", tema=tema))
        elif estilo == "Práctico":
            return redirect(url_for("practico", tema=tema))

    return render_template("index.html", nombre=nombre_estudiante, temas=[t["nombre"] for t in _temas_lista])


# ── Búsqueda de recursos educativos (recursos curados + Wikipedia) ────────────
import re as _re

# Recursos curados por subtema — fuente primaria, siempre disponible
_RECURSOS_POR_SUBTEMA = {
    # ── Fundamentos y Análisis Descriptivo ──
    "Conceptos básicos de estadística": [
        {"titulo": "Khan Academy - Qué es la estadística", "url": "https://es.khanacademy.org/math/statistics-probability", "descripcion": "Introducción a la estadística: ramas, tipos y conceptos fundamentales."},
        {"titulo": "Wikipedia - Estadística", "url": "https://es.wikipedia.org/wiki/Estad%C3%ADstica", "descripcion": "Ciencia que trata de la recolección, análisis e interpretación de datos."},
        {"titulo": "Ejemplos de Estadística - Conceptos", "url": "https://www.ejemplos.co/categoria/estadistica/", "descripcion": "Ejemplos prácticos de conceptos estadísticos para entender mejor."},
    ],
    "Tipos de variables": [
        {"titulo": "Wikipedia - Variable estadística", "url": "https://es.wikipedia.org/wiki/Variable_estad%C3%ADstica", "descripcion": "Definición y clasificación de variables cualitativas y cuantitativas."},
        {"titulo": "Khan Academy - Variables cuantitativas y cualitativas", "url": "https://es.khanacademy.org/math/probability/data-distributions-a1", "descripcion": "Diferencias entre variables cualitativas y cuantitativas con ejemplos."},
    ],
    "Escalas de medición": [
        {"titulo": "Wikipedia - Nivel de medición", "url": "https://es.wikipedia.org/wiki/Nivel_de_medici%C3%B3n", "descripcion": "Escalas nominal, ordinal, de intervalo y de razón."},
        {"titulo": "Universo Fórmulas - Escalas de medición", "url": "https://www.universoformulas.com/estadistica/medicion/", "descripcion": "Explicación detallada de las escalas de medición en estadística."},
    ],
    "Población y muestra": [
        {"titulo": "Wikipedia - Población (estadística)", "url": "https://es.wikipedia.org/wiki/Poblaci%C3%B3n_(estad%C3%ADstica)", "descripcion": "Concepto de población y muestra estadística."},
        {"titulo": "Khan Academy - Muestreo y muestreo aleatorio", "url": "https://es.khanacademy.org/math/statistics-probability/sampling-distributions-a1", "descripcion": "Diferencia entre población y muestra, tipos de muestreo."},
    ],
    "Recolección de datos": [
        {"titulo": "Wikipedia - Recolección de datos", "url": "https://es.wikipedia.org/wiki/Recolecci%C3%B3n_de_datos", "descripcion": "Métodos y técnicas para obtener datos."},
        {"titulo": "QuestionPro - Métodos de recolección de datos", "url": "https://www.questionpro.com/blog/es/metodos-de-recoleccion-de-datos/", "descripcion": "Encuestas, entrevistas, observación y otros métodos de recolección."},
    ],
    "Organización de datos": [
        {"titulo": "Wikipedia - Tabla de frecuencias", "url": "https://es.wikipedia.org/wiki/Tabla_de_frecuencias", "descripcion": "Cómo organizar datos en tablas."},
        {"titulo": "Khan Academy - Organización de datos", "url": "https://es.khanacademy.org/math/probability/data-distributions-a1", "descripcion": "Técnicas para organizar y presentar datos estadísticos."},
    ],
    "Tablas de frecuencia": [
        {"titulo": "Wikipedia - Distribución de frecuencias", "url": "https://es.wikipedia.org/wiki/Distribuci%C3%B3n_de_frecuencias", "descripcion": "Tablas y gráficos de frecuencias absolutas y relativas."},
        {"titulo": "Ejemplos de tablas de frecuencia", "url": "https://www.ejemplos.co/tabla-de-frecuencias/", "descripcion": "Ejemplos prácticos de tablas de frecuencia paso a paso."},
    ],
    "Distribución de frecuencias": [
        {"titulo": "Wikipedia - Distribución (estadística)", "url": "https://es.wikipedia.org/wiki/Distribuci%C3%B3n_de_probabilidad", "descripcion": "Cómo se distribuyen los datos en estadística."},
        {"titulo": "Khan Academy - Histogramas y distribuciones", "url": "https://es.khanacademy.org/math/probability/data-distributions-a1", "descripcion": "Visualización de distribuciones con histogramas y polígonos."},
    ],

    # ── Medidas Estadísticas ──
    "Media": [
        {"titulo": "Wikipedia - Media aritmética", "url": "https://es.wikipedia.org/wiki/Media_aritm%C3%A9tica", "descripcion": "Definición, fórmula y ejemplos de la media aritmética."},
        {"titulo": "Khan Academy - Media aritmética", "url": "https://es.khanacademy.org/math/statistics-probability/summarizing-quantitative-data", "descripcion": "Cómo calcular e interpretar la media aritmética."},
        {"titulo": "Ejemplos de media aritmética", "url": "https://www.ejemplos.co/media-aritmetica/", "descripcion": "Ejemplos resueltos de cálculo de media aritmética."},
    ],
    "Mediana": [
        {"titulo": "Wikipedia - Mediana (estadística)", "url": "https://es.wikipedia.org/wiki/Mediana_(estad%C3%ADstica)", "descripcion": "Concepto de mediana y cómo se calcula."},
        {"titulo": "Khan Academy - Mediana", "url": "https://es.khanacademy.org/math/statistics-probability/summarizing-quantitative-data", "descripcion": "Cálculo e interpretación de la mediana."},
    ],
    "Moda": [
        {"titulo": "Wikipedia - Moda (estadística)", "url": "https://es.wikipedia.org/wiki/Moda_(estad%C3%ADstica)", "descripcion": "Definición de moda y su interpretación."},
        {"titulo": "Ejemplos de moda estadística", "url": "https://www.ejemplos.co/moda-estadistica/", "descripcion": "Cómo encontrar la moda en un conjunto de datos."},
    ],
    "Cuartiles": [
        {"titulo": "Wikipedia - Cuartil", "url": "https://es.wikipedia.org/wiki/Cuartil", "descripcion": "Los tres cuartiles que dividen una distribución."},
        {"titulo": "Khan Academy - Cuartiles y rango intercuartílico", "url": "https://es.khanacademy.org/math/probability/data-distributions-a1", "descripcion": "Cómo calcular e interpretar los cuartiles."},
    ],
    "Deciles": [
        {"titulo": "Wikipedia - Decil", "url": "https://es.wikipedia.org/wiki/Decil", "descripcion": "Los nueve deciles que dividen una distribución."},
        {"titulo": "Ejemplos de deciles", "url": "https://www.ejemplos.co/deciles/", "descripcion": "Cálculo e interpretación de deciles con ejemplos."},
    ],
    "Percentiles": [
        {"titulo": "Wikipedia - Percentil", "url": "https://es.wikipedia.org/wiki/Percentil", "descripcion": "Los percentiles y su uso en estadística."},
        {"titulo": "Khan Academy - Percentiles", "url": "https://es.khanacademy.org/math/probability/data-distributions-a1", "descripcion": "Cómo calcular y usar percentiles."},
    ],
    "Rango": [
        {"titulo": "Wikipedia - Rango (estadística)", "url": "https://es.wikipedia.org/wiki/Rango_(estad%C3%ADstica)", "descripcion": "Diferencia entre el valor máximo y mínimo."},
        {"titulo": "Ejemplos de rango estadístico", "url": "https://www.ejemplos.co/rango-estadistico/", "descripcion": "Cálculo del rango y su interpretación."},
    ],
    "Varianza": [
        {"titulo": "Wikipedia - Varianza", "url": "https://es.wikipedia.org/wiki/Varianza", "descripcion": "Definición y fórmula de la varianza poblacional y muestral."},
        {"titulo": "Khan Academy - Varianza", "url": "https://es.khanacademy.org/math/statistics-probability/summarizing-quantitative-data", "descripcion": "Cómo calcular la varianza y su interpretación."},
        {"titulo": "Ejemplos de varianza", "url": "https://www.ejemplos.co/varianza/", "descripcion": "Ejemplos resueltos de cálculo de varianza."},
    ],
    "Desviación estándar": [
        {"titulo": "Wikipedia - Desviación típica", "url": "https://es.wikipedia.org/wiki/Desviaci%C3%B3n_t%C3%ADpica", "descripcion": "Concepto de desviación estándar y su cálculo."},
        {"titulo": "Khan Academy - Desviación estándar", "url": "https://es.khanacademy.org/math/statistics-probability/summarizing-quantitative-data", "descripcion": "Cómo calcular e interpretar la desviación estándar."},
    ],
    "Coeficiente de variación": [
        {"titulo": "Wikipedia - Coeficiente de variación", "url": "https://es.wikipedia.org/wiki/Coeficiente_de_variaci%C3%B3n", "descripcion": "Medida de variabilidad relativa entre dos datos."},
        {"titulo": "Ejemplos de coeficiente de variación", "url": "https://www.ejemplos.co/coeficiente-de-variacion/", "descripcion": "Cálculo y aplicación del coeficiente de variación."},
    ],
    "Asimetría": [
        {"titulo": "Wikipedia - Asimetría (estadística)", "url": "https://es.wikipedia.org/wiki/Asimetr%C3%ADa_(estad%C3%ADstica)", "descripcion": "Medida de asimetría de una distribución."},
        {"titulo": "Ejemplos de asimetría estadística", "url": "https://www.ejemplos.co/asimetria-estadistica/", "descripcion": "Distribuciones simétricas, asimetría positiva y negativa."},
    ],
    "Curtosis": [
        {"titulo": "Wikipedia - Curtosis", "url": "https://es.wikipedia.org/wiki/Curtosis", "descripcion": "Medida de la forma de una distribución (aplanamiento)."},
        {"titulo": "Ejemplos de curtosis", "url": "https://www.ejemplos.co/curtosis/", "descripcion": "Tipos de curtosis y su interpretación."},
    ],
    "Interpretación de resultados": [
        {"titulo": "Wikipedia - Estadística descriptiva", "url": "https://es.wikipedia.org/wiki/Estad%C3%ADstica_descriptiva", "descripcion": "Cómo interpretar medidas estadísticas correctamente."},
        {"titulo": "Khan Academy - Lectura de datos", "url": "https://es.khanacademy.org/math/statistics-probability", "descripcion": "Habilidades para interpretar gráficos y tablas."},
    ],

    # ── Fundamentos de Probabilidad ──
    "Experimentos aleatorios": [
        {"titulo": "Wikipedia - Experimento aleatorio", "url": "https://es.wikipedia.org/wiki/Experimento_aleatorio", "descripcion": "Definición de experimento aleatorio."},
        {"titulo": "Ejemplos de experimentos aleatorios", "url": "https://www.ejemplos.co/experimentos-aleatorios/", "descripcion": "Ejemplos cotidianos de experimentos aleatorios."},
    ],
    "Espacio muestral": [
        {"titulo": "Wikipedia - Espacio muestral", "url": "https://es.wikipedia.org/wiki/Espacio_muestral", "descripcion": "Conjunto de todos los resultados posibles."},
        {"titulo": "Ejemplos de espacio muestral", "url": "https://www.ejemplos.co/espacio-muestral/", "descripcion": "Cómo definir y representar el espacio muestral."},
    ],
    "Eventos y sucesos": [
        {"titulo": "Wikipedia - Evento (probabilidad)", "url": "https://es.wikipedia.org/wiki/Evento_(probabilidad)", "descripcion": "Definición de evento y suceso en probabilidad."},
        {"titulo": "Ejemplos de eventos y sucesos", "url": "https://www.ejemplos.co/eventos-y-sucesos/", "descripcion": "Eventos simples, compuestos y sus relaciones."},
    ],
    "Principio multiplicativo": [
        {"titulo": "Wikipedia - Regla multiplicativa", "url": "https://es.wikipedia.org/wiki/Regla_de_la_multiplicaci%C3%B3n", "descripcion": "Principio multiplicativo en combinatoria y probabilidad."},
        {"titulo": "Ejemplos de principio multiplicativo", "url": "https://www.ejemplos.co/principio-multiplicativo/", "descripcion": "Cómo aplicar el principio multiplicativo paso a paso."},
    ],
    "Permutaciones": [
        {"titulo": "Wikipedia - Permutación", "url": "https://es.wikipedia.org/wiki/Permutaci%C3%B3n", "descripcion": "Cálculo de permutaciones en combinatoria."},
        {"titulo": "Ejemplos de permutaciones", "url": "https://www.ejemplos.co/permutaciones/", "descripcion": "Fórmula y ejemplos de permutaciones con y sin repetición."},
    ],
    "Combinaciones": [
        {"titulo": "Wikipedia - Combinación", "url": "https://es.wikipedia.org/wiki/Combinaci%C3%B3n", "descripcion": "Cálculo de combinaciones en combinatoria."},
        {"titulo": "Ejemplos de combinaciones", "url": "https://www.ejemplos.co/combinaciones/", "descripcion": "Diferencia entre permutaciones y combinaciones con ejemplos."},
    ],
    "Probabilidad clásica": [
        {"titulo": "Wikipedia - Probabilidad clásica", "url": "https://es.wikipedia.org/wiki/Probabilidad_cl%C3%A1sica", "descripcion": "Modelo clásico de probabilidad: casos favorables sobre total."},
        {"titulo": "Khan Academy - Probabilidad", "url": "https://es.khanacademy.org/math/probability/probability-basics", "descripcion": "Introducción a la probabilidad con ejemplos."},
    ],
    "Probabilidad frecuencial": [
        {"titulo": "Wikipedia - Probabilidad frecuencial", "url": "https://es.wikipedia.org/wiki/Probabilidad_frecuencial", "descripcion": "Definición de probabilidad basada en frecuencias."},
        {"titulo": "Ejemplos de probabilidad frecuencial", "url": "https://www.ejemplos.co/probabilidad-frecuencial/", "descripcion": "Cómo calcular probabilidad usando frecuencias."},
    ],
    "Probabilidad subjetiva": [
        {"titulo": "Wikipedia - Probabilidad subjetiva", "url": "https://es.wikipedia.org/wiki/Probabilidad_subjetiva", "descripcion": "Probabilidad basada en juicio personal."},
        {"titulo": "Ejemplos de probabilidad subjetiva", "url": "https://www.ejemplos.co/probabilidad-subjetiva/", "descripcion": "Cuándo y cómo usar la probabilidad subjetiva."},
    ],
    "Probabilidad condicional": [
        {"titulo": "Wikipedia - Probabilidad condicional", "url": "https://es.wikipedia.org/wiki/Probabilidad_condicional", "descripcion": "Definición y fórmula de probabilidad condicional."},
        {"titulo": "Khan Academy - Probabilidad condicional", "url": "https://es.khanacademy.org/math/probability/independent-dependent-probability", "descripcion": "Ejemplos de probabilidad condicional."},
    ],
    "Teorema de Bayes": [
        {"titulo": "Wikipedia - Teorema de Bayes", "url": "https://es.wikipedia.org/wiki/Teorema_de_Bayes", "descripcion": "El teorema de Bayes y su aplicación en estadística."},
        {"titulo": "Ejemplos de teorema de Bayes", "url": "https://www.ejemplos.co/teorema-de-bayes/", "descripcion": "Ejemplos prácticos del teorema de Bayes."},
    ],
    "Eventos independientes y dependientes": [
        {"titulo": "Wikipedia - Independencia (probabilidad)", "url": "https://es.wikipedia.org/wiki/Independencia_(probabilidad)", "descripcion": "Diferencia entre eventos independientes y dependientes."},
        {"titulo": "Khan Academy - Independencia", "url": "https://es.khanacademy.org/math/probability/independent-dependent-probability", "descripcion": "Cómo identificar eventos independientes."},
    ],

    # ── Distribuciones de Probabilidad ──
    "Bernoulli": [
        {"titulo": "Wikipedia - Distribución de Bernoulli", "url": "https://es.wikipedia.org/wiki/Distribuci%C3%B3n_de_Bernoulli", "descripcion": "La distribución más simple: dos resultados posibles."},
        {"titulo": "Ejemplos de distribución Bernoulli", "url": "https://www.ejemplos.co/distribucion-de-bernoulli/", "descripcion": "Ejemplos prácticos de distribución de Bernoulli."},
    ],
    "Binomial": [
        {"titulo": "Wikipedia - Distribución binomial", "url": "https://es.wikipedia.org/wiki/Distribuci%C3%B3n_binomial", "descripcion": "Distribución binomial y su fórmula."},
        {"titulo": "Khan Academy - Distribución binomial", "url": "https://es.khanacademy.org/math/probability/binomial-probability", "descripcion": "Cómo calcular probabilidades con la distribución binomial."},
    ],
    "Poisson": [
        {"titulo": "Wikipedia - Distribución de Poisson", "url": "https://es.wikipedia.org/wiki/Distribuci%C3%B3n_de_Poisson", "descripcion": "Distribución de Poisson para eventos raros."},
        {"titulo": "Ejemplos de distribución de Poisson", "url": "https://www.ejemplos.co/distribucion-de-poisson/", "descripcion": "Ejemplos de eventos que siguen la distribución de Poisson."},
    ],
    "Hipergeométrica": [
        {"titulo": "Wikipedia - Distribución hipergeométrica", "url": "https://es.wikipedia.org/wiki/Distribuci%C3%B3n_hipergeom%C3%A9trica", "descripcion": "Muestreo sin reemplazo: distribución hipergeométrica."},
        {"titulo": "Ejemplos hipergeométrica", "url": "https://www.ejemplos.co/distribucion-hipergeometrica/", "descripcion": "Cómo aplicar la distribución hipergeométrica."},
    ],
    "Uniforme": [
        {"titulo": "Wikipedia - Distribución uniforme", "url": "https://es.wikipedia.org/wiki/Distribuci%C3%B3n_uniforme", "descripcion": "Distribución uniforme continua y discreta."},
        {"titulo": "Ejemplos de distribución uniforme", "url": "https://www.ejemplos.co/distribucion-uniforme/", "descripcion": "Casos prácticos de distribución uniforme."},
    ],
    "Normal": [
        {"titulo": "Wikipedia - Distribución normal", "url": "https://es.wikipedia.org/wiki/Distribuci%C3%B3n_normal", "descripcion": "La campana de Gauss: distribución normal."},
        {"titulo": "Khan Academy - Distribución normal", "url": "https://es.khanacademy.org/math/probability/normal-distribution-basics", "descripcion": "Propiedades y cálculos de la distribución normal."},
    ],
    "Exponencial": [
        {"titulo": "Wikipedia - Distribución exponencial", "url": "https://es.wikipedia.org/wiki/Distribuci%C3%B3n_exponencial", "descripcion": "Tiempo entre eventos en un proceso de Poisson."},
        {"titulo": "Ejemplos de distribución exponencial", "url": "https://www.ejemplos.co/distribucion-exponencial/", "descripcion": "Aplicaciones de la distribución exponencial."},
    ],
    "t de Student": [
        {"titulo": "Wikipedia - Distribución t de Student", "url": "https://es.wikipedia.org/wiki/Distribuci%C3%B3n_t_de_Student", "descripcion": "Distribución t para muestras pequeñas."},
        {"titulo": "Ejemplos de t de Student", "url": "https://www.ejemplos.co/distribucion-t-de-student/", "descripcion": "Cuándo usar la distribución t de Student."},
    ],
    "Chi-cuadrado": [
        {"titulo": "Wikipedia - Distribución chi-cuadrado", "url": "https://es.wikipedia.org/wiki/Distribuci%C3%B3n_chi-cuadrado", "descripcion": "Distribución chi-cuadrado y sus aplicaciones."},
        {"titulo": "Ejemplos de chi-cuadrado", "url": "https://www.ejemplos.co/distribucion-chi-cuadrado/", "descripcion": "Pruebas de bondad de ajuste y tablas de contingencia."},
    ],
    "Cálculo de probabilidades": [
        {"titulo": "Wikipedia - Cálculo de probabilidades", "url": "https://es.wikipedia.org/wiki/C%C3%A1lculo_de_probabilidades", "descripcion": "Métodos para calcular probabilidades."},
        {"titulo": "Khan Academy - Probabilidad", "url": "https://es.khanacademy.org/math/probability", "descripcion": "Lecciones de cálculo de probabilidades."},
    ],
    "Uso de tablas estadísticas": [
        {"titulo": "Wikipedia - Tabla estadística", "url": "https://es.wikipedia.org/wiki/Tabla_estad%C3%ADstica", "descripcion": "Cómo leer y usar tablas de distribución."},
        {"titulo": "Ejemplos de tablas estadísticas", "url": "https://www.ejemplos.co/tablas-estadisticas/", "descripcion": "Guía para usar tablas de distribución normal, t, chi-cuadrado."},
    ],
    "Interpretación de distribuciones": [
        {"titulo": "Wikipedia - Distribución de probabilidad", "url": "https://es.wikipedia.org/wiki/Distribuci%C3%B3n_de_probabilidad", "descripcion": "Cómo interpretar diferentes distribuciones."},
        {"titulo": "Khan Academy - Comparar distribuciones", "url": "https://es.khanacademy.org/math/probability", "descripcion": "Cómo comparar y elegir distribuciones."},
    ],

    # ── Inferencia Estadística ──
    "Muestreo": [
        {"titulo": "Wikipedia - Muestreo estadístico", "url": "https://es.wikipedia.org/wiki/Muestreo_estad%C3%ADstico", "descripcion": "Técnicas de muestreo: aleatorio, estratificado, por conglomerados."},
        {"titulo": "Khan Academy - Muestreo", "url": "https://es.khanacademy.org/math/statistics-probability/sampling-distributions-a1", "descripcion": "Tipos de muestreo y sus características."},
    ],
    "Distribuciones muestrales": [
        {"titulo": "Wikipedia - Distribución muestral", "url": "https://es.wikipedia.org/wiki/Distribuci%C3%B3n_muestral", "descripcion": "Distribución de la media muestral y el teorema central del límite."},
        {"titulo": "Khan Academy - Teorema central del límite", "url": "https://es.khanacademy.org/math/statistics-probability/sampling-distributions-a1", "descripcion": "El teorema central del límite y su importancia."},
    ],
    "Estimación puntual": [
        {"titulo": "Wikipedia - Estimación puntual", "url": "https://es.wikipedia.org/wiki/Estimaci%C3%B3n_puntual", "descripcion": "Estimación de un solo valor para un parámetro."},
        {"titulo": "Ejemplos de estimación puntual", "url": "https://www.ejemplos.co/estimacion-puntual/", "descripcion": "Propiedades de los estimadores: insesgabilidad, eficiencia."},
    ],
    "Intervalos de confianza": [
        {"titulo": "Wikipedia - Intervalo de confianza", "url": "https://es.wikipedia.org/wiki/Intervalo_de_confianza", "descripcion": "Rango de valores que probablemente contiene el parámetro."},
        {"titulo": "Khan Academy - Intervalos de confianza", "url": "https://es.khanacademy.org/math/statistics-probability/confidence-intervals", "descripcion": "Cálculo e interpretación de intervalos de confianza."},
    ],
    "Pruebas de hipótesis": [
        {"titulo": "Wikipedia - Contraste de hipótesis", "url": "https://es.wikipedia.org/wiki/Contraste_de_hip%C3%B3tesis", "descripcion": "Procedimiento de pruebas de hipótesis."},
        {"titulo": "Khan Academy - Pruebas de hipótesis", "url": "https://es.khanacademy.org/math/statistics-probability/significance-tests", "descripcion": "Cómo plantear y resolver pruebas de hipótesis."},
    ],
    "Errores tipo I y II": [
        {"titulo": "Wikipedia - Error tipo I y tipo II", "url": "https://es.wikipedia.org/wiki/Error_tipo_I_y_error_tipo_II", "descripcion": "Falso positivo y falso negativo en pruebas de hipótesis."},
        {"titulo": "Ejemplos de errores tipo I y II", "url": "https://www.ejemplos.co/errores-tipo-i-y-ii/", "descripcion": "Cómo minimizar los errores en pruebas estadísticas."},
    ],
    "Pruebas para medias": [
        {"titulo": "Wikipedia - Prueba Z", "url": "https://es.wikipedia.org/wiki/Prueba_Z", "descripcion": "Prueba Z para una y dos muestras."},
        {"titulo": "Ejemplos de pruebas para medias", "url": "https://www.ejemplos.co/pruebas-para-medias/", "descripcion": "Cuándo usar prueba Z, t de Student para comparar medias."},
    ],
    "Pruebas para proporciones": [
        {"titulo": "Wikipedia - Prueba de proporciones", "url": "https://es.wikipedia.org/wiki/Prueba_de_proporciones", "descripcion": "Prueba de hipótesis para proporciones."},
        {"titulo": "Ejemplos de pruebas para proporciones", "url": "https://www.ejemplos.co/pruebas-para-proporciones/", "descripcion": "Cálculo de pruebas Z para proporciones."},
    ],
    "Comparación de grupos": [
        {"titulo": "Wikipedia - Prueba t de Student", "url": "https://es.wikipedia.org/wiki/Prueba_t_de_Student", "descripcion": "Comparación de dos muestras independientes."},
        {"titulo": "Khan Academy - Comparación de medias", "url": "https://es.khanacademy.org/math/statistics-probability/significance-tests", "descripcion": "Cómo comparar medias entre grupos."},
    ],
    "Interpretación de resultados (Inferencia)": [
        {"titulo": "Wikipedia - Inferencia estadística", "url": "https://es.wikipedia.org/wiki/Inferencia_estad%C3%ADstica", "descripcion": "Cómo interpretar resultados de inferencia."},
        {"titulo": "Khan Academy - Interpretar resultados", "url": "https://es.khanacademy.org/math/statistics-probability", "descripcion": "Guía para interpretar pruebas estadísticas."},
    ],

    # ── Modelado y Análisis de Relaciones ──
    "Covarianza": [
        {"titulo": "Wikipedia - Covarianza", "url": "https://es.wikipedia.org/wiki/Covarianza", "descripcion": "Medida de variación conjunta entre dos variables."},
        {"titulo": "Ejemplos de covarianza", "url": "https://www.ejemplos.co/covarianza/", "descripcion": "Cálculo e interpretación de la covarianza."},
    ],
    "Correlación Pearson": [
        {"titulo": "Wikipedia - Coeficiente de correlación de Pearson", "url": "https://es.wikipedia.org/wiki/Coeficiente_de_correlaci%C3%B3n_de_Pearson", "descripcion": "Medida de correlación lineal entre dos variables."},
        {"titulo": "Khan Academy - Correlación", "url": "https://es.khanacademy.org/math/statistics-probability/describing-relationships", "descripcion": "Cómo medir y interpretar la correlación."},
    ],
    "Correlación Spearman": [
        {"titulo": "Wikipedia - Correlación de rangos de Spearman", "url": "https://es.wikipedia.org/wiki/Coeficiente_de_correlaci%C3%B3n_de_rangos_de_Spearman", "descripcion": "Correlación no paramétrica por rangos."},
        {"titulo": "Ejemplos de correlación Spearman", "url": "https://www.ejemplos.co/correlacion-de-spearman/", "descripcion": "Cuándo usar Spearman en lugar de Pearson."},
    ],
    "Regresión lineal simple": [
        {"titulo": "Wikipedia - Regresión lineal", "url": "https://es.wikipedia.org/wiki/Regresi%C3%B3n_lineal", "descripcion": "Modelo de regresión lineal y sus componentes."},
        {"titulo": "Khan Academy - Regresión lineal", "url": "https://es.khanacademy.org/math/statistics-probability/describing-relationships", "descripcion": "Cómo ajustar una recta de regresión a los datos."},
    ],
    "Regresión lineal múltiple": [
        {"titulo": "Wikipedia - Regresión lineal múltiple", "url": "https://es.wikipedia.org/wiki/Regresi%C3%B3n_lineal_m%C3%BAltiple", "descripcion": "Regresión con múltiples variables predictoras."},
        {"titulo": "Ejemplos de regresión múltiple", "url": "https://www.ejemplos.co/regresion-lineal-multiple/", "descripcion": "Cómo interpretar coeficientes en regresión múltiple."},
    ],
    "Coeficiente de determinación R²": [
        {"titulo": "Wikipedia - Coeficiente de determinación", "url": "https://es.wikipedia.org/wiki/Coeficiente_de_determinaci%C3%B3n", "descripcion": "Porcentaje de varianza explicada por el modelo."},
        {"titulo": "Khan Academy - R²", "url": "https://es.khanacademy.org/math/statistics-probability/describing-relationships", "descripcion": "Interpretación del R² en regresión."},
    ],
    "Predicción de valores": [
        {"titulo": "Wikipedia - Predicción estadística", "url": "https://es.wikipedia.org/wiki/Predicci%C3%B3n_estad%C3%ADstica", "descripcion": "Uso del modelo de regresión para predecir."},
        {"titulo": "Ejemplos de predicción", "url": "https://www.ejemplos.co/prediccion-estadistica/", "descripcion": "Cómo usar la ecuación de regresión para predecir valores."},
    ],
    "Análisis de residuos": [
        {"titulo": "Wikipedia - Análisis de residuos", "url": "https://es.wikipedia.org/wiki/An%C3%A1lisis_de_residuos", "descripcion": "Diagnóstico del modelo de regresión."},
        {"titulo": "Ejemplos de análisis de residuos", "url": "https://www.ejemplos.co/analisis-de-residuos/", "descripcion": "Cómo interpretar gráficos de residuos."},
    ],
    "Interpretación de modelos": [
        {"titulo": "Wikipedia - Modelos estadísticos", "url": "https://es.wikipedia.org/wiki/Modelo_estad%C3%ADstico", "descripcion": "Cómo interpretar los parámetros de un modelo."},
        {"titulo": "Khan Academy - Interpretar modelos", "url": "https://es.khanacademy.org/math/statistics-probability", "descripcion": "Guía para interpretar modelos de regresión."},
    ],
    "Aplicaciones en negocios e investigación": [
        {"titulo": "Wikipedia - Estadística aplicada", "url": "https://es.wikipedia.org/wiki/Estad%C3%ADstica_aplicada", "descripcion": "Uso de la estadística en negocios e investigación."},
        {"titulo": "Ejemplos de estadística aplicada", "url": "https://www.ejemplos.co/estadistica-aplicada/", "descripcion": "Casos reales de uso de estadística en empresas."},
    ],
}


def _buscar_wikipedia(subtema: str, tema: str, cantidad: int = 5) -> list:
    """Busca artículos educativos en Wikipedia como complemento."""
    try:
        import requests as _requests

        headers = {"User-Agent": "IAEducativaBootcamp/1.0 (educational project)"}
        consulta = f'"{subtema}" {tema} estadistica'
        params = {
            "action": "query",
            "list": "search",
            "srsearch": consulta,
            "srlimit": cantidad + 3,
            "format": "json",
            "utf8": 1,
        }

        resp = _requests.get(
            "https://es.wikipedia.org/w/api.php",
            params=params,
            headers=headers,
            timeout=8,
        )
        resp.raise_for_status()
        data = resp.json()

        resultados = []
        for item in data.get("query", {}).get("search", []):
            title = item.get("title", "")
            snippet = item.get("snippet", "")
            snippet_limpio = _re.sub(r"<[^>]+>", "", snippet)[:200]
            url = f"https://es.wikipedia.org/wiki/{title.replace(' ', '_')}"
            resultados.append({
                "titulo": title,
                "url": url,
                "descripcion": snippet_limpio,
            })
            if len(resultados) >= cantidad:
                break

        return resultados
    except Exception as e:
        print(f"[buscar_wikipedia] Error: {e}")
        return []


# Fallback universal cuando no hay recursos específicos
_RECURSOS_UNIVERSALES = [
    {"titulo": "Khan Academy - Estadística y probabilidad", "url": "https://es.khanacademy.org/math/statistics-probability", "descripcion": "Curso completo de estadística y probabilidad con ejercicios."},
    {"titulo": "Wikipedia - Glossary of probability and statistics", "url": "https://es.wikipedia.org/wiki/Glosario_de_probabilidad_y_estad%C3%ADstica", "descripcion": "Glosario completo de términos estadísticos."},
]


def buscar_recursos_web(subtema: str, tema: str = "", cantidad: int = 5) -> list:
    """Busca recursos educativos: curados por subtema, luego Wikipedia, luego fallback."""
    ahora = time.time()
    clave = f"{subtema}_{tema}_{cantidad}"
    if clave in _recursos_cache:
        resultados, ts = _recursos_cache[clave]
        if ahora - ts < 600:
            return resultados

    resultados = []

    # 1. Recursos curados por subtema (máxima relevancia)
    if subtema in _RECURSOS_POR_SUBTEMA:
        resultados.extend(_RECURSOS_POR_SUBTEMA[subtema][:cantidad])

    # 2. Wikipedia como complemento si faltan resultados
    if len(resultados) < cantidad:
        wiki_resultados = _buscar_wikipedia(subtema, tema, cantidad)
        urls_existentes = {r["url"] for r in resultados}
        for r in wiki_resultados:
            if len(resultados) >= cantidad:
                break
            if r["url"] not in urls_existentes:
                resultados.append(r)
                urls_existentes.add(r["url"])

    # 3. Fallback universal si no hubo resultados
    if not resultados:
        resultados = _RECURSOS_UNIVERSALES[:cantidad]

    _recursos_cache[clave] = (resultados, time.time())
    return resultados


# ---------------------- VISUAL ------------------------
@app.route("/visual")
@login_required
def visual():
    nombre  = session.get("student_data", {}).get("nombre", "Estudiante")
    tema    = request.args.get("tema")
    subtema = request.args.get("subtema", "").strip()

    if not tema:
        tema = "Tema no especificado"

    introduccion = (
        f"📘 El tema '{tema}' trata sobre los conceptos fundamentales de "
        f"{tema.lower()} en el campo de la estadística. "
        f"En esta sección aprenderás su aplicación práctica, ejemplos visuales y cómo interpretarlo."
    )

    # Subtemas disponibles para la categoría actual
    subtemas_lista = TEMAS_ESTADISTICA.get(tema, [])

    # Query dinámica: subtema seleccionado o el tema general
    query_videos = f"{subtema} Estadística" if subtema else f"{tema} Estadística"
    videos = get_youtube_videos(query_videos, 6, ttl=600)
    random.shuffle(videos)
    videos = videos[:3]

    # Recursos educativos solo si hay subtema seleccionado
    recursos = buscar_recursos_web(subtema, tema) if subtema else []

    user_id = session.get('user')
    if user_id:
        StudentData.update_student_progress(user_id, tema, ejercicio_completado=False)

    return render_template(
        "visual.html",
        nombre=nombre,
        tema=tema,
        subtema=subtema,
        subtemas_lista=subtemas_lista,
        introduccion=introduccion,
        videos=videos,
        recursos=recursos,
    )


# ---------------------- PRÁCTICO ------------------------
@app.route("/practico", methods=["GET", "POST"])
@login_required
def practico():
    nombre = session.get("student_data", {}).get("nombre", "Estudiante")
    tema   = request.args.get("tema")

    if not tema:
        flash("⚠️ Tema no especificado.", "error")
        return redirect(url_for("index"))

    session['tema_actual'] = tema

    user_id = session.get('user')
    if user_id:
        StudentData.update_student_progress(user_id, tema, ejercicio_completado=False)

    return render_template(
        "practico.html",
        nombre=nombre,
        tema=tema,
        preguntas=[],
    )


@app.route("/generar_preguntas", methods=["POST"])
@login_required
def generar_preguntas():
    """Generar preguntas de forma asíncrona."""
    import time as _time
    try:
        data  = request.get_json()
        tema  = data.get('tema')

        if not tema:
            return jsonify({"success": False, "error": "Tema no especificado"})

        user_id      = session.get('user')
        student_data = session.get('student_data')
        nivel_academico = "universidad"
        intereses = None

        if student_data:
            if 'nivel_academico' in student_data:
                nivel_academico = student_data['nivel_academico']
            intereses = student_data.get('intereses')

        info_tema = obtener_info_tema(tema)
        excluir_ids = StudentData.preguntas_ya_vistas(user_id, tema) if user_id else set()

        # Verificar si hay banco disponible (para delay inteligente en el frontend)
        from gemini_service import BancoPreguntas as _BP
        _bp_check = _BP()
        tiene_banco = _bp_check.hay_banco_para_tema(tema, nivel_academico)

        t0 = _time.time()
        gemini_service = get_gemini_service()
        preguntas = gemini_service.generar_preguntas(
            tema_nombre=tema,
            nivel_academico=nivel_academico,
            cantidad=10,
            descripcion=info_tema["descripcion"] if info_tema else None,
            conceptos_clave=info_tema["conceptos_clave"] if info_tema else None,
            intereses=intereses,
            excluir_ids=excluir_ids,
        )
        tiempo_ms = int((_time.time() - t0) * 1000)

        # Determinar la fuente real de las preguntas
        son_fallback = all(p.get("es_fallback") for p in preguntas)
        alguna_real  = any(not p.get("es_fallback") for p in preguntas)
        if son_fallback:
            fuente = "fallback"
        elif tiene_banco and tiempo_ms < 500:
            fuente = "banco"
        elif alguna_real and tiempo_ms > 500:
            fuente = "gemini_live"
        else:
            fuente = "cache"

        # Banner de fallback: solo si TODAS las preguntas son fallback
        # (preguntas del banco curado NO deben triggerear este banner)
        todas_fallback = all(p.get("es_fallback") for p in preguntas)
        alguna_real = any(not p.get("es_fallback") for p in preguntas)
        mostrar_fallback = todas_fallback and not alguna_real

        # Registrar IDs vistos — incluir TODAS las preguntas (banco y cache)
        # para que el contador "X/20 preguntas vistas" funcione correctamente
        ids_servidos = [p["id_estable"] for p in preguntas if p.get("id_estable")]
        if ids_servidos and user_id:
            StudentData.registrar_preguntas_vistas(user_id, tema, ids_servidos)

        nuevos_ids = [i for i in ids_servidos if i not in excluir_ids]
        vistas_total = len(excluir_ids) + len(nuevos_ids)

        # Tamaño real del pool para este tema/nivel
        from gemini_service import BancoPreguntas
        _banco = BancoPreguntas()
        pool_size = max(20, _banco.total_disponibles(tema, nivel_academico) + _banco.total_en_cache(tema, nivel_academico))
        en_rotacion = vistas_total >= pool_size

        return jsonify({
            "success": True,
            "preguntas": preguntas,
            "fallback": mostrar_fallback,
            "fuente": fuente,
            "tiempo_ms": tiempo_ms,
            "info_ronda": {
                "vistas": vistas_total,
                "total_pool": pool_size,
                "en_rotacion": en_rotacion,
                "nivel": nivel_academico,
            },
        })

    except Exception as e:
        print(f"Error generando preguntas: {e}")
        return jsonify({"success": False, "error": str(e)})


@app.route("/evaluar_respuestas", methods=["POST"])
@login_required
def evaluar_respuestas():
    """Evaluar respuestas localmente (cerradas) y mostrar respuestas sugeridas (abiertas/reflexión) sin usar la API."""
    try:
        data              = request.get_json()
        tema              = data.get('tema')
        preguntas         = data.get('preguntas')
        respuestas_usuario = data.get('respuestas')

        if not all([tema, preguntas, respuestas_usuario]):
            return jsonify({"success": False, "error": "Datos incompletos"})

        respuestas_evaluadas = []
        puntaje_total_cerradas = 0
        cantidad_cerradas = 0

        for pregunta in preguntas:
            pregunta_id      = pregunta['id']
            respuesta_usuario = respuestas_usuario.get(str(pregunta_id), '')

            tipo = pregunta.get("tipo", "opcion_multiple")
            if tipo in ("opcion_multiple", "verdadero_falso"):
                resp_correcta = pregunta.get("respuesta_correcta", "").strip().upper()
                resp_usuario = respuesta_usuario.strip().upper()
                es_correcta = resp_usuario == resp_correcta

                resultado = {
                    "pregunta_id":      pregunta_id,
                    "respuesta_usuario": respuesta_usuario,
                    "correcta":         es_correcta,
                    "puntaje":          1.0 if es_correcta else 0.0,
                    "explicacion":      pregunta.get("explicacion", ""),
                    "respuesta_correcta": pregunta.get("respuesta_correcta", "")
                }
                puntaje_total_cerradas += resultado["puntaje"]
                cantidad_cerradas += 1
            else:
                # Pregunta abierta (Ejercicio de Reflexión)
                resultado = {
                    "pregunta_id":      pregunta_id,
                    "respuesta_usuario": respuesta_usuario,
                    "correcta":         None,  # No aplica calificación
                    "puntaje":          None,
                    "explicacion":      pregunta.get("explicacion", ""),
                    "respuesta_correcta": pregunta.get("respuesta_correcta", "")
                }

            respuestas_evaluadas.append(resultado)

        if cantidad_cerradas > 0:
            puntaje_final = (puntaje_total_cerradas / cantidad_cerradas) * 100
        else:
            puntaje_final = 100.0  # Fallback si no hay preguntas cerradas

        user_id = session.get('user')
        if user_id:
            progreso = {
                "tema":                   tema,
                "puntaje":                puntaje_final,
                "fecha":                  datetime.now().isoformat(),
                "preguntas_respondidas":  len(preguntas),
                "respuestas_correctas":   sum(1 for r in respuestas_evaluadas if r["correcta"] is True),
            }

            StudentData.update_student_progress(user_id, tema, ejercicio_completado=True)

            historial_result = StudentData.save_evaluation_history(user_id, progreso)
            if not historial_result["success"]:
                print(f"Error guardando historial: {historial_result['error']}")

        return jsonify({
            "success":       True,
            "puntaje_final": puntaje_final,
            "respuestas":    respuestas_evaluadas,
            "tema":          tema,
        })

    except Exception as e:
        print(f"Error evaluando respuestas: {e}")
        return jsonify({"success": False, "error": str(e)})


if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))

    if sys.platform == "win32":
        # Gunicorn no funciona en Windows → usamos Waitress
        try:
            from waitress import serve
            print(f"[IA Educativa] Servidor iniciado → http://localhost:{port}")
            print("[IA Educativa] Presiona Ctrl+C para detener.")
            serve(app, host="0.0.0.0", port=port, threads=4)
        except ImportError:
            # Si waitress no está instalado, caer de vuelta al servidor de desarrollo
            print("[ADVERTENCIA] waitress no encontrado. Usando servidor de desarrollo.")
            print(f"[IA Educativa] Servidor iniciado → http://localhost:{port}")
            app.run(host="0.0.0.0", port=port, debug=False)
    else:
        app.run(host="0.0.0.0", port=port, debug=False)