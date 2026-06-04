import pytest
import sys
import os

# Añadir el directorio raíz al path para que pueda importar la app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app
from db_config import initialize_db

@pytest.fixture
def client():
    # Establecer la app en modo testing
    app.config['TESTING'] = True

    with app.test_client() as client:
        with app.app_context():
            # Asegurar la base de datos local
            initialize_db()
        yield client

def test_login_sql_injection(client):
    """Prueba que el login es resistente a inyección SQL básica"""
    payload = {
        'email': "admin@test.com' OR '1'='1",
        'password': "any_password"
    }
    response = client.post('/login', data=payload, follow_redirects=True)
    
    # Debería fallar, por lo tanto no redirigirá a un panel con sesión válida.
    # Comprobamos que sigue en login o da error.
    assert b"Error al iniciar" in response.data or b"Usuario no encontrado" in response.data or b"Contrase\xc3\xb1a incorrecta" in response.data

def test_protected_routes_unauthorized(client):
    """Asegura que las rutas protegidas redirigen al login si no hay sesión"""
    protected_routes = ['/', '/perfil', '/visual', '/practico']
    
    for route in protected_routes:
        response = client.get(route)
        # 302 es redirección, y debe apuntar a login
        assert response.status_code == 302
        assert '/login' in response.location

def test_xss_protection_on_register(client):
    """Prueba la protección contra inyección XSS (Cross-Site Scripting)"""
    payload = {
        'email': 'test_xss@test.com',
        'password': 'password123',
        'confirm_password': 'password123',
        'nombre': '<script>alert("XSS")</script>',
        'edad': '20',
        'nivel_educativo': 'universidad',
        'intereses': 'math'
    }
    # Intentamos registrarnos
    client.post('/register', data=payload, follow_redirects=True)
    
    # Logueamos para ver el perfil
    login_payload = {
        'email': 'test_xss@test.com',
        'password': 'password123'
    }
    client.post('/login', data=login_payload, follow_redirects=True)
    
    # Revisamos el perfil
    res_perfil = client.get('/perfil')
    
    # Jinja by default escapes HTML tags
    assert b"&lt;script&gt;alert(&#34;XSS&#34;)&lt;/script&gt;" in res_perfil.data
    assert b"<script>alert(\"XSS\")</script>" not in res_perfil.data
