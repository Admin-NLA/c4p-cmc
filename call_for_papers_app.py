import os
import secrets
import string
import datetime

from urllib.parse import urlparse  # (se mantiene aunque ya no se use para CV/FOTO/VIDEO en esta versión)
from flask_wtf import CSRFProtect
from flask_wtf import FlaskForm
from flask import (
    Flask, request, redirect, url_for, flash,
    session, render_template_string
)
from sqlalchemy import text
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import case
from werkzeug.security import generate_password_hash, check_password_hash

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

#------ New Info -------------#
# >>> CLOUDINARY
import cloudinary
import cloudinary.uploader
import cloudinary.api
#------------------------------#

# =========================
# CONFIGURACIÓN
# =========================
app = Flask(__name__)

from werkzeug.middleware.proxy_fix import ProxyFix
app.wsgi_app = ProxyFix(
    app.wsgi_app,
    x_for=1,
    x_proto=1,
    x_host=1,
    x_port=1,
)

basedir = os.path.abspath(os.path.dirname(__file__))

DB_DIR = os.path.join(basedir, "data")
os.makedirs(DB_DIR, exist_ok=True)
DB_PATH = os.path.join(DB_DIR, "c4p_cmc.db")

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + DB_PATH
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Límite de carga (ajusta si quieres)
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100 MB
db = SQLAlchemy(app)

app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY"),
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="None",
    WTF_CSRF_SSL_STRICT=False
)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"]
)

csrf = CSRFProtect(app)

#------ New Info -------------#
# =========================
# >>> CLOUDINARY CONFIG
# =========================

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True
)
#-----------------------------#

# =========================
# ROLES / ADMINS (COMITÉ TÉCNICO)
# =========================

ADMIN_USERS = {
    "gtrujillo@noria.mx": "dNiXY2UOzS",
    "usuariotec1@noria.mx": "hKVBK56vXA",
    "usuariotec2@noria.mx": "I1FER28fFb",
    "usuariotec3@noria.mx": "pfN1q3CkuZ",
    "usuariotec4@noria.mx": "GWD9v0bXBW",
    "usuariotec5@noria.mx": "I4J3GEbkS4",
    "usuariotec6@noria.mx": "JHCx13NVqt",
    "usuariotec7@noria.mx": "XNPN5OHOup",
}

ADMIN_EMAILS = {e.lower() for e in ADMIN_USERS.keys()}

def is_admin_user(user) -> bool:
    return bool(user and user.email and user.email.lower() in ADMIN_EMAILS)

#---------------------- New Info -----------------------#
# =========================
# HELPERS
# =========================

def upload_to_cloudinary(file, folder):
    if not file or file.filename == "":
        return None

    result = cloudinary.uploader.upload(
        file,
        folder=folder,
        resource_type="auto",
        use_filename=True,
        unique_filename=True,
        overwrite=False
    )
    return result.get("secure_url")

MAX_FILE_SIZES = {
    "cv": 5 * 1024 * 1024,       # 5 MB
    "photo": 3 * 1024 * 1024,    # 3 MB
    "proposal": 10 * 1024 * 1024 # 10 MB
}

def validate_file_size(file, file_type):
    max_size = MAX_FILE_SIZES.get(file_type)
    if not max_size:
        return True
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    return size <= max_size

ALLOWED_EXTENSIONS = {
    "cv": {"pdf", "doc", "docx"},
    "photo": {"jpg", "jpeg", "png"},
    "proposal": {"pdf", "doc", "docx"},
}

def allowed_file(filename: str, file_type: str) -> bool:
    if not filename or "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in ALLOWED_EXTENSIONS.get(file_type, set())
#------------------------------------------------------------------------#

class DummyForm(FlaskForm):
    pass

# =========================
# MODELOS
# =========================

class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)

    password_hash = db.Column(db.String(255), nullable=False)
    unique_password = db.Column(db.String(128), nullable=False)

    role = db.Column(db.String(20), default="user")

    profile = db.relationship("Profile", backref="user", uselist=False)
    proposals = db.relationship("Proposal", backref="user", lazy="dynamic")


class Profile(db.Model):
    __tablename__ = "profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)

    # Datos personales
    phone = db.Column(db.String(20))
    country = db.Column(db.String(50))
    linkedin_url = db.Column(db.String(255))

    cv_url = db.Column(db.String(255))
    photo_url = db.Column(db.String(255))

    certifications = db.Column(db.Text)

    # Empresa
    company_name = db.Column(db.String(100))
    company_description = db.Column(db.Text)
    company_website = db.Column(db.String(255))
    position = db.Column(db.String(100))

    action_field = db.Column(db.String(100))
    speaker_experience = db.Column(db.Text)


class Proposal(db.Model):
    __tablename__ = "proposals"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    # IMPORTANTE:
    # Estos campos eran NOT NULL en tu BD anterior.
    # Aunque ya no se capturen en UI, los seguimos guardando con placeholders.
    title = db.Column(db.String(200), nullable=False)
    session_type = db.Column(db.String(50), nullable=False)  # BRÚJULA / SPARK (placeholder: DOCUMENTO)
    instructional_objective = db.Column(db.Text, nullable=False)
    detailed_process = db.Column(db.Text, nullable=False)
    learning_outcome = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), nullable=False)

    supporting_doc_url = db.Column(db.String(255))          # /uploads/doc/<filename>
    video_url = db.Column(db.String(255), nullable=False)   # tu BD vieja lo exige (placeholder)

    venue = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(50), default="Enviada")

    # Fecha de recepción (se crea via migración ligera si no existe en SQLite)
    received_at = db.Column(db.DateTime, default=datetime.datetime.now())
#----------------------------------------------------------------------------------------------------------------------#

#-------------------------------------------------------#
# =========================
# UTILIDADES
# =========================

def generate_random_password(length=10):
    characters = string.ascii_letters + string.digits
    return "".join(secrets.choice(characters) for _ in range(length))

def get_current_user():
    user_id = session.get("user_id")
    return db.session.get(User, user_id) if user_id else None

def is_valid_public_url(url: str) -> bool:
    """Se mantiene por compatibilidad, aunque ya no se usa."""
    if not url:
        return False
    try:
        p = urlparse(url.strip())
        return p.scheme in ("http", "https") and bool(p.netloc)
    except Exception:
        return False

def ensure_sqlite_columns():
    """
    Migración ligera (SQLite): agrega proposals.received_at si no existe.
    No borra la BD.
    """
    try:
        # Solo aplica en SQLite
        uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
        if not uri.startswith("sqlite:///"):
            return

        # Verifica columnas existentes
        rows = db.session.execute(text("PRAGMA table_info(proposals)")).fetchall()
        existing_cols = {r[1] for r in rows}  # (cid, name, type, notnull, dflt_value, pk)

        if "received_at" not in existing_cols:
            db.session.execute(text("ALTER TABLE proposals ADD COLUMN received_at DATETIME"))
            db.session.execute(text("UPDATE proposals SET received_at = COALESCE(received_at, CURRENT_TIMESTAMP)"))
            db.session.commit()
            print("✅ Migración aplicada: proposals.received_at agregado.")
    except Exception as e:
        print("⚠️ No se pudo aplicar migración ligera (received_at):", repr(e))
        try:
            db.session.rollback()
        except Exception:
            pass

# =========================
# UI / TEMPLATES
# =========================

BASE_CSS = """
<script src="https://cdn.tailwindcss.com"></script>
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
body { font-family: 'Inter', sans-serif; background-color: #DBDEE3; }
.cmc-blue { background-color: #2F4885; }
.cmc-text-blue { color: #2F4885; }
.cmc-gray { color: #818788; }
.cmc-border { border-color: #818788; }

input[type="text"], input[type="email"], input[type="tel"], input[type="url"], input[type="file"], textarea, select {
    border: 1px solid #DBDEE3;
}
</style>
"""

def render_internal_page(title, content_html):
    user = get_current_user()
    is_admin = is_admin_user(user)

    # Header:
    # - Admin: solo "Cerrar Sesión"
    # - Usuario: Mi Perfil / Mis Propuestas / Enviar Propuesta / Cerrar Sesión + avatar + nombre
    user_badge_html = ""
    nav_html = ""

    if user and not is_admin:
        photo = ""
        if user.profile and user.profile.photo_url:
            photo = f'<img src="{user.profile.photo_url}" alt="Foto" class="w-9 h-9 rounded-full object-cover border border-white/40 shadow-sm">'
        else:
            photo = '<div class="w-9 h-9 rounded-full bg-white/20 flex items-center justify-center text-white text-sm font-bold">👤</div>'

        user_badge_html = f"""
        <div class="flex items-center space-x-3 mr-3">
            {photo}
            <div class="leading-tight">
                <div class="text-sm font-semibold text-white">{user.full_name}</div>
                <div class="text-xs text-white/80">{user.email}</div>
            </div>
        </div>
        """

        nav_html = f"""
        <a href="{{{{ url_for('profile') }}}}" class="bg-[#2F4885] text-white px-4 py-2 rounded-full font-semibold hover:opacity-90 transition shadow-md">Mi Perfil</a>
        <a href="{{{{ url_for('proposals_list') }}}}" class="bg-[#2F4885] text-white px-4 py-2 rounded-full font-semibold hover:opacity-90 transition shadow-md">Mis Propuestas</a>
        <a href="{{{{ url_for('submit_proposal') }}}}" class="bg-[#2F4885] text-white px-4 py-2 rounded-full font-semibold hover:opacity-90 transition shadow-md">Enviar Propuesta</a>
        <a href="{{{{ url_for('logout') }}}}" class="bg-[#2F4885] text-white px-4 py-2 rounded-full font-semibold hover:opacity-90 transition shadow-md">Cerrar Sesión</a>
        """
    elif user and is_admin:
        nav_html = f"""
        <a href="{{{{ url_for('logout') }}}}" class="bg-[#2F4885] text-white px-4 py-2 rounded-full font-semibold hover:opacity-90 transition shadow-md">Cerrar Sesión</a>
        """

    template_html = """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{{ title }} | CMC C4P</title>
        {{ base_css|safe }}
    </head>
    <body class="bg-[#DBDEE3] min-h-screen flex flex-col">
        <header class="bg-[#2F4885] text-white shadow-lg">
            <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex justify-between items-center">
                <h1 class="text-xl font-bold">CMC C4P 2026</h1>
                <nav class="flex items-center space-x-3 md:space-x-4">
                    {{ user_badge_html|safe }}
                    """ + nav_html + """
                </nav>
            </div>
        </header>

        <main class="flex-grow py-8 px-4 sm:px-6 lg:px-8">
            <div class="max-w-4xl mx-auto bg-white p-8 rounded-xl shadow-2xl">
                <h2 class="text-3xl font-bold cmc-text-blue mb-6">{{ title }}</h2>

                {% with messages = get_flashed_messages(with_categories=true) %}
                    {% if messages %}
                        <div class="mt-4">
                            {% for category, message in messages %}
                            <div class="p-3 mb-2 rounded-lg text-sm {% if category == 'success' %}bg-green-100 text-green-800{% else %}bg-red-100 text-red-800{% endif %}" role="alert">
                                {{ message|safe }}
                            </div>
                            {% endfor %}
                        </div>
                    {% endif %}
                {% endwith %}

                {{ content_html|safe }}
            </div>
        </main>

        <footer class="bg-[#2F4885] text-white py-4 text-center text-sm mt-8">
            <p>&copy; 2026 Congreso de Mantenimiento & Confiabilidad (CMC). Para soporte: contacto@cmc-latam.com</p>
        </footer>
    </body>
    </html>
    """
    return render_template_string(
        template_html,
        title=title,
        base_css=BASE_CSS,
        content_html=content_html,
        user_badge_html=user_badge_html
    )

# =========================
# AUTH + HOME
# =========================

@app.route("/", methods=["GET"])
def index():
    user = get_current_user()
    if user:
        if is_admin_user(user):
            return redirect(url_for("admin_proposals"))
        return redirect(url_for("profile"))

    HOME_HTML = """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Convocatoria C4P 2026 | CMC</title>
        {{ base_css|safe }}
    </head>
    <body class="bg-[#DBDEE3] min-h-screen flex flex-col">
        <div class="flex-grow py-12 px-4 sm:px-6 lg:px-8">
            <div class="max-w-6xl mx-auto bg-white p-8 md:p-12 rounded-2xl shadow-2xl">
                <div class="grid md:grid-cols-2 gap-12">
                    <div>
                        <h1 class="text-4xl font-extrabold cmc-text-blue mb-2">EL LLAMADO A LOS EXPERTOS DEL MANTENIMIENTO Y LA CONFIABILIDAD</h1>
                        <h2 class="text-2xl cmc-text-blue mb-6 font-semibold">Convocatoria Anual 2026</h2>

                        <p class="text-[#818788] mb-4">
                            Es el momento de que formes parte de esta gran red de expertos y compartas tus conocimientos, experiencias y buenas prácticas con la comunidad del Congreso de Mantenimiento & Confiabilidad (CMC).
                        </p>
                        <p class="text-xl font-bold cmc-blue inline-block px-3 py-1 rounded text-white mb-6">#YoSoyCMC</p>

                        <h3 class="text-xl font-bold cmc-text-blue mb-3">¡Conoce nuestras sedes 2026!</h3>
                        <ul class="list-disc list-inside cmc-gray space-y-1 ml-4 mb-6">
                            <li>Cartagena, Colombia — 13 al 16 de julio 2026</li>
                            <li>Monterrey, México — 7 al 10 de septiembre 2026</li>
                            <li>Santiago, Chile — 9 al 12 de noviembre 2026</li>
                        </ul>

                        <h3 class="text-xl font-bold cmc-text-blue mb-4">¿Qué debes hacer para postularte?</h3>
                        <ol class="space-y-3 cmc-gray">
                            <li><span class="font-bold">1) Regístrate:</span> Completa tu registro con un correo activo.</li>
                            <li><span class="font-bold">2) Guarda tu contraseña única:</span> La plataforma la genera automáticamente.</li>
                            <li><span class="font-bold">3) Inicia sesión:</span> Entra con tu correo y contraseña.</li>
                            <li><span class="font-bold">4) Completa tu perfil:</span> Incluye tu CV y Foto (archivo).</li>
                            <li><span class="font-bold">5) Envía tu propuesta:</span> Sube tu propuesta en PDF/Word y selecciona sede(s).</li>
                        </ol>

                        <p class="text-sm cmc-gray mt-6">Soporte: contacto@cmc-latam.com</p>
                    </div>

                    <div class="bg-[#DBDEE3] p-6 rounded-xl shadow-inner flex flex-col space-y-6">

                        {% with messages = get_flashed_messages(with_categories=true) %}
                            {% if messages %}
                                <div class="mt-2">
                                    {% for category, message in messages %}
                                    <div class="p-3 mb-2 rounded-lg text-sm {% if category == 'success' %}bg-green-100 text-green-800{% else %}bg-red-100 text-red-800{% endif %}">
                                        {{ message|safe }}
                                    </div>
                                    {% endfor %}
                                </div>
                            {% endif %}
                        {% endwith %}

                        <div id="login-form-container" class="bg-white p-6 rounded-lg shadow-md">
                            <h3 class="text-2xl font-bold cmc-text-blue mb-4">Iniciar Sesión</h3>
                            <form method="POST" action="{{ url_for('login') }}" class="space-y-4">
                                <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
                                <input type="text" name="email" placeholder="Correo Electrónico" required class="w-full p-3 rounded-lg border-2 cmc-border focus:ring-2 focus:ring-blue-500">
                                <input type="password" name="password" placeholder="Contraseña Única" required class="w-full p-3 rounded-lg border-2 cmc-border focus:ring-2 focus:ring-blue-500">
                                <button type="submit" class="w-full cmc-blue text-white py-3 rounded-lg font-bold hover:opacity-90 transition shadow-md">Ingresar</button>                           
                            </form>
                        </div>

                        <div class="bg-white p-6 rounded-lg shadow-md">
                            <h3 class="text-2xl font-bold cmc-text-blue mb-4">Registro Rápido</h3>
                             <form method="POST" action="{{ url_for('register') }}" class="space-y-4">
                                <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
                                <input type="text" name="full_name" placeholder="Nombre Completo" required class="w-full p-3 rounded-lg border-2 cmc-border focus:ring-2 focus:ring-blue-500">
                                <input type="text" name="email" placeholder="Correo Electrónico" required class="w-full p-3 rounded-lg border-2 cmc-border focus:ring-2 focus:ring-blue-500">
                                <button type="submit" class="w-full bg-green-600 text-white py-3 rounded-lg font-bold hover:bg-green-700 transition shadow-md">Registrarme</button>
                            </form>
                            <p class="text-sm cmc-gray mt-4">
                                Al registrarte se generará una contraseña única y se mostrará en pantalla. Guárdala de inmediato.
                            </p>
                        </div>

                    </div>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    return render_template_string(HOME_HTML, base_css=BASE_CSS)


@app.route("/register", methods=["POST"])
def register():
    full_name = request.form.get("full_name", "").strip()
    email = request.form.get("email", "").strip().lower()

    if not full_name or not email:
        flash("Completa nombre y correo.", "error")
        return redirect(url_for("index"))

    existing = User.query.filter_by(email=email).first()
    if existing:
        flash(
            "Este correo ya se registró anteriormente. "
            "Si perdiste tu contraseña, por favor escribe a "
            "<span class='font-semibold'>contacto@cmc-latam.com</span> para solicitar recuperación.",
            "error"
        )
        return redirect(url_for("index"))

    unique_password = generate_random_password()
    hashed_password = generate_password_hash(unique_password, method="pbkdf2:sha256")

    new_user = User(
        full_name=full_name,
        email=email,
        password_hash=hashed_password,
        unique_password=unique_password
    )
    db.session.add(new_user)
    db.session.commit()

    flash_message = (
        '¡Registro exitoso! Tu contraseña única es: '
        f'<span class="font-mono font-bold text-lg bg-green-200 p-1 rounded-md text-gray-900">{unique_password}</span>. '
        "Guárdala de inmediato. Ahora puedes iniciar sesión."
    )
    session["user_id"] = new_user.id
    flash(flash_message, "success")
    return redirect(url_for("profile"))


@app.route("/login", methods=["POST"])
@limiter.limit("5 per minute")
def login():
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "").strip()

    user = User.query.filter_by(email=email).first()
    if user and check_password_hash(user.password_hash, password):
        session["user_id"] = user.id

        if is_admin_user(user):
            flash("Bienvenido administrador.", "success")
            return redirect(url_for("admin_proposals"))

        flash("Inicio de sesión exitoso.", "success")
        return redirect(url_for("profile"))

    flash("Credenciales inválidas.", "error")
    return redirect(url_for("index"))


@app.route("/logout")
def logout():
    session.pop("user_id", None)
    flash("Sesión cerrada correctamente.", "success")
    return redirect(url_for("index"))

# =========================
# PERFIL
# =========================

@app.route("/profile", methods=["GET", "POST"])
def profile():
    form = DummyForm()
    if form.validate_on_submit():
        user = get_current_user()
    if not user:
        flash("Debe iniciar sesión para acceder a su perfil.", "error")
        return redirect(url_for("index"))

    # admins no usan perfil candidato
    if is_admin_user(user):
        return redirect(url_for("admin_proposals"))

    profile_data = user.profile or Profile(user_id=user.id)

    COUNTRIES = [
        "Argentina", "Bolivia", "Chile", "Colombia", "Costa Rica", "Cuba",
        "Ecuador", "El Salvador", "España", "Guatemala", "Honduras", "México",
        "Nicaragua", "Panamá", "Paraguay", "Perú", "Puerto Rico",
        "República Dominicana", "Uruguay", "Venezuela"
    ]

    if request.method == "POST":
        if user.profile is None:
            db.session.add(profile_data)
            user.profile = profile_data

        user.full_name = request.form.get("full_name", "").strip()

        profile_data.phone = request.form.get("phone", "").strip()
        profile_data.country = request.form.get("country", "").strip()
        profile_data.linkedin_url = request.form.get("linkedin_url", "").strip()

        cv_file = request.files.get("cv_file")
        photo_file = request.files.get("photo_file")

        if cv_file and cv_file.filename:
            if not allowed_file(cv_file.filename, "cv"):
                flash("CV inválido. Formatos permitidos: PDF, DOC, DOCX.", "error")
                return redirect(url_for("profile"))
            cv_url = upload_to_cloudinary(cv_file, "c4p/profiles/cv")
            if not cv_url:
                flash("Error al subir el CV.", "error")
                return redirect(url_for("profile"))
            profile_data.cv_url = cv_url

        if photo_file and photo_file.filename:
            if not allowed_file(photo_file.filename, "photo"):
                flash("Foto inválida. Formatos permitidos: JPG, JPEG, PNG.", "error")
                return redirect(url_for("profile"))
            photo_url = upload_to_cloudinary(photo_file, "c4p/profiles/photos")
            if not photo_url:
                flash("Error al subir la foto.", "error")
                return redirect(url_for("profile"))
            profile_data.photo_url = photo_url

        profile_data.certifications = request.form.get("certifications", "").strip()

        profile_data.company_name = request.form.get("company_name", "").strip()
        profile_data.company_description = request.form.get("company_description", "").strip()
        profile_data.company_website = request.form.get("company_website", "").strip()
        profile_data.position = request.form.get("position", "").strip()

        profile_data.action_field = request.form.get("action_field", "").strip()
        profile_data.speaker_experience = request.form.get("speaker_experience", "").strip()

        if not profile_data.cv_url:
            flash("Por favor sube tu CV (obligatorio).", "error")
            return redirect(url_for("profile"))

        if not profile_data.photo_url:
            flash("Por favor sube tu Foto profesional (obligatorio).", "error")
            return redirect(url_for("profile"))
        
        #CV
        if cv_file and not validate_file_size(cv_file, "cv"):
            flash("El CV no debe exceder 5 MB.", "error")
            return redirect(url_for("profile"))

        #FOTO
        if not validate_file_size(photo_file, "photo"):
            flash("La foto no debe exceder 3 MB.", "error")
            return redirect(url_for("profile"))

        db.session.commit()
        flash("¡Perfil actualizado exitosamente!", "success")
        return redirect(url_for("submit_proposal"))

    country_options = "".join(
        f'<option value="{c}" {"selected" if c == (profile_data.country or "") else ""}>{c}</option>'
        for c in COUNTRIES
    )

    PROFILE_HTML = """
    <form method="POST" class="space-y-6" enctype="multipart/form-data">
        <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div class="col-span-full">
                <h3 class="text-xl font-semibold mb-3 cmc-text-blue border-b cmc-border pb-2">1. Datos Personales</h3>
            </div>

            <div>
                <label class="block text-sm font-medium cmc-text-blue">Nombre Completo</label>
                <input type="text" name="full_name" value="{{ user.full_name or '' }}" required class="mt-1 block w-full p-2 rounded-lg border focus:ring focus:ring-blue-200">
            </div>

            <div>
                <label class="block text-sm font-medium cmc-text-blue">Correo Electrónico (Solo lectura)</label>
                <input type="email" value="{{ user.email }}" readonly class="mt-1 block w-full p-2 rounded-lg bg-gray-100 border">
            </div>

            <div>
                <label class="block text-sm font-medium cmc-text-blue">Teléfono (Solo números)</label>
                <input type="tel" name="phone" value="{{ profile.phone or '' }}" pattern="[0-9]+" class="mt-1 block w-full p-2 rounded-lg border focus:ring focus:ring-blue-200">
            </div>

            <div>
                <label class="block text-sm font-medium cmc-text-blue">País</label>
                <select name="country" class="mt-1 block w-full p-2 rounded-lg border focus:ring focus:ring-blue-200">
                    <option value="">-- Selecciona País --</option>
                    {{ country_options|safe }}
                </select>
            </div>

            <div class="col-span-full">
                <label class="block text-sm font-medium cmc-text-blue">Enlace de LinkedIn (URL)</label>
                <input type="url" name="linkedin_url" value="{{ profile.linkedin_url or '' }}" class="mt-1 block w-full p-2 rounded-lg border focus:ring focus:ring-blue-200">
            </div>

            <div class="col-span-full">
                <label class="block text-sm font-medium cmc-text-blue">CV (obligatorio) - Subir archivo</label>
                <input type="file" name="cv_file" accept=".pdf,.doc,.docx" class="mt-1 block w-full p-2 rounded-lg border focus:ring focus:ring-blue-200">
                <p class="text-xs text-gray-600 mt-1">
                    Formatos permitidos: PDF, DOC, DOCX.
                    {% if profile.cv_url %}
                        <br>Ya cargado: <a class="cmc-text-blue font-semibold hover:underline" href="{{ profile.cv_url }}" target="_blank">Ver CV</a>
                    {% endif %}
                </p>
            </div>

            <div class="col-span-full">
                <label class="block text-sm font-medium cmc-text-blue">Foto profesional (obligatorio) - Subir archivo</label>
                <input type="file" name="photo_file" accept=".jpg,.jpeg,.png" class="mt-1 block w-full p-2 rounded-lg border focus:ring focus:ring-blue-200">
                <p class="text-xs text-gray-600 mt-1">
                    Formatos permitidos: JPG, JPEG, PNG.
                    {% if profile.photo_url %}
                        <br>Ya cargada: <a class="cmc-text-blue font-semibold hover:underline" href="{{ profile.photo_url }}" target="_blank">Ver Foto</a>
                    {% endif %}
                </p>
            </div>

            <div class="col-span-full bg-gray-50 p-4 rounded-lg border border-dashed cmc-border">
                <p class="text-sm font-medium text-gray-800 mb-1">Indicaciones para la Foto (referencia):</p>
                <ul class="list-disc list-inside text-xs cmc-gray space-y-0.5">
                    <li>Plano medio (rostro visible, buena iluminación).</li>
                    <li>Fondo neutro (blanco, beige, gris claro).</li>
                    <li>No selfies. Evitar lentes con reflejo.</li>
                    <li>Vestimenta formal, color liso.</li>
                </ul>
            </div>

            <div class="col-span-full">
                <label class="block text-sm font-medium cmc-text-blue">Certificaciones (Resumen)</label>
                <textarea name="certifications" rows="3" class="mt-1 block w-full p-2 rounded-lg border focus:ring focus:ring-blue-200">{{ profile.certifications or '' }}</textarea>
            </div>

            <div class="col-span-full mt-6">
                <h3 class="text-xl font-semibold mb-3 cmc-text-blue border-b cmc-border pb-2">2. Información Laboral</h3>
            </div>

            <div>
                <label class="block text-sm font-medium cmc-text-blue">Empresa</label>
                <input type="text" name="company_name" value="{{ profile.company_name or '' }}" class="mt-1 block w-full p-2 rounded-lg border focus:ring focus:ring-blue-200">
            </div>

            <div>
                <label class="block text-sm font-medium cmc-text-blue">Puesto</label>
                <input type="text" name="position" value="{{ profile.position or '' }}" class="mt-1 block w-full p-2 rounded-lg border focus:ring focus:ring-blue-200">
            </div>

            <div class="col-span-full">
                <label class="block text-sm font-medium cmc-text-blue">A qué se dedica la Empresa (Breve descripción)</label>
                <textarea name="company_description" rows="3" class="mt-1 block w-full p-2 rounded-lg border focus:ring focus:ring-blue-200">{{ profile.company_description or '' }}</textarea>
            </div>

            <div class="col-span-full">
                <label class="block text-sm font-medium cmc-text-blue">Sitio web de la empresa (URL)</label>
                <input type="url" name="company_website" value="{{ profile.company_website or '' }}" class="mt-1 block w-full p-2 rounded-lg border focus:ring focus:ring-blue-200">
            </div>

            <div class="col-span-full">
                <label class="block text-sm font-medium cmc-text-blue">Selecciona tu campo de acción:</label>
                <select name="action_field" class="mt-1 block w-full p-2 rounded-lg border focus:ring focus:ring-blue-200">
                    <option value="">-- Selecciona una opción --</option>
                    <option value="Consultor /Proveedor" {% if profile.action_field == 'Consultor /Proveedor' %}selected{% endif %}>Consultor /Proveedor</option>
                    <option value="Usuario" {% if profile.action_field == 'Usuario' %}selected{% endif %}>Usuario (mantenimiento / confiabilidad / activos)</option>
                </select>
            </div>

            <div class="col-span-full">
                <label class="block text-sm font-medium cmc-text-blue">Conferencias donde has participado como Ponente</label>
                <textarea name="speaker_experience" rows="3" class="mt-1 block w-full p-2 rounded-lg border focus:ring focus:ring-blue-200">{{ profile.speaker_experience or '' }}</textarea>
            </div>
        </div>

        <button type="submit" class="bg-[#2F4885] text-white py-3 px-6 rounded-lg font-bold hover:opacity-90 transition shadow-lg text-lg w-full md:w-auto">
            Guardar y Actualizar Perfil
        </button>
    </form>
    """
    rendered = render_template_string(
        PROFILE_HTML,
        user=user,
        profile=profile_data,
        country_options=country_options
    )

    return render_internal_page("Mi Perfil de Candidato", rendered)

# =========================
# ENVIAR PROPUESTA (UI: instrucciones + archivo + sedes)
# =========================

@app.route("/submit", methods=["GET", "POST"])
@limiter.limit("3 per minute")
def submit_proposal():
    user = get_current_user()
    if not user:
        flash("Debe iniciar sesión para enviar una propuesta.", "error")
        return redirect(url_for("index"))

    if is_admin_user(user):
        return redirect(url_for("admin_proposals"))

    if not user.profile:
        flash("Debe completar su perfil antes de enviar una propuesta.", "error")
        return redirect(url_for("profile"))

    VENUES = ["Colombia, Cartagena", "México, Monterrey", "Chile, Santiago"]

    # Cambia aquí el link del asistente
    ASSISTANT_URL = "https://zurl.co/YMAcE"  # ejemplo: "https://zurl.co/YMAcE"

    if request.method == "POST":
        proposal_file = request.files.get("proposal_file")
        venues = request.form.getlist("venues")

        if not proposal_file or not proposal_file.filename:
            flash("Debe cargar un archivo con su propuesta (PDF o Word).", "error")
            return redirect(url_for("submit_proposal"))

        # Usamos allowed_file("doc") pero limitamos a pdf/doc/docx
        if not allowed_file(proposal_file.filename, "proposal"):
            flash("Archivo inválido. Formatos permitidos: PDF, DOC, DOCX.", "error")
            return redirect(url_for("submit_proposal"))

        if not venues:
            flash("Debe seleccionar al menos una sede.", "error")
            return redirect(url_for("submit_proposal"))

        # Guardar archivo como doc --------------- Cambio
        doc_url = upload_to_cloudinary(proposal_file, "c4p/proposals/docs")
        if not doc_url:
            flash("Error al subir el archivo. Intenta nuevamente.", "error")
            return redirect(url_for("submit_proposal"))

        # Título automático basado en el nombre del archivo
        base_name = os.path.splitext((proposal_file.filename))[0]
        title_auto = base_name.replace("_", " ").strip() or "Propuesta en documento"

        # Placeholders para cumplir con tu BD vieja (campos NOT NULL)
        session_type_value = "DOCUMENTO"
        category_value = "Documento"
        placeholder_text = "Ver documento adjunto en 'Documento de apoyo'."
        # video_url era NOT NULL en tu esquema anterior -> guardamos doc_path como placeholder seguro.
        video_url_value = doc_url

        for venue in venues:
            new_proposal = Proposal(
                user_id=user.id,
                title=title_auto,
                session_type=session_type_value,
                instructional_objective=placeholder_text,
                detailed_process=placeholder_text,
                learning_outcome=placeholder_text,
                category=category_value,
                supporting_doc_url=doc_url, #-----Ajuste----#
                video_url=video_url_value,
                venue=venue,
                status="Enviada",
                received_at=datetime.datetime.now()
            )
            db.session.add(new_proposal)

        #PROPUESTA
        if not validate_file_size(proposal_file, "proposal"):
            flash("La propuesta no debe exceder 10 MB.", "error")
            return redirect(url_for("submit_proposal"))

        db.session.commit()
        flash(f'¡Propuesta "{title_auto}" enviada a {len(venues)} sede(s) con éxito!', "success")
        return redirect(url_for("proposals_list"))

    venue_options = "".join(
        f"""
        <label class="flex items-center space-x-2">
            <input type="checkbox" name="venues" value="{v}" class="rounded border-gray-300">
            <span>{v}</span>
        </label>
        """
        for v in VENUES
    )

    assist_link_html = (
        f'<a class="cmc-text-blue font-semibold hover:underline" href="{ASSISTANT_URL}" target="_blank">Accede al asistente aquí</a>'
        if ASSISTANT_URL else
        '<span class="cmc-gray">[Insertar link]</span>'
    )

    PROPOSAL_HTML = f"""
    <div class="space-y-6">

        <div class="bg-gray-50 p-5 rounded-lg border border-dashed cmc-border">
            <h3 class="text-xl font-semibold cmc-text-blue mb-3">Instrucciones para el envío de propuesta</h3>

            <p class="text-sm cmc-gray mb-4">
                En este espacio deberás cargar la propuesta de tu sesión para el Congreso de Mantenimiento y Confiabilidad (CMC).
            </p>

            <p class="text-sm cmc-gray mb-2">
                Para apoyarte en este proceso, ponemos a tu disposición un asistente automatizado diseñado para ayudarte a:
            </p>

            <ul class="list-disc list-inside text-sm cmc-gray space-y-1 ml-2 mb-3">
                <li>Crear tu propuesta desde cero, alineada al marco teórico de evaluación del Comité Técnico del CMC, o</li>
                <li>Evaluar y optimizar una propuesta que ya tengas desarrollada.</li>
            </ul>

            <p class="text-sm cmc-gray mb-4">
                <span class="font-semibold">👉</span> {assist_link_html}
            </p>

            <p class="text-sm cmc-gray mb-2">Al finalizar la interacción con el asistente:</p>
            <ul class="list-disc list-inside text-sm cmc-gray space-y-1 ml-2 mb-4">
                <li>Recibirás un porcentaje estimado de probabilidad de aceptación, calculado con base en el marco teórico de evaluación del CMC.</li>
                <li>Podrás descargar tu propuesta en formato PDF, ya optimizada.</li>
            </ul>

            <p class="text-sm cmc-gray mb-2">Una vez que cuentes con tu archivo final:</p>
            <ol class="list-decimal list-inside text-sm cmc-gray space-y-1 ml-2 mb-4">
                <li>Cárgalo en este espacio dentro de la plataforma.</li>
                <li>Selecciona si deseas enviar tu propuesta a una, dos o las tres sedes del CMC correspondientes al año en curso.</li>
                <li>Envía tu postulación para su revisión por el Comité Técnico.</li>
            </ol>

            <p class="text-sm cmc-gray">
                El uso del asistente es opcional, pero altamente recomendado para incrementar la alineación y claridad de tu propuesta.
            </p>
        </div>

        <form method="POST" class="space-y-6" enctype="multipart/form-data">
            <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
            <div>
                <label class="block text-sm font-medium cmc-text-blue">Archivo de Propuesta (obligatorio) *</label>
                <input type="file" name="proposal_file" accept=".pdf,.doc,.docx" required
                       class="mt-1 block w-full p-3 rounded-lg border focus:ring focus:ring-blue-200">
                <p class="text-xs text-gray-600 mt-1">
                    Formatos permitidos: PDF, DOC, DOCX.
                </p>
            </div>

            <div>
                <label class="block text-sm font-medium cmc-text-blue mb-2">Selecciona la(s) Sede(s) *</label>
                <div class="space-y-2">{venue_options}</div>
            </div>

            <button type="submit"
                class="bg-[#2F4885] text-white py-4 px-8 rounded-lg font-bold text-lg hover:opacity-90 transition shadow-lg mt-8 w-full">
                Enviar Propuesta
            </button>
        </form>
    </div>
    """

    return render_internal_page("Enviar Propuesta (Call for Papers)", PROPOSAL_HTML)

# =========================
# LISTA DE PROPUESTAS
# =========================

@app.route("/proposals")
def proposals_list():
    user = get_current_user()
    if not user:
        flash("Debe iniciar sesión para ver sus propuestas.", "error")
        return redirect(url_for("index"))

    if is_admin_user(user):
        return redirect(url_for("admin_proposals"))

    proposals = user.proposals.order_by(Proposal.id.desc()).all()

    STATUS_COLORS = {
        "Enviada": "bg-blue-100 text-blue-800",
        "En revisión": "bg-yellow-100 text-yellow-800",
        "Aceptada": "bg-green-100 text-green-800",
        "Rechazada": "bg-red-100 text-red-800",
    }

    rows = ""
    if proposals:
        for p in proposals:
            color_class = STATUS_COLORS.get(p.status, "bg-gray-100 text-gray-800")

            # Título como link al archivo, si existe
            if p.supporting_doc_url:
                title_display = f'<a class="cmc-text-blue font-semibold hover:underline" href="{p.supporting_doc_url}" target="_blank">{p.title}</a>'
            else:
                title_display = f'{p.title}'

            rows += f"""
            <tr class="border-b hover:bg-gray-50 transition duration-150">
                <td class="px-6 py-4 font-semibold cmc-text-blue">{title_display}</td>
                <td class="px-6 py-4">{p.session_type} ({p.category})</td>
                <td class="px-6 py-4">{p.venue}</td>
                <td class="px-6 py-4">
                    <span class="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium {color_class}">
                        {p.status}
                    </span>
                </td>
            </tr>
            """
    else:
        rows = """
        <tr>
            <td colspan="4" class="px-6 py-8 text-center cmc-gray">
                Aún no has enviado ninguna propuesta.
                <a href="/submit" class="cmc-text-blue font-semibold hover:underline block mt-2">¡Comienza ahora!</a>
            </td>
        </tr>
        """

    HTML = f"""
    <div class="overflow-x-auto shadow-md rounded-lg">
        <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-[#2F4885] text-white">
                <tr>
                    <th class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">Título</th>
                    <th class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">Tipo / Categoría</th>
                    <th class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">Sede</th>
                    <th class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">Estatus</th>
                </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
                {rows}
            </tbody>
        </table>
    </div>

    <div class="mt-6">
        <h3 class="text-lg font-semibold cmc-text-blue mb-2">Posibles Estatus:</h3>
        <ul class="list-disc list-inside cmc-gray space-y-1 ml-4 text-sm">
            <li><span class="font-semibold">Enviada:</span> Propuesta recibida correctamente.</li>
            <li><span class="font-semibold">En revisión:</span> El Comité Técnico está evaluando el contenido.</li>
            <li><span class="font-semibold">Aceptada:</span> Propuesta seleccionada. Se contactará para continuar.</li>
            <li><span class="font-semibold">Rechazada:</span> Propuesta no seleccionada en esta ocasión.</li>
        </ul>
    </div>
    """
    return render_internal_page("Mis Propuestas", HTML)

# =========================
# ADMIN - TABLA PROPUESTAS + CAMBIO ESTATUS
# =========================

@app.route("/admin/proposals", methods=["GET", "POST"])
def admin_proposals():
    user = get_current_user()
    if not user:
        flash("Debe iniciar sesión.", "error")
        return redirect(url_for("index"))
    if not is_admin_user(user):
        flash("Acceso no autorizado.", "error")
        return redirect(url_for("profile"))

    if request.method == "POST":
        proposal_id = request.form.get("proposal_id", "").strip()
        new_status = request.form.get("new_status", "").strip()

        if proposal_id and new_status:
            p = db.session.get(Proposal, int(proposal_id))
            if p:
                p.status = new_status
                db.session.commit()
                flash("Estatus actualizado correctamente.", "success")
            else:
                flash("Propuesta no encontrada.", "error")
        else:
            flash("Acción inválida.", "error")

        return redirect(url_for("admin_proposals"))

    # Orden por sede: Colombia -> México -> Chile
    venue_order = case(
        (Proposal.venue == "Colombia, Cartagena", 1),
        (Proposal.venue == "México, Monterrey", 2),
        (Proposal.venue == "Chile, Santiago", 3),
        else_=99
    )

    proposals = (
        Proposal.query
        .join(User, User.id == Proposal.user_id)
        .order_by(venue_order.asc(), Proposal.received_at.desc(), Proposal.id.desc())
        .all()
    )

    STATUS_OPTIONS = ["Enviada", "En revisión", "Aceptada", "Rechazada"]

    rows = ""
    last_venue = None
    for p in proposals:
        # separador entre sedes (línea de contorno)
        if last_venue is not None and p.venue != last_venue:
            rows += """
            <tr>
                <td colspan="7" class="px-0 py-0">
                    <div class="border-t-4 border-[#2F4885] my-1"></div>
                </td>
            </tr>
            """
        last_venue = p.venue

        doc_link = '<span class="cmc-gray">—</span>'
        if p.supporting_doc_url:
            doc_link = f'<a class="cmc-text-blue font-semibold hover:underline" href="{p.supporting_doc_url}" target="_blank">Ver archivo</a>'

        # Nombre candidato clicable al perfil admin
        candidate_name = p.user.full_name if p.user else f"User {p.user_id}"
        candidate_link = f'<a class="cmc-text-blue font-semibold hover:underline" href="{url_for("admin_candidate_profile", user_id=p.user_id)}">{candidate_name}</a>'

        received = "—"
        try:
            if p.received_at:
                received = p.received_at.strftime("%Y-%m-%d %H:%M")
        except Exception:
            received = "—"

        options_html = "".join(
            f'<option value="{s}" {"selected" if s == p.status else ""}>{s}</option>'
            for s in STATUS_OPTIONS
        )

        rows += f"""
        <tr class="border-b hover:bg-gray-50 transition duration-150">
            <td class="px-6 py-4">{p.id}</td>
            <td class="px-6 py-4">{candidate_link}<div class="text-xs cmc-gray">{p.user.email if p.user else ''}</div></td>
            <td class="px-6 py-4">{p.venue}</td>
            <td class="px-6 py-4">{received}</td>
            <td class="px-6 py-4">{doc_link}</td>
            <td class="px-6 py-4">
                <form method="POST" class="flex items-center space-x-2">
                <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
                    <input type="hidden" name="proposal_id" value="{p.id}">
                    <select name="new_status" class="p-2 rounded-lg border">
                        {options_html}
                    </select>
                    <button type="submit" class="bg-[#2F4885] text-white px-3 py-2 rounded-lg font-semibold hover:opacity-90 transition">
                        Guardar
                    </button>
                </form>
            </td>
            <td class="px-6 py-4">{p.status}</td>
        </tr>
        """

    HTML = f"""
    <div class="flex items-center justify-between mb-6">
        <h3 class="text-xl font-semibold cmc-text-blue">Propuestas recibidas</h3>
        <div class="space-x-2">
            <a href="{url_for('admin_passwords')}" class="bg-white border border-[#2F4885] text-[#2F4885] px-4 py-2 rounded-lg font-semibold hover:bg-gray-50 transition">Contraseñas</a>
        </div>
    </div>

    <div class="overflow-x-auto shadow-md rounded-lg">
        <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-[#2F4885] text-white">
                <tr>
                    <th class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">ID</th>
                    <th class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">Candidato</th>
                    <th class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">Sede</th>
                    <th class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">Fecha recepción</th>
                    <th class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">Archivo</th>
                    <th class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">Cambiar estatus</th>
                    <th class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">Estatus actual</th>
                </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
                {rows or '<tr><td colspan="7" class="px-6 py-8 text-center cmc-gray">Sin propuestas.</td></tr>'}
            </tbody>
        </table>
    </div>
    """
    return render_internal_page("Admin | Propuestas", HTML)

# =========================
# ADMIN - PERFIL DEL CANDIDATO (LECTURA)
# =========================

@app.route("/admin/candidate/<int:user_id>")
def admin_candidate_profile(user_id):
    user = get_current_user()
    if not user:
        flash("Debe iniciar sesión.", "error")
        return redirect(url_for("index"))
    if not is_admin_user(user):
        flash("Acceso no autorizado.", "error")
        return redirect(url_for("profile"))

    cand = db.session.get(User, user_id)
    if not cand:
        flash("Candidato no encontrado.", "error")
        return redirect(url_for("admin_proposals"))

    prof = cand.profile

    cv_link = '<span class="cmc-gray">—</span>'
    if prof and prof.cv_url:
        cv_link = f'<a class="cmc-text-blue font-semibold hover:underline" href="{prof.cv_url}" target="_blank">Ver CV</a>'

    photo_link = '<span class="cmc-gray">—</span>'
    if prof and prof.photo_url:
        photo_link = f'<a class="cmc-text-blue font-semibold hover:underline" href="{prof.photo_url}" target="_blank">Ver Foto</a>'

    linkedin_link = '<span class="cmc-gray">—</span>'
    if prof and prof.linkedin_url:
        linkedin_link = f'<a class="cmc-text-blue font-semibold hover:underline" href="{prof.linkedin_url}" target="_blank">{prof.linkedin_url}</a>'

    # Sitio web Empresa como link
    company_site = '<span class="cmc-gray">—</span>'
    if prof and prof.company_website:
        company_site = (
            f'<a class="cmc-text-blue font-semibold hover:underline" '
            f'href="{prof.company_website}" target="_blank">{prof.company_website}</a>'
        )

    HTML = f"""
    <div class="space-y-6">
        <div class="bg-gray-50 p-5 rounded-lg border border-dashed cmc-border">
            <div class="flex items-center justify-between">
                <div>
                    <h3 class="text-xl font-semibold cmc-text-blue">Perfil del candidato</h3>
                    <p class="text-sm cmc-gray">Vista de lectura para revisión interna.</p>
                </div>
                <div>
                    <a href="{url_for('admin_proposals')}" class="bg-[#2F4885] text-white px-4 py-2 rounded-lg font-semibold hover:opacity-90 transition">Volver a Propuestas</a>
                </div>
            </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div class="md:col-span-2">
                <div class="text-lg font-semibold cmc-text-blue">{cand.full_name}</div>
                <div class="text-sm cmc-gray">{cand.email}</div>
            </div>

            <div><span class="font-semibold">Teléfono:</span><br><span class="cmc-gray">{(prof.phone if prof and prof.phone else '—')}</span></div>
            <div><span class="font-semibold">País:</span><br><span class="cmc-gray">{(prof.country if prof and prof.country else '—')}</span></div>

            <div class="md:col-span-2"><span class="font-semibold">LinkedIn:</span><br>{linkedin_link}</div>

            <div><span class="font-semibold">CV:</span><br>{cv_link}</div>
            <div><span class="font-semibold">Foto:</span><br>{photo_link}</div>

            <div class="md:col-span-2"><span class="font-semibold">Certificaciones:</span><br><span class="cmc-gray whitespace-pre-line">{(prof.certifications if prof and prof.certifications else '—')}</span></div>

            <div><span class="font-semibold">Empresa:</span><br><span class="cmc-gray">{(prof.company_name if prof and prof.company_name else '—')}</span></div>
            <div><span class="font-semibold">Puesto:</span><br><span class="cmc-gray">{(prof.position if prof and prof.position else '—')}</span></div>

            <div class="md:col-span-2"><span class="font-semibold">Descripción empresa:</span><br><span class="cmc-gray whitespace-pre-line">{(prof.company_description if prof and prof.company_description else '—')}</span></div>

            <div class="md:col-span-2"><span class="font-semibold">Sitio web Empresa:</span><br>{company_site}</div>

            <div class="md:col-span-2"><span class="font-semibold">Campo de acción:</span><br><span class="cmc-gray">{(prof.action_field if prof and prof.action_field else '—')}</span></div>

            <div class="md:col-span-2"><span class="font-semibold">Experiencia como ponente:</span><br><span class="cmc-gray whitespace-pre-line">{(prof.speaker_experience if prof and prof.speaker_experience else '—')}</span></div>
        </div>
    </div>
    """
    return render_internal_page("Admin | Perfil de Candidato", HTML)

# =========================
# ADMIN - CONTRASEÑAS (BUSCADOR)
# =========================

@app.route("/admin/passwords", methods=["GET"])
def admin_passwords():
    user = get_current_user()
    if not user:
        flash("Debe iniciar sesión.", "error")
        return redirect(url_for("index"))
    if not is_admin_user(user):
        flash("Acceso no autorizado.", "error")
        return redirect(url_for("profile"))

    q = (request.args.get("q") or "").strip().lower()

    query = User.query.filter(User.email.notin_(list(ADMIN_EMAILS)))
    if q:
        like = f"%{q}%"
        query = query.filter((User.email.ilike(like)) | (User.full_name.ilike(like)))

    users = query.order_by(User.id.desc()).all()

    rows = ""
    for u in users:
        rows += f"""
        <tr class="border-b hover:bg-gray-50 transition duration-150">
            <td class="px-6 py-4">{u.full_name}</td>
            <td class="px-6 py-4">{u.email}</td>
            <td class="px-6 py-4 font-mono">{u.unique_password}</td>
        </tr>
        """

    HTML = f"""
    <div class="flex items-center justify-between mb-4">
        <h3 class="text-xl font-semibold cmc-text-blue">Contraseñas</h3>
        <a href="{url_for('admin_proposals')}" class="bg-[#2F4885] text-white px-4 py-2 rounded-lg font-semibold hover:opacity-90 transition">Volver a Propuestas</a>
    </div>

    <form method="GET" class="mb-6">
        <label class="block text-sm font-medium cmc-text-blue mb-2">Buscador (nombre o correo)</label>
        <div class="flex space-x-2">
            <input type="text" name="q" value="{q}" placeholder="Ej. maria@empresa.com o María Pérez"
                   class="w-full p-3 rounded-lg border focus:ring focus:ring-blue-200">
            <button type="submit" class="bg-[#2F4885] text-white px-6 py-3 rounded-lg font-bold hover:opacity-90 transition">
                Buscar
            </button>
        </div>
        <p class="text-xs cmc-gray mt-2">Esta sección es solo para soporte interno y recuperación manual.</p>
    </form>

    <div class="overflow-x-auto shadow-md rounded-lg">
        <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-[#2F4885] text-white">
                <tr>
                    <th class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">Nombre</th>
                    <th class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">Correo</th>
                    <th class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">Contraseña</th>
                </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
                {rows or '<tr><td colspan="3" class="px-6 py-8 text-center cmc-gray">Sin resultados.</td></tr>'}
            </tbody>
        </table>
    </div>
    """
    return render_internal_page("Admin | Contraseñas", HTML)

# =========================
# BOOTSTRAP ADMINS (ADMIN + COMITÉ TÉCNICO)
# =========================

def bootstrap_admins():
    for email, pwd in ADMIN_USERS.items():
        email_l = email.lower()
        u = User.query.filter_by(email=email_l).first()
        hashed = generate_password_hash(pwd, method="pbkdf2:sha256")

        if u:
            u.password_hash = hashed
            u.unique_password = pwd
            u.role = "admin"
        else:
            u = User(
                full_name="Administrador Comité Técnico",
                email=email_l,
                password_hash=hashed,
                unique_password=pwd,
                role="admin"
            )
            db.session.add(u)

    db.session.commit()

with app.app_context():
    db.create_all()
    ensure_sqlite_columns()
    bootstrap_admins()

    inspector = db.inspect(db.engine)
    print("📦 Tablas existentes:", inspector.get_table_names())

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)