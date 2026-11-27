import time
from flask import current_app

_config_cache = {}
_config_last_loaded = 0.0

def load_live_config(app, force=False):
    global _config_last_loaded, _config_cache
    now = time.time()
    if force or (now - _config_last_loaded > 60):
        from app.models import AppSetting
        try:
            settings = AppSetting.query.all()
            settings_dict = {s.key: s.value for s in settings}
            
            # First, update string keys directly (only if non-empty, preserving .env defaults)
            for key, val in settings_dict.items():
                if key in (
                    "GEMINI_API_KEY", "GEMINI_API_KEY_FREE", "GEMINI_API_KEY_PAID",
                    "GEMINI_MODEL_MCQ", "GEMINI_MODEL_ASSISTANT_PRIMARY", "GEMINI_MODEL_ASSISTANT_FALLBACK",
                    "GEMINI_MODE", "GEMINI_PAID_PROVIDER_RPM", "GEMINI_PAID_PROVIDER_RPD"
                ):
                    if val and val.strip():
                        app.config[key] = val.strip().strip('"\'')
            
            # Parse booleans
            for key, val in settings_dict.items():
                if key in ("GEMINI_BILLING_ENABLED", "GEMINI_ALLOW_CROSS_KEY_FALLBACK"):
                    app.config[key] = val.lower() in ("true", "1", "yes")

            # Parse integers
            for key, val in settings_dict.items():
                if key in (
                    "GEMINI_DAILY_LIMIT_MCQ", "GEMINI_RPM_LIMIT_MCQ",
                    "GEMINI_DAILY_LIMIT_ASSISTANT_PRIMARY", "GEMINI_DAILY_LIMIT_ASSISTANT_FALLBACK",
                    "GEMINI_RPM_LIMIT_ASSISTANT_PRIMARY", "GEMINI_RPM_LIMIT_ASSISTANT_FALLBACK",
                    "GEMINI_DAILY_LIMIT_MCQ_PAID", "GEMINI_RPM_LIMIT_MCQ_PAID",
                    "GEMINI_DAILY_LIMIT_ASSISTANT_PRIMARY_PAID", "GEMINI_RPM_LIMIT_ASSISTANT_PRIMARY_PAID",
                    "GEMINI_GLOBAL_DAILY_LIMIT_FREE", "GEMINI_GLOBAL_DAILY_LIMIT_PAID",
                    "GEMINI_GLOBAL_RPM_LIMIT_FREE", "GEMINI_GLOBAL_RPM_LIMIT_PAID"
                ):
                    try:
                        app.config[key] = int(val)
                    except (ValueError, TypeError):
                        app.config[key] = 0

            # Derive canonical GEMINI_MODE and GEMINI_BILLING_ENABLED precedence
            db_mode = settings_dict.get("GEMINI_MODE")
            if db_mode:
                app.config["GEMINI_MODE"] = db_mode.lower()
            else:
                db_billing = settings_dict.get("GEMINI_BILLING_ENABLED")
                if db_billing is not None:
                    billing_bool = db_billing.lower() in ("true", "1", "yes")
                    app.config["GEMINI_MODE"] = "paid" if billing_bool else "free"
            
            app.config["GEMINI_BILLING_ENABLED"] = (app.config.get("GEMINI_MODE") == "paid")
            _config_last_loaded = now
        except Exception as e:
            # Table might not exist yet during migrations/initialization
            pass
