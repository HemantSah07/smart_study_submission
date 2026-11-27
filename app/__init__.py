from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from flask_mail import Mail
from config import Config

db            = SQLAlchemy()
bcrypt        = Bcrypt()
login_manager = LoginManager()
mail          = Mail()
login_manager.login_view             = "auth.login"
login_manager.login_message_category = "warning"

# Destructive database safety block to protect production database during test executions
original_drop_all = db.drop_all

def safe_drop_all(*args, **kwargs):
    from flask import current_app
    try:
        if current_app:
            testing = current_app.config.get('TESTING', False)
            uri = current_app.config.get('SQLALCHEMY_DATABASE_URI', '')
            if testing:
                if 'smart_study.db' in uri and not ('test' in uri or 'memory' in uri):
                    raise RuntimeError(
                        "SAFETY BLOCK: Automated tests are NOT allowed to perform destructive "
                        "operations (like db.drop_all) on the production database 'smart_study.db'!"
                    )
    except RuntimeError as e:
        if "SAFETY BLOCK" in str(e):
            raise e
    original_drop_all(*args, **kwargs)

db.drop_all = safe_drop_all

def create_app(config_class=None):
    app = Flask(__name__)
    if config_class:
        app.config.from_object(config_class)
    else:
        app.config.from_object(Config)

    if app.config.get('TESTING'):
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'

    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)

    with app.app_context():
        from app.live_config import load_live_config
        load_live_config(app, force=True)
        try:
            db.create_all()
        except Exception as err:
            print(f"[DB Setup] db.create_all() warning: {err}")
        try:
            from sqlalchemy import text
            db.session.execute(text("ALTER TABLE uploaded_materials ADD COLUMN relative_folder_path VARCHAR(500)"))
            db.session.commit()
        except Exception:
            db.session.rollback()

        # Guarantee Primary Super Admin account role integrity
        try:
            from app.models import User, SUPER_ADMIN_EMAIL
            super_admin_user = User.query.filter(db.func.lower(User.email) == SUPER_ADMIN_EMAIL.lower()).first()
            if super_admin_user and super_admin_user.role != 'super_admin':
                super_admin_user.role = 'super_admin'
                super_admin_user.is_active = True
                db.session.commit()
                print(f"[DB Setup] Primary Super Admin account ({SUPER_ADMIN_EMAIL}) role synced to 'super_admin'.")
        except Exception as err:
            db.session.rollback()
            print(f"[DB Setup] Super admin sync warning: {err}")

    @app.before_request
    def check_live_config():
        from app.live_config import load_live_config
        load_live_config(app)

    @app.after_request
    def set_security_headers(response):
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        return response

    @app.errorhandler(403)
    def forbidden_error(e):
        from flask import render_template
        return render_template("errors/403.html"), 403

    from app.routes.auth    import auth_bp
    from app.routes.student import student_bp
    from app.routes.admin   import admin_bp
    from app.routes.main    import main_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(student_bp, url_prefix="/student")
    app.register_blueprint(admin_bp,   url_prefix="/admin")

    return app