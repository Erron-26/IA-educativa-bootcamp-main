import os
import sys
import random
import time
import functools
from dotenv import load_dotenv
load_dotenv()

# ── Fix de encoding para la consola de Windows (CMD/PowerShell) ──────────────
# Sin esto, los caracteres en español (tildes, ñ) se ven como símbolos raros.
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
# ─────────────────────────────────────────────────────────────────────────────

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
            flash("Por favor completa todos los campos.")
            return redirect(url_for("login"))

        result = LocalAuth.login_user(email, password)

        if result["success"]:
            user_id = result['user']['localId']
            session['user'] = user_id
            session['email'] = email

            student_data = StudentData.get_student_data(user_id)
            if student_data["success"]:
                session['student_data'] = student_data["data"]

            flash("Inicio de sesión exitoso.")
            return redirect(url_for("index"))
        else:
            flash(f"Error al iniciar sesión: {result['error']}")

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
            flash("Por favor completa todos los campos.")
            return redirect(url_for("register"))

        if password != confirm_password:
            flash("Las contraseñas no coinciden.")
            return redirect(url_for("register"))

        if len(password) < 6:
            flash("La contraseña debe tener al menos 6 caracteres.")
            return redirect(url_for("register"))

        # ── Validar edad y asignar nivel según criterios ──────────
        try:
            edad = int(edad_str)
        except ValueError:
            flash("La edad debe ser un número válido.")
            return redirect(url_for("register"))

        if edad < 12:
            flash("La edad mínima para registrarse es 12 años.")
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
                flash("Por favor selecciona tu nivel educativo.")
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
                flash("Cuenta creada exitosamente. Ahora puedes iniciar sesión.")
                return redirect(url_for("login"))
            else:
                flash(f"Error al guardar datos del estudiante: {save_result['error']}")
        else:
            flash(f"Error al crear la cuenta: {result['error']}")

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

        temas_disponibles = temas["Estadística"]
        if not tema or not estilo:
            flash("⚠️ Por favor completa todos los campos.")
            return redirect(url_for("index"))

        if tema not in temas_disponibles:
            flash("El tema seleccionado no es válido. Selecciona uno de la lista.")
            return redirect(url_for("index"))

        if estilo == "Visual":
            return redirect(url_for("visual", nombre=nombre_estudiante, tema=tema))
        elif estilo == "Práctico":
            return redirect(url_for("practico", nombre=nombre_estudiante, tema=tema))

    return render_template("index.html", nombre=nombre_estudiante, temas=temas["Estadística"])


# ---------------------- VISUAL ------------------------
@app.route("/visual")
@login_required
def visual():
    nombre = request.args.get("nombre")
    tema   = request.args.get("tema")

    if not tema:
        tema = "Tema no especificado"

    introduccion = (
        f"📘 El tema '{tema}' trata sobre los conceptos fundamentales de "
        f"{tema.lower()} en el campo de la estadística. "
        f"En esta sección aprenderás su aplicación práctica, ejemplos visuales y cómo interpretarlo."
    )

    videos = get_youtube_videos(f"{tema} Estadística", 6, ttl=600)
    random.shuffle(videos)
    videos = videos[:3]

    user_id = session.get('user')
    if user_id:
        StudentData.update_student_progress(user_id, tema, ejercicio_completado=False)

    return render_template(
        "visual.html",
        nombre=nombre,
        tema=tema,
        introduccion=introduccion,
        videos=videos,
    )


# ---------------------- PRÁCTICO ------------------------
@app.route("/practico", methods=["GET", "POST"])
@login_required
def practico():
    nombre = request.args.get("nombre")
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
    try:
        data  = request.get_json()
        tema  = data.get('tema')

        if not tema:
            return jsonify({"success": False, "error": "Tema no especificado"})

        user_id      = session.get('user')
        student_data = session.get('student_data')
        nivel_academico = "universidad"

        if student_data and 'nivel_academico' in student_data:
            nivel_academico = student_data['nivel_academico']

        gemini_service = get_gemini_service()
        preguntas = gemini_service.generar_preguntas(tema, nivel_academico, cantidad=10)

        session['preguntas_actuales'] = preguntas

        return jsonify({"success": True, "preguntas": preguntas})

    except Exception as e:
        print(f"Error generando preguntas: {e}")
        return jsonify({"success": False, "error": str(e)})


@app.route("/evaluar_respuestas", methods=["POST"])
@login_required
def evaluar_respuestas():
    """Evaluar respuestas usando Gemini."""
    try:
        data              = request.get_json()
        tema              = data.get('tema')
        preguntas         = data.get('preguntas')
        respuestas_usuario = data.get('respuestas')

        if not all([tema, preguntas, respuestas_usuario]):
            return jsonify({"success": False, "error": "Datos incompletos"})

        gemini_service     = get_gemini_service()
        respuestas_evaluadas = []
        puntaje_total      = 0

        for pregunta in preguntas:
            pregunta_id      = pregunta['id']
            respuesta_usuario = respuestas_usuario.get(str(pregunta_id), '')

            evaluacion = gemini_service.evaluar_respuesta(pregunta, respuesta_usuario)

            resultado = {
                "pregunta_id":      pregunta_id,
                "respuesta_usuario": respuesta_usuario,
                "correcta":         evaluacion["correcta"],
                "puntaje":          evaluacion["puntaje"],
                "explicacion":      evaluacion["explicacion"],
            }

            respuestas_evaluadas.append(resultado)
            puntaje_total += evaluacion["puntaje"]

        puntaje_final = (puntaje_total / len(preguntas)) * 100

        user_id = session.get('user')
        if user_id:
            progreso = {
                "tema":                   tema,
                "puntaje":                puntaje_final,
                "fecha":                  datetime.now().isoformat(),
                "preguntas_respondidas":  len(preguntas),
                "respuestas_correctas":   sum(1 for r in respuestas_evaluadas if r["correcta"]),
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