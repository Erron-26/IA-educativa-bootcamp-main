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
app.secret_key = os.getenv("FLASK_SECRET_KEY", "clave_secreta_demo")

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
    if request.method == "POST":
        email            = request.form.get("email", "").strip()
        password         = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        nombre           = request.form.get("nombre", "").strip()
        edad_str         = request.form.get("edad", "").strip()
        nivel_educativo  = request.form.get("nivel_educativo", "").strip()
        intereses        = request.form.get("intereses", "estadistica").strip()

        # ── Validar campos básicos ────────────────────────────────
        if not all([email, password, confirm_password, nombre, edad_str]):
            flash("Por favor completa todos los campos.", "error")
            return redirect(url_for("register"))

        if password != confirm_password:
            flash("Las contraseñas no coinciden.", "error")
            return redirect(url_for("register"))

        if len(password) < 6:
            flash("La contraseña debe tener al menos 6 caracteres.", "error")
            return redirect(url_for("register"))

        # ── Validar edad y asignar nivel según criterios ──────────
        try:
            edad = int(edad_str)
        except ValueError:
            flash("La edad debe ser un número válido.", "error")
            return redirect(url_for("register"))

        if edad < 12:
            flash("La edad mínima para registrarse es 12 años.", "error")
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

    return render_template("register.html")


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
            flash("Error al cargar datos del perfil.")
            return redirect(url_for("index"))

    return render_template("perfil.html", student_data=student_data)


@app.route("/logout")
def logout():
    LocalAuth.logout_user()
    flash("Sesión cerrada exitosamente.")
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
            flash("⚠️ Por favor completa todos los campos.")
            return redirect(url_for("index"))

        if tema not in _temas_por_nombre:
            flash("El tema seleccionado no es válido. Selecciona uno de la lista.")
            return redirect(url_for("index"))

        if estilo == "Visual":
            return redirect(url_for("visual", tema=tema))
        elif estilo == "Práctico":
            return redirect(url_for("practico", tema=tema))

    return render_template("index.html", nombre=nombre_estudiante, temas=[t["nombre"] for t in _temas_lista])


# ── Búsqueda de recursos web/PDFs con DuckDuckGo ──────────────────────────────
def buscar_recursos_web(subtema: str, cantidad: int = 5) -> list:
    """Busca PDFs y recursos educativos en la web via DuckDuckGo."""
    ahora = time.time()
    clave = f"{subtema}_{cantidad}"
    if clave in _recursos_cache:
        resultados, ts = _recursos_cache[clave]
        if ahora - ts < 600:
            return resultados

    try:
        # pyrefly: ignore [missing-import]
        from duckduckgo_search import DDGS
        query = f"{subtema} estadística filetype:pdf"
        resultados = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=cantidad):
                resultados.append({
                    "titulo":      r.get("title", subtema),
                    "url":         r.get("href", ""),
                    "descripcion": r.get("body", "")[:200],
                })
        _recursos_cache[clave] = (resultados, time.time())
        return resultados
    except Exception as e:
        print(f"[buscar_recursos_web] Error: {e}")
        return []


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

    # Recursos web/PDFs solo si hay subtema seleccionado
    recursos = buscar_recursos_web(subtema) if subtema else []

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
        flash("⚠️ Tema no especificado.")
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