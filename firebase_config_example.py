# ARCHIVO DE EJEMPLO - COPIA ESTE CONTENIDO A firebase_config.py Y CONFIGURA TUS DATOS

import pyrebase
import os
from flask import session

# IMPORTANTE: Reemplaza estos valores con los de tu proyecto Firebase
firebase_config = {
    "apiKey": "TU_API_KEY_AQUI",  # Ve a Project Settings > General > Web API Key
    "authDomain": "tu-proyecto.firebaseapp.com",  # tu-proyecto-id.firebaseapp.com
    "projectId": "tu-proyecto-id",  # El ID de tu proyecto Firebase
    "storageBucket": "tu-proyecto.appspot.com",  # tu-proyecto-id.appspot.com
    "messagingSenderId": "123456789012",  # Project Settings > General > Sender ID
    "appId": "1:123456789012:web:abcdef123456789"  # Project Settings > General > App ID
}

# INSTRUCCIONES PARA CONFIGURAR FIREBASE:
# 1. Ve a https://console.firebase.google.com/
# 2. Crea un nuevo proyecto o selecciona uno existente
# 3. Ve a "Authentication" > "Sign-in method"
# 4. Habilita "Email/Password"
# 5. Ve a "Project Settings" (el ícono de engranaje)
# 6. En la pestaña "General", copia los valores de configuración
# 7. Reemplaza los valores en firebase_config arriba
# 8. Renombra este archivo a firebase_config.py

# Inicializar Firebase
firebase = pyrebase.initialize_app(firebase_config)
auth = firebase.auth()
db = firebase.database()  # Para Firestore

class FirebaseAuth:
    @staticmethod
    def login_user(email, password):
        """Autentica un usuario con email y contraseña"""
        try:
            user = auth.sign_in_with_email_and_password(email, password)
            return {"success": True, "user": user}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    @staticmethod
    def register_user(email, password):
        """Registra un nuevo usuario"""
        try:
            user = auth.create_user_with_email_and_password(email, password)
            return {"success": True, "user": user}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    @staticmethod
    def logout_user():
        """Cierra la sesión del usuario"""
        try:
            auth.current_user = None
            session.clear()
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    @staticmethod
    def get_current_user():
        """Obtiene el usuario actual autenticado"""
        try:
            return auth.current_user
        except:
            return None

class StudentData:
    @staticmethod
    def save_student_data(user_id, student_data):
        """Guarda los datos del estudiante en Firestore"""
        try:
            db.child("students").child(user_id).set(student_data)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    @staticmethod
    def get_student_data(user_id):
        """Obtiene los datos del estudiante desde Firestore"""
        try:
            student_data = db.child("students").child(user_id).get()
            if student_data.val():
                return {"success": True, "data": student_data.val()}
            else:
                return {"success": False, "error": "No se encontraron datos del estudiante"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    @staticmethod
    def update_student_progress(user_id, tema, ejercicio_completado=False):
        """Actualiza el progreso del estudiante"""
        try:
            # Obtener datos actuales
            current_data = StudentData.get_student_data(user_id)
            if not current_data["success"]:
                return current_data
            
            data = current_data["data"]
            if "progreso" not in data:
                data["progreso"] = {}
            
            if tema not in data["progreso"]:
                data["progreso"][tema] = {
                    "ejercicios_completados": 0,
                    "ultimo_acceso": None,
                    "videos_vistos": 0
                }
            
            if ejercicio_completado:
                data["progreso"][tema]["ejercicios_completados"] += 1
            
            data["progreso"][tema]["ultimo_acceso"] = {
                "fecha": str(__import__('datetime').datetime.now()),
                "tipo": "ejercicio" if ejercicio_completado else "visualizacion"
            }
            
            return StudentData.save_student_data(user_id, data)
        except Exception as e:
            return {"success": False, "error": str(e)}
