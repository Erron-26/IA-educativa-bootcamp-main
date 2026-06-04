import os
from dotenv import load_dotenv
load_dotenv()

from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from busquedas import buscar_videos_youtube
from temas import temas
from db_config import FirebaseAuth, StudentData
from gemini_service import GeminiService
import random
import json
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "clave_secreta_demo")

# Decorador para verificar autenticación
def login_required(f):
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
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
        
        result = FirebaseAuth.login_user(email, password)
        
        if result["success"]:
            user_id = result['user']['localId']
            session['user'] = user_id
            session['email'] = email
            
            # Cargar datos del estudiante
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
        email = request.form.get("email")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")
        nombre = request.form.get("nombre")
        edad = request.form.get("edad")
        nivel_educativo = request.form.get("nivel_educativo")
        intereses = request.form.get("intereses")
        
        # Validar campos obligatorios
        required_fields = [email, password, confirm_password, nombre, edad, nivel_educativo, intereses]
        if not all(required_fields):
            flash("Por favor completa todos los campos.")
            return redirect(url_for("register"))
        
        if password != confirm_password:
            flash("Las contraseñas no coinciden.")
            return redirect(url_for("register"))
        
        if len(password) < 6:
            flash("La contraseña debe tener al menos 6 caracteres.")
            return redirect(url_for("register"))
        
        # Crear usuario en Firebase Auth
        result = FirebaseAuth.register_user(email, password)
        
        if result["success"]:
            user_id = result["user"]["localId"]
            
            # Mapear nivel educativo al formato del sistema
            nivel_mapping = {
                "secundaria": "bachillerato",
                "bachillerato": "bachillerato", 
                "universidad": "universidad",
                "posgrado": "postgrado",
                "otro": "universidad"  # Default para "otro"
            }
            nivel_academico = nivel_mapping.get(nivel_educativo, "universidad")
            
            # Guardar datos adicionales del estudiante
            student_data = {
                "email": email,
                "nombre": nombre,
                "edad": int(edad),
                "nivel_educativo": nivel_educativo,
                "nivel_academico": nivel_academico,  # Para el sistema de preguntas
                "intereses": intereses,
                "fecha_registro": str(__import__('datetime').datetime.now()),
                "progreso": {},
                "activo": True
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
    user_id = session.get('user')
    student_data = session.get('student_data')
    
    if not student_data:
        # Intentar cargar desde la base de datos
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
    FirebaseAuth.logout_user()
    flash("Sesión cerrada exitosamente.")
    return redirect(url_for("login"))

@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    asignatura = "Estadística"

    # Cargar nombre del estudiante desde la sesión o Firebase
    user_id = session.get("user")
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
        tema = request.form.get("tema")
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
    tema = request.args.get("tema")

    # Evitar errores si el tema llega vacío
    if not tema:
        tema = "Tema no especificado"

    # Introducción dinámica
    introduccion = (
        f"📘 El tema '{tema}' trata sobre los conceptos fundamentales de "
        f"{tema.lower()} en el campo de la estadística. "
        f"En esta sección aprenderás su aplicación práctica, ejemplos visuales y cómo interpretarlo."
    )

    # Obtener videos aleatorios
    videos = buscar_videos_youtube(f"{tema} Estadística", 6)
    random.shuffle(videos)
    videos = videos[:3]  # muestra 3 aleatorios

    # Registrar progreso del estudiante
    user_id = session.get('user')
    if user_id:
        StudentData.update_student_progress(user_id, tema, ejercicio_completado=False)

    return render_template(
        "visual.html",
        nombre=nombre,
        tema=tema,
        introduccion=introduccion,
        videos=videos
    )


# ---------------------- PRÁCTICO ------------------------
@app.route("/practico", methods=["GET", "POST"])
@login_required
def practico():
    nombre = request.args.get("nombre")
    tema = request.args.get("tema")

    # Evitar errores si el tema llega vacío
    if not tema:
        flash("⚠️ Tema no especificado.")
        return redirect(url_for("index"))

    # Guardar tema en sesión para generación asíncrona
    session['tema_actual'] = tema
    
    # Registrar progreso del estudiante
    user_id = session.get('user')
    if user_id:
        StudentData.update_student_progress(user_id, tema, ejercicio_completado=False)

    # Mostrar página inmediatamente con skeleton loading
    return render_template(
        "practico.html",
        nombre=nombre,
        tema=tema,
        preguntas=[]  # Vacío inicialmente
    )

@app.route("/generar_preguntas", methods=["POST"])
@login_required
def generar_preguntas():
    """Generar preguntas de forma asíncrona"""
    try:
        data = request.get_json()
        tema = data.get('tema')
        
        if not tema:
            return jsonify({"success": False, "error": "Tema no especificado"})
        
        # Obtener nivel académico del estudiante
        user_id = session.get('user')
        student_data = session.get('student_data')
        nivel_academico = "universidad"  # Default
        
        if student_data and 'nivel_academico' in student_data:
            nivel_academico = student_data['nivel_academico']
        
        # Generar preguntas con Gemini
        gemini_service = GeminiService()
        preguntas = gemini_service.generar_preguntas(tema, nivel_academico, cantidad=10)
        
        # Guardar preguntas en la sesión
        session['preguntas_actuales'] = preguntas
        
        return jsonify({
            "success": True,
            "preguntas": preguntas
        })
        
    except Exception as e:
        print(f"Error generando preguntas: {e}")
        return jsonify({"success": False, "error": str(e)})

@app.route("/evaluar_respuestas", methods=["POST"])
@login_required
def evaluar_respuestas():
    """Evaluar respuestas usando Gemini"""
    try:
        data = request.get_json()
        tema = data.get('tema')
        preguntas = data.get('preguntas')
        respuestas_usuario = data.get('respuestas')
        
        if not all([tema, preguntas, respuestas_usuario]):
            return jsonify({"success": False, "error": "Datos incompletos"})
        
        # Evaluar respuestas con Gemini
        gemini_service = GeminiService()
        respuestas_evaluadas = []
        puntaje_total = 0
        
        for pregunta in preguntas:
            pregunta_id = pregunta['id']
            respuesta_usuario = respuestas_usuario.get(str(pregunta_id), '')
            
            # Evaluar respuesta
            evaluacion = gemini_service.evaluar_respuesta(pregunta, respuesta_usuario)
            
            resultado = {
                "pregunta_id": pregunta_id,
                "respuesta_usuario": respuesta_usuario,
                "correcta": evaluacion["correcta"],
                "puntaje": evaluacion["puntaje"],
                "explicacion": evaluacion["explicacion"]
            }
            
            respuestas_evaluadas.append(resultado)
            puntaje_total += evaluacion["puntaje"]
        
        # Calcular puntaje final
        puntaje_final = (puntaje_total / len(preguntas)) * 100
        
        # Guardar progreso en Firebase
        user_id = session.get('user')
        if user_id:
            progreso = {
                "tema": tema,
                "puntaje": puntaje_final,
                "fecha": datetime.now().isoformat(),
                "preguntas_respondidas": len(preguntas),
                "respuestas_correctas": sum(1 for r in respuestas_evaluadas if r["correcta"])
            }
            
            # Actualizar progreso del estudiante
            StudentData.update_student_progress(user_id, tema, ejercicio_completado=True)
            
            # Guardar historial de evaluaciones
            historial_result = StudentData.save_evaluation_history(user_id, progreso)
            if not historial_result["success"]:
                print(f"Error guardando historial: {historial_result['error']}")
        
        return jsonify({
            "success": True,
            "puntaje_final": puntaje_final,
            "respuestas": respuestas_evaluadas,
            "tema": tema
        })
        
    except Exception as e:
        print(f"Error evaluando respuestas: {e}")
        return jsonify({"success": False, "error": str(e)})



if __name__ == "__main__":
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)