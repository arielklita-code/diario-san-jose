from flask import Flask, request, jsonify, send_from_directory, url_for, session
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime
from werkzeug.utils import secure_filename

app = Flask(__name__)

# Configurar cookies de sesión para desarrollo
app.config['SECRET_KEY'] = 'scout_secret_key_2026'
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = False
app.config['SESSION_COOKIE_NAME'] = 'scout_session'

# Configurar CORS para permitir cookies y credenciales
CORS(app, supports_credentials=True, origins=['http://localhost:5000', 'http://127.0.0.1:5000', 'http://localhost:3000', 'http://127.0.0.1:3000', 'http://192.168.100.85:5000'])

# --- CONFIGURACIÓN ---
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
basedir = os.path.abspath(os.path.dirname(__file__))
local_sqlite_db = 'sqlite:///' + os.path.join(basedir, '..', 'instance', 'diario_scout.db')
database_url = os.getenv('DATABASE_URL')

if database_url:
    # Render suele enviar postgres://...; SQLAlchemy necesita postgresql://...
    database_url = database_url.replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = local_sqlite_db

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Crear carpeta de subidas si no existe
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# --- MODELOS DE DATOS ---
class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=True)  # Null si no puso clave
    is_admin = db.Column(db.Boolean, default=False)  # True si tiene contraseña
    fecha_registro = db.Column(db.String(100))
    
    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "is_admin": self.is_admin
        }

class UserProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    recomendaciones = db.Column(db.Text, default='')
    frases = db.Column(db.Text, default='')
    que_es_scout = db.Column(db.Text, default='')
    fecha_actualizacion = db.Column(db.String(100))
    
    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "recomendaciones": self.recomendaciones,
            "frases": self.frases,
            "que_es_scout": self.que_es_scout
        }

class Cronica(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    rama = db.Column(db.String(50), nullable=False)
    contenido = db.Column(db.Text, nullable=False)
    imagen_url = db.Column(db.String(500))
    likes = db.Column(db.Integer, default=0)
    autor = db.Column(db.String(100), default='Redacción San José')
    fecha = db.Column(db.String(100))
    user_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "titulo": self.titulo,
            "rama": self.rama,
            "contenido": self.contenido,
            "imagen_url": self.imagen_url,
            "likes": self.likes,
            "autor": self.autor,
            "fecha": self.fecha
        }

# Crear la base de datos y ajustar columnas faltantes
with app.app_context():
    db.create_all()
    # Asegurar compatibilidad con bases SQLite existentes que no tengan la columna user_id
    from sqlalchemy import text
    try:
        db.session.execute(text("ALTER TABLE cronica ADD COLUMN user_id INTEGER"))
        db.session.commit()
    except Exception:
        db.session.rollback()

# --- UTILIDADES ---
def allowed_file(filename):
    """Comprueba si un archivo tiene una extensión permitida para subir imágenes."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- RUTAS DE AUTENTICACIÓN ---

@app.route('/api/registro', methods=['POST'])
def registro():
    """Registra un nuevo usuario"""
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    # Validaciones
    if not username:
        return jsonify({"error": "El username es requerido"}), 400
    
    if Usuario.query.filter_by(username=username).first():
        return jsonify({"error": "El username ya existe"}), 409
    
    # Crear usuario
    nuevo_usuario = Usuario(
        username=username,
        is_admin=(password == 'clan123'),  # Solo admin si la contraseña es clan123
        fecha_registro=datetime.now().strftime('%d %b %Y')
    )
    
    if password == 'clan123':
        nuevo_usuario.password = generate_password_hash(password)
    
    db.session.add(nuevo_usuario)
    db.session.commit()
    
    # Crear perfil vacío
    perfil = UserProfile(
        user_id=nuevo_usuario.id,
        fecha_actualizacion=datetime.now().strftime('%d %b %Y')
    )
    db.session.add(perfil)
    db.session.commit()
    # Iniciar sesión en el backend para todos los usuarios registrados
    session['user_id'] = nuevo_usuario.id
    session['username'] = nuevo_usuario.username
    
    return jsonify({
        "message": "Usuario registrado exitosamente",
        "user": nuevo_usuario.to_dict()
    }), 201

@app.route('/api/login', methods=['POST'])
def login():
    """Autentica un usuario"""
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    usuario = Usuario.query.filter_by(username=username).first()
    
    if not usuario:
        return jsonify({"error": "Usuario no encontrado"}), 404
    
    if not usuario.is_admin:
        session.clear()
        return jsonify({"error": "Este usuario no tiene permiso de administrador"}), 403
    
    if not usuario.password or not check_password_hash(usuario.password, password):
        usuario.is_admin = False
        db.session.commit()
        session.clear()
        return jsonify({"error": "Contraseña incorrecta"}), 401
    
    session['user_id'] = usuario.id
    session['username'] = usuario.username
    
    return jsonify({
        "message": "Login exitoso",
        "user": usuario.to_dict()
    }), 200

@app.route('/api/logout', methods=['POST'])
def logout():
    """Cierra sesión del usuario"""
    session.clear()
    return jsonify({"message": "Logout exitoso"}), 200

@app.route('/api/usuario-actual', methods=['GET'])
def usuario_actual():
    """Obtiene el usuario actualmente logueado"""
    if 'user_id' not in session:
        return jsonify({"user": None}), 200
    
    usuario = Usuario.query.get(session['user_id'])
    if usuario:
        return jsonify({"user": usuario.to_dict()}), 200
    return jsonify({"user": None}), 200

@app.route('/api/usuarios', methods=['GET'])
def get_usuarios():
    """Obtiene todos los usuarios registrados"""
    usuarios = Usuario.query.all()
    return jsonify([u.to_dict() for u in usuarios]), 200

@app.route('/api/admin/usuarios', methods=['GET'])
def get_admin_usuarios():
    """Obtiene la lista completa de usuarios y sus perfiles para el administrador"""
    if 'user_id' not in session:
        return jsonify({"error": "No autenticado"}), 403

    usuario_actual = Usuario.query.get(session['user_id'])
    if not usuario_actual or not usuario_actual.is_admin:
        return jsonify({"error": "No autorizado"}), 403

    usuarios = Usuario.query.order_by(Usuario.id.asc()).all()
    resultado = []
    for usuario in usuarios:
        perfil = UserProfile.query.filter_by(user_id=usuario.id).first()
        resultado.append({
            "id": usuario.id,
            "username": usuario.username,
            "is_admin": usuario.is_admin,
            "fecha_registro": usuario.fecha_registro,
            "perfil": {
                "recomendaciones": perfil.recomendaciones if perfil else '',
                "frases": perfil.frases if perfil else '',
                "que_es_scout": perfil.que_es_scout if perfil else ''
            }
        })

    return jsonify(resultado), 200

# --- RUTAS DE PERFIL ---
# Estas rutas permiten crear y actualizar el perfil de cada usuario.

@app.route('/api/perfil/<int:user_id>', methods=['GET'])
def get_perfil(user_id):
    """Obtiene el perfil de un usuario"""
    perfil = UserProfile.query.filter_by(user_id=user_id).first()
    if perfil:
        return jsonify(perfil.to_dict()), 200
    return jsonify({"error": "Perfil no encontrado"}), 404

@app.route('/api/perfil/<int:user_id>', methods=['PUT'])
def update_perfil(user_id):
    """Actualiza el perfil de un usuario"""
    # Verificar que el usuario está editando su propio perfil
    if 'user_id' not in session or session['user_id'] != user_id:
        return jsonify({"error": "No autorizado"}), 403
    
    data = request.get_json()
    perfil = UserProfile.query.filter_by(user_id=user_id).first()
    
    if not perfil:
        return jsonify({"error": "Perfil no encontrado"}), 404
    
    perfil.recomendaciones = data.get('recomendaciones', perfil.recomendaciones)
    perfil.frases = data.get('frases', perfil.frases)
    perfil.que_es_scout = data.get('que_es_scout', perfil.que_es_scout)
    perfil.fecha_actualizacion = datetime.now().strftime('%d %b %Y')
    
    db.session.commit()
    return jsonify(perfil.to_dict()), 200

# --- RUTAS DE LA API ---


@app.route('/')
def index():
    """Ruta para servir el frontend (index.html)"""
    return send_from_directory('templates', 'index.html')

@app.route('/api/cronicas', methods=['GET'])
def get_cronicas():
    """Obtiene todas las crónicas ordenadas por ID descendente"""
    cronicas = Cronica.query.order_by(Cronica.id.desc()).all()
    return jsonify([c.to_dict() for c in cronicas])

@app.route('/api/cronicas', methods=['POST'])
def create_cronica():
    """Crea una nueva crónica con soporte para archivos"""
    # Validar autenticación
    if 'user_id' not in session:
        return jsonify({"error": "No autenticado. Debes estar registrado como admin."}), 403

    usuario = Usuario.query.get(session['user_id'])
    if not usuario or not usuario.is_admin:
        return jsonify({"error": "No tienes permiso. Solo admins pueden publicar crónicas."}), 403

    titulo = request.form.get('titulo')
    rama = request.form.get('rama')
    contenido = request.form.get('contenido')
    
    # Manejo de la imagen
    imagen_url = None
    if 'file' in request.files:
        file = request.files['file']
        if file and allowed_file(file.filename):
            filename = secure_filename(f"{datetime.now().timestamp()}_{file.filename}")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            # Genera la URL absoluta de forma dinámica (funciona en local y en producción)
            imagen_url = url_for('uploaded_file', filename=filename, _external=True)

    nueva_cronica = Cronica(
        titulo=titulo,
        rama=rama,
        contenido=contenido,
        imagen_url=imagen_url,
        fecha=datetime.now().strftime('%d %b %Y'),
        autor=usuario.username,
        user_id=usuario.id
    )
    
    db.session.add(nueva_cronica)
    db.session.commit()
    
    return jsonify(nueva_cronica.to_dict()), 201

@app.route('/api/cronicas/<int:id>/like', methods=['POST'])
def like_cronica(id):
    """Incrementa los likes de una crónica"""
    cronica = Cronica.query.get_or_404(id)
    cronica.likes += 1
    db.session.commit()
    return jsonify({"likes": cronica.likes})

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """Ruta para servir las imágenes subidas"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)