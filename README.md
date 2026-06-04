# IA Educativa Bootcamp

Proyecto de plataforma educativa con IA para el aprendizaje de estadística.

## Características

- Autenticación de usuarios con Firebase
- Base de datos en tiempo real con Firebase Realtime Database
- Aprendizaje visual con videos de YouTube
- Ejercicios prácticos personalizados
- Seguimiento de progreso del estudiante

## Configuración

### 1. Configurar Firebase

1. Crea un proyecto en [Firebase Console](https://console.firebase.google.com/)
2. Habilita Authentication con Email/Password
3. Crea una Realtime Database
4. Descarga las credenciales de servicio (firebase-key.json)

### 2. Configurar credenciales

#### Para desarrollo local:
1. Copia `firebase-key-example.json` a `firebase-key.json`
2. Reemplaza los valores con tus credenciales reales

#### Para producción (Render.com):
1. Ve a tu proyecto en Render.com
2. En Environment Variables, agrega:
   - `FIREBASE_SERVICE_ACCOUNT`: Contenido completo del archivo firebase-key.json como JSON string
   - `FIREBASE_API_KEY`: Tu API key de Firebase

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 4. Ejecutar la aplicación

```bash
python app.py
```

## Estructura del proyecto

```
├── app.py                 # Aplicación principal Flask
├── firebase_config.py     # Configuración de Firebase
├── busquedas.py          # Búsqueda de videos de YouTube
├── temas.py              # Definición de temas educativos
├── ejercicios.py         # Generación de ejercicios
├── templates/            # Plantillas HTML
├── static/              # Archivos CSS
└── requirements.txt     # Dependencias Python
```

## Despliegue en Render.com

1. Conecta tu repositorio de GitHub a Render.com
2. Configura las variables de entorno mencionadas arriba
3. El proyecto se desplegará automáticamente

## Tecnologías utilizadas

- Python Flask
- Firebase Authentication
- Firebase Realtime Database
- YouTube Data API
- HTML/CSS/JavaScript

## Contribuir

1. Fork el proyecto
2. Crea una rama para tu feature
3. Commit tus cambios
4. Push a la rama
5. Abre un Pull Request

