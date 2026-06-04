"""
db_config.py
============
Reemplazo COMPLETO de firebase_config.py usando SQLite + werkzeug.

- Sin credenciales externas: no requiere Firebase key ni service account.
- API 100% compatible: FirebaseAuth y StudentData mantienen los mismos
  métodos y estructura de retorno que el módulo original.
- Solo una línea cambia en app.py:
    ANTES:  from firebase_config import FirebaseAuth, StudentData
    AHORA:  from db_config      import FirebaseAuth, StudentData
"""

import sqlite3
import json
import uuid
import os
from datetime import datetime
from flask import session
from werkzeug.security import generate_password_hash, check_password_hash

# ─────────────────────────────────────────────
# Configuración de la base de datos
# ─────────────────────────────────────────────

# En producción (Render) se recomienda apuntar a un disco persistente:
#   DB_PATH=/data/educativa.db
# En desarrollo local usará educativa.db en el directorio del proyecto.
DB_PATH = os.environ.get("DB_PATH", "educativa.db")


def get_db() -> sqlite3.Connection:
    """Retorna una conexión SQLite con row_factory configurado."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # WAL mejora la concurrencia en lecturas simultáneas
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def initialize_db() -> None:
    """
    Crea las tablas si no existen.
    Se invoca automáticamente al importar este módulo.

    Esquema:
        users    → reemplaza Firebase Authentication
        students → reemplaza Firebase Realtime Database (students/{uid})
    """
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id           TEXT PRIMARY KEY,
                email        TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at   TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS students (
                user_id    TEXT PRIMARY KEY,
                data       TEXT NOT NULL DEFAULT '{}',
                updated_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
        """)
        conn.commit()
    print(f"[db_config] Base de datos SQLite inicializada en: {DB_PATH}")


# Inicializar al importar (igual que el módulo original con Firebase)
initialize_db()


# ─────────────────────────────────────────────
# FirebaseAuth  (reemplaza firebase_admin.auth)
# ─────────────────────────────────────────────

class FirebaseAuth:
    """
    Autenticación local con email + contraseña.
    Todos los métodos mantienen la misma firma y estructura de retorno
    que el módulo firebase_config.py original.
    """

    @staticmethod
    def login_user(email: str, password: str) -> dict:
        """
        Autentica un usuario con email y contraseña.

        Retorna:
            {"success": True,  "user": {"localId": ..., "email": ...,
                                        "idToken": ..., "refreshToken": ...}}
            {"success": False, "error": "<mensaje>"}
        """
        try:
            email = email.strip().lower()
            with get_db() as conn:
                row = conn.execute(
                    "SELECT id, email, password_hash FROM users WHERE email = ?",
                    (email,)
                ).fetchone()

            if not row:
                return {"success": False, "error": "Usuario no encontrado"}

            if not check_password_hash(row["password_hash"], password):
                return {"success": False, "error": "Contraseña incorrecta"}

            # Retorna la misma estructura que Firebase para que app.py no cambie
            return {
                "success": True,
                "user": {
                    "localId":      row["id"],
                    "email":        row["email"],
                    # idToken y refreshToken se mantienen por compatibilidad
                    # (app.py no los usa directamente, solo localId y email)
                    "idToken":      row["id"],
                    "refreshToken": row["id"],
                }
            }
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    @staticmethod
    def register_user(email: str, password: str) -> dict:
        """
        Registra un nuevo usuario.

        Retorna:
            {"success": True,  "user": {"localId": ..., "email": ...}}
            {"success": False, "error": "<mensaje>"}
        """
        try:
            user_id       = str(uuid.uuid4())
            email         = email.strip().lower()
            password_hash = generate_password_hash(password)

            with get_db() as conn:
                try:
                    conn.execute(
                        "INSERT INTO users (id, email, password_hash) VALUES (?, ?, ?)",
                        (user_id, email, password_hash)
                    )
                    conn.commit()
                except sqlite3.IntegrityError:
                    return {"success": False, "error": "El email ya está registrado"}

            return {
                "success": True,
                "user": {
                    "localId": user_id,
                    "email":   email,
                }
            }
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    @staticmethod
    def logout_user() -> dict:
        """Cierra la sesión limpiando la sesión de Flask."""
        try:
            session.clear()
            return {"success": True}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    @staticmethod
    def get_current_user():
        """Retorna el user_id del usuario activo (desde la sesión de Flask)."""
        return session.get("user")


# ─────────────────────────────────────────────
# StudentData  (reemplaza Firebase Realtime DB)
# ─────────────────────────────────────────────

class StudentData:
    """
    Almacenamiento de datos de estudiantes en SQLite.
    El campo `data` es un JSON blob que replica la estructura
    que Firebase guardaba en students/{user_id}.
    """

    @staticmethod
    def save_student_data(user_id: str, student_data: dict) -> dict:
        """
        Guarda (o reemplaza) los datos del estudiante.

        Retorna:
            {"success": True}
            {"success": False, "error": "<mensaje>"}
        """
        try:
            data_json = json.dumps(student_data, ensure_ascii=False)
            with get_db() as conn:
                conn.execute(
                    """
                    INSERT INTO students (user_id, data, updated_at)
                    VALUES (?, ?, datetime('now'))
                    ON CONFLICT(user_id) DO UPDATE SET
                        data       = excluded.data,
                        updated_at = excluded.updated_at
                    """,
                    (user_id, data_json)
                )
                conn.commit()
            return {"success": True}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    @staticmethod
    def get_student_data(user_id: str) -> dict:
        """
        Carga los datos del estudiante.

        Retorna:
            {"success": True,  "data": {...}}
            {"success": False, "error": "<mensaje>"}
        """
        try:
            with get_db() as conn:
                row = conn.execute(
                    "SELECT data FROM students WHERE user_id = ?",
                    (user_id,)
                ).fetchone()

            if row:
                return {"success": True, "data": json.loads(row["data"])}
            return {"success": False, "error": "No se encontraron datos del estudiante"}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    @staticmethod
    def update_student_progress(
        user_id: str,
        tema: str,
        ejercicio_completado: bool = False
    ) -> dict:
        """
        Actualiza el progreso del estudiante para un tema específico.
        Lógica idéntica al módulo original.
        """
        try:
            result = StudentData.get_student_data(user_id)
            if not result["success"]:
                return result

            data = result["data"]
            data.setdefault("progreso", {})

            if tema not in data["progreso"]:
                data["progreso"][tema] = {
                    "ejercicios_completados": 0,
                    "ultimo_acceso":          None,
                    "videos_vistos":          0,
                }

            if ejercicio_completado:
                data["progreso"][tema]["ejercicios_completados"] += 1

            data["progreso"][tema]["ultimo_acceso"] = {
                "fecha": datetime.now().isoformat(),
                "tipo":  "ejercicio" if ejercicio_completado else "visualizacion",
            }

            return StudentData.save_student_data(user_id, data)
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    @staticmethod
    def save_evaluation_history(user_id: str, evaluation_data: dict) -> dict:
        """
        Agrega una evaluación al historial del estudiante.
        Mantiene un máximo de 50 evaluaciones (igual que el original).
        """
        try:
            result = StudentData.get_student_data(user_id)
            if not result["success"]:
                return {"success": False, "error": "No se pudieron cargar los datos del estudiante"}

            data = result["data"]
            data.setdefault("historial_evaluaciones", [])
            data["historial_evaluaciones"].append(evaluation_data)

            # Conservar solo las últimas 50
            if len(data["historial_evaluaciones"]) > 50:
                data["historial_evaluaciones"] = data["historial_evaluaciones"][-50:]

            return StudentData.save_student_data(user_id, data)
        except Exception as exc:
            return {"success": False, "error": str(exc)}