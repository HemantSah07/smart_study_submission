import os
import urllib.parse
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "CHANGE-ME-IN-PRODUCTION-SET-SECRET-KEY-ENV-VAR")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Production Debug & Session Cookie Security Configuration
    FLASK_DEBUG = os.getenv("FLASK_DEBUG", "False").lower() in ("true", "1", "yes")
    DEBUG = FLASK_DEBUG
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "True").lower() in ("true", "1", "yes")
    SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
    
    # Check if configured for MySQL production or SQLite development
    DB_TYPE = os.getenv("DB_TYPE", "sqlite") # 'mysql' or 'sqlite'
    
    if DB_TYPE == "mysql":
        DB_USER = os.getenv("DB_USER", "root")
        DB_PASSWORD = os.getenv("DB_PASSWORD", "")
        DB_HOST = os.getenv("DB_HOST", "localhost")
        DB_NAME = os.getenv("DB_NAME", "smart_study")
        encoded_password = urllib.parse.quote_plus(DB_PASSWORD)
        SQLALCHEMY_DATABASE_URI = (
            f"mysql+pymysql://{DB_USER}:{encoded_password}@{DB_HOST}/{DB_NAME}"
        )
    else:
        # SQLite local development database file
        basedir = os.path.abspath(os.path.dirname(__file__))
        db_file = os.path.join(basedir, 'smart_study.db').replace('\\', '/')
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{db_file}"

    
    _raw_key = os.getenv("GEMINI_API_KEY")
    GEMINI_API_KEY = _raw_key.strip().strip('"\'') if _raw_key else None
    _raw_free = os.getenv("GEMINI_API_KEY_FREE")
    GEMINI_API_KEY_FREE = _raw_free.strip().strip('"\'') if _raw_free else None
    _raw_paid = os.getenv("GEMINI_API_KEY_PAID")
    GEMINI_API_KEY_PAID = _raw_paid.strip().strip('"\'') if _raw_paid else None
    ABSTRACT_API_KEY = os.getenv("ABSTRACT_API_KEY")
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

    # ── Gemini mode canonical settings ───────────────────────────────────────
    # Primary mode setting: 'free' or 'paid'
    # Derive from GEMINI_BILLING_ENABLED only if GEMINI_MODE is completely missing
    _legacy_billing = os.getenv("GEMINI_BILLING_ENABLED", "False").lower() in ("true", "1", "yes")
    GEMINI_MODE = os.getenv("GEMINI_MODE", "paid" if _legacy_billing else "free").lower()
    if GEMINI_MODE not in ("free", "paid"):
        GEMINI_MODE = "free"
    
    # Legacy flag for backwards compatibility
    GEMINI_BILLING_ENABLED = (GEMINI_MODE == "paid")
    GEMINI_ALLOW_CROSS_KEY_FALLBACK = os.getenv("GEMINI_ALLOW_CROSS_KEY_FALLBACK", "False").lower() in ("true", "1", "yes")

    # ── Gemini model selection per feature ────────────────────────────────────
    GEMINI_MODEL_MCQ       = os.getenv("GEMINI_MODEL_MCQ",       "gemini-3.5-flash-lite")
    GEMINI_MODEL_ASSISTANT_PRIMARY = os.getenv("GEMINI_MODEL_ASSISTANT_PRIMARY", "gemini-3.6-flash")
    GEMINI_MODEL_ASSISTANT_FALLBACK = os.getenv("GEMINI_MODEL_ASSISTANT_FALLBACK", "gemini-3.5-flash-lite")


    # ── Usage limits (daily and RPM) for FREE tier ────────────────────────────
    GEMINI_DAILY_LIMIT_MCQ       = int(os.getenv("GEMINI_DAILY_LIMIT_MCQ",       "450"))
    GEMINI_RPM_LIMIT_MCQ         = int(os.getenv("GEMINI_RPM_LIMIT_MCQ",         "15"))

    GEMINI_DAILY_LIMIT_ASSISTANT_PRIMARY  = int(os.getenv("GEMINI_DAILY_LIMIT_ASSISTANT_PRIMARY",  "18"))
    GEMINI_DAILY_LIMIT_ASSISTANT_FALLBACK = int(os.getenv("GEMINI_DAILY_LIMIT_ASSISTANT_FALLBACK", "450"))
    GEMINI_RPM_LIMIT_ASSISTANT_PRIMARY   = int(os.getenv("GEMINI_RPM_LIMIT_ASSISTANT_PRIMARY",   "5"))
    GEMINI_RPM_LIMIT_ASSISTANT_FALLBACK  = int(os.getenv("GEMINI_RPM_LIMIT_ASSISTANT_FALLBACK",  "15"))

    # ── Usage limits for PAID tier ────────────────────────────────────────────
    GEMINI_DAILY_LIMIT_MCQ_PAID       = int(os.getenv("GEMINI_DAILY_LIMIT_MCQ_PAID",       "2000"))
    GEMINI_RPM_LIMIT_MCQ_PAID         = int(os.getenv("GEMINI_RPM_LIMIT_MCQ_PAID",         "60"))
    GEMINI_DAILY_LIMIT_ASSISTANT_PRIMARY_PAID = int(os.getenv("GEMINI_DAILY_LIMIT_ASSISTANT_PRIMARY_PAID", "1000"))
    GEMINI_RPM_LIMIT_ASSISTANT_PRIMARY_PAID  = int(os.getenv("GEMINI_RPM_LIMIT_ASSISTANT_PRIMARY_PAID",  "30"))

    # ── Global request and RPM limits ──────────────────────────────────────────
    GEMINI_GLOBAL_DAILY_LIMIT_FREE    = int(os.getenv("GEMINI_GLOBAL_DAILY_LIMIT_FREE",    "450"))
    GEMINI_GLOBAL_DAILY_LIMIT_PAID    = int(os.getenv("GEMINI_GLOBAL_DAILY_LIMIT_PAID",    "5000"))
    GEMINI_GLOBAL_RPM_LIMIT_FREE      = int(os.getenv("GEMINI_GLOBAL_RPM_LIMIT_FREE",      "12"))
    GEMINI_GLOBAL_RPM_LIMIT_PAID      = int(os.getenv("GEMINI_GLOBAL_RPM_LIMIT_PAID",      "60"))

    # ── Paid provider quota reference limits (optional environment overrides) ──
    GEMINI_PAID_PROVIDER_RPM          = os.getenv("GEMINI_PAID_PROVIDER_RPM",          "Unrestricted")
    GEMINI_PAID_PROVIDER_RPD          = os.getenv("GEMINI_PAID_PROVIDER_RPD",          "Unrestricted")

    # ── Flask-Mail configuration ──────────────────────────────────────────────
    MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.getenv("MAIL_PORT", "587"))
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "True").lower() in ("true", "1", "yes")
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_USERNAME")

