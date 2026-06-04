import pytest
import time
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_login_page_load_time(client):
    """Mide el tiempo de respuesta de la página de login (debería ser < 500ms)"""
    start_time = time.time()
    response = client.get('/login')
    elapsed_time = time.time() - start_time
    
    assert response.status_code == 200
    assert elapsed_time < 0.5  # 500ms

def test_register_page_load_time(client):
    """Mide el tiempo de respuesta de la página de registro (debería ser < 500ms)"""
    start_time = time.time()
    response = client.get('/register')
    elapsed_time = time.time() - start_time
    
    assert response.status_code == 200
    assert elapsed_time < 0.5  # 500ms

def test_api_protection_speed(client):
    """
    Mide la velocidad de los redireccionamientos de protección.
    Debería ser extremadamente rápido (< 100ms)
    """
    start_time = time.time()
    response = client.get('/')
    elapsed_time = time.time() - start_time
    
    assert response.status_code == 302
    assert elapsed_time < 0.1  # 100ms
