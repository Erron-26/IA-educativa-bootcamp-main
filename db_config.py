import sqlite3
import json
import uuid
import os
from datetime import datetime
from flask import session
from werkzeug.security import generate_password_hash, check_password_hash

DB_PATH = os.environ.get("DB_PATH", "educativa.db")


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def initialize_db() -> None:
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


initialize_db()


class LocalAuth:

    @staticmethod
    def login_user(email: str, password: str) -> dict:
        try:
            email = email.strip().lower()
            with get_db() as conn:
                row = conn.execute(
                    "SELECT id, email, password_hash FROM users WHERE email = ?",
                    (email,)
                ).fetchone()

            if not row or not check_password_hash(row["password_hash"], password):
                return {"success": False, "error": "Correo electrónico o contraseña incorrectos"}

            return {
                "success": True,
                "user": {
                    "localId":      row["id"],
                    "email":        row["email"],
                    "idToken":      row["id"],
                    "refreshToken": row["id"],
                }
            }
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    @staticmethod
    def register_user(email: str, password: str) -> dict:
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
        try:
            session.clear()
            return {"success": True}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    @staticmethod
    def get_current_user():
        return session.get("user")


class StudentData:

    @staticmethod
    def save_student_data(user_id: str, student_data: dict) -> dict:
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
    def preguntas_ya_vistas(user_id: str, tema: str) -> set:
        result = StudentData.get_student_data(user_id)
        if not result["success"]:
            return set()
        data = result["data"]
        return set(data.get("preguntas_vistas", {}).get(tema, []))

    @staticmethod
    def registrar_preguntas_vistas(user_id: str, tema: str, ids_vistos: list) -> dict:
        result = StudentData.get_student_data(user_id)
        if not result["success"]:
            return result
        data = result["data"]
        data.setdefault("preguntas_vistas", {})
        data["preguntas_vistas"].setdefault(tema, [])
        existentes = set(data["preguntas_vistas"][tema])
        for id_v in ids_vistos:
            existentes.add(id_v)
        data["preguntas_vistas"][tema] = list(existentes)
        return StudentData.save_student_data(user_id, data)

    @staticmethod
    def save_evaluation_history(user_id: str, evaluation_data: dict) -> dict:
        try:
            result = StudentData.get_student_data(user_id)
            if not result["success"]:
                return {"success": False, "error": "No se pudieron cargar los datos del estudiante"}

            data = result["data"]
            data.setdefault("historial_evaluaciones", [])
            data["historial_evaluaciones"].append(evaluation_data)

            if len(data["historial_evaluaciones"]) > 50:
                data["historial_evaluaciones"] = data["historial_evaluaciones"][-50:]

            return StudentData.save_student_data(user_id, data)
        except Exception as exc:
            return {"success": False, "error": str(exc)}