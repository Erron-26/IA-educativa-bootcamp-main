import random

def generar_ejercicio_aleatorio(tema):
    ejemplos = {
        "Probabilidad básica": {
            "pregunta": "Si lanzas un dado, ¿cuál es la probabilidad de obtener un número par?",
            "opciones": ["1/2", "1/3", "2/3", "1/6"],
            "respuesta": "1/2",
            "pista": "Recuerda que un dado tiene 3 números pares (2, 4 y 6) de 6 posibles.",
            "guia": "Para resolver, divide el número de resultados favorables (3) entre el total de posibles (6)."
        },
        "Media aritmética y ponderada": {
            "pregunta": "¿Cuál es la media de los números 2, 4, 6, 8, 10?",
            "opciones": ["5", "6", "8", "4"],
            "respuesta": "6",
            "pista": "Suma todos los valores y divide por la cantidad de datos.",
            "guia": "Media = (2+4+6+8+10)/5 = 30/5 = 6"
        },
        "Varianza y desviación estándar": {
            "pregunta": "Si los datos son 2, 4 y 6, ¿cuál es su varianza?",
            "opciones": ["2.67", "4", "8", "1.5"],
            "respuesta": "2.67",
            "pista": "Calcula primero la media, luego la suma de los cuadrados de las desviaciones dividida entre n.",
            "guia": "Media=4. Varianza=((2−4)²+(4−4)²+(6−4)²)/3=8/3=2.67"
        },
    }

    if tema not in ejemplos:
        tema = random.choice(list(ejemplos.keys()))

    return ejemplos[tema]
