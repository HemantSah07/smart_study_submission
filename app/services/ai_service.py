import hashlib
import json
import logging
import os
import re
import time
from datetime import date, datetime
from threading import Lock

from flask import current_app
from app import db
from app.models import AICache, DailyAPIUsage, Subject, LearningMaterial, Topic, Chapter, Flashcard

logger = logging.getLogger(__name__)

class AIServiceError(Exception):
    """Base exception for all AI Service errors."""
    pass

class QuotaExceededError(AIServiceError):
    """Raised when a daily quota (global or feature) is exceeded."""
    def __init__(self, feature: str = "feature"):
        self.feature = feature
        super().__init__("AI usage limit has been reached temporarily. Please try again later.")

class RateLimitError(AIServiceError):
    """Raised when an RPM or temporary rate limit is exceeded."""
    def __init__(self, detail: str = ""):
        message = "AI service is temporarily busy. Please try again in a moment."
        if detail:
            message += f" ({detail})"
        super().__init__(message)

class ConfigurationError(AIServiceError):
    """Raised when the API key is missing, invalid, or billing/configuration is broken."""
    def __init__(self, detail: str = ""):
        message = "AI service configuration requires attention."
        if detail:
            message += f" ({detail})"
        super().__init__(message)

class SlidingWindowLimiter:
    def __init__(self):
        self._calls = []  # list of float timestamps
        self._lock = Lock()

    def record_call(self):
        now = time.time()
        with self._lock:
            self._calls.append(now)
            self._clean(now)

    def _clean(self, now):
        cutoff = now - 60.0
        self._calls = [t for t in self._calls if t > cutoff]

    def get_count(self) -> int:
        now = time.time()
        with self._lock:
            self._clean(now)
            return len(self._calls)


# ── Feature identifiers ────────────────────────────────────────────────────────
FEATURE_MCQ       = "mcq"        # Assessment MCQ generation
FEATURE_ASSISTANT = "assistant"  # AI tutoring chat


# ── Metadata reference for free-tier provider limits ──────────────────────────
PROVIDER_QUOTA_METADATA = {
    "free": {
        "gemini-3.6-flash": {"rpm": 15, "rpd": 500},
        "gemini-3.5-flash": {"rpm": 15, "rpd": 500},
        "gemini-3.5-flash-lite": {"rpm": 15, "rpd": 500},
        "gemini-3.1-flash-lite": {"rpm": 15, "rpd": 500},
    }
}



class CentralQuotaManager:
    def __init__(self):
        self._global_limiter = SlidingWindowLimiter()
        self._feature_limiters = {
            FEATURE_MCQ: SlidingWindowLimiter(),
            FEATURE_ASSISTANT: SlidingWindowLimiter()
        }

    def check_rpm_and_quota(self, feature: str, model_name: str):
        """
        Check global and per-feature rate limits (RPM) and daily quotas.
        Raises QuotaExceededError or RateLimitError on violation.
        """
        mode = current_app.config.get("GEMINI_MODE", "free").lower()
        billing_on = (mode == "paid")

        # 1. Global Daily Quota Check (Daily Safety Budget)
        if billing_on:
            global_daily_limit = current_app.config.get("GEMINI_GLOBAL_DAILY_LIMIT_PAID", 5000)
        else:
            global_daily_limit = current_app.config.get("GEMINI_GLOBAL_DAILY_LIMIT_FREE", 450)

        today_global_usage = self.get_today_global_usage()
        if today_global_usage >= global_daily_limit:
            logger.warning(
                "Global daily safety budget exhausted: %d/%d calls used today (mode: %s).",
                today_global_usage, global_daily_limit, mode
            )
            raise QuotaExceededError("global")

        # 2. Feature Daily Quota Check
        feature_limit = self.get_feature_daily_limit(feature, model_name, billing_on)
        feature_usage = self.get_today_feature_usage(feature, model_name)
        if feature_usage >= feature_limit:
            logger.warning(
                "Daily safety budget reached for feature='%s' model='%s': %d/%d calls used today (mode: %s).",
                feature, model_name, feature_usage, feature_limit, mode
            )
            raise QuotaExceededError(feature)

        # 3. Global RPM Check
        if billing_on:
            global_rpm_limit = current_app.config.get("GEMINI_GLOBAL_RPM_LIMIT_PAID", 60)
        else:
            global_rpm_limit = current_app.config.get("GEMINI_GLOBAL_RPM_LIMIT_FREE", 12)

        current_global_rpm = self._global_limiter.get_count()
        if current_global_rpm >= global_rpm_limit:
            logger.warning(
                "Global RPM limit reached: %d/%d calls in last 60 seconds (mode: %s).",
                current_global_rpm, global_rpm_limit, mode
            )
            raise RateLimitError("global limit hit")

        # 4. Feature RPM Check
        feature_rpm_limit = self.get_feature_rpm_limit(feature, billing_on)
        current_feature_rpm = self._feature_limiters.get(feature).get_count()
        if current_feature_rpm >= feature_rpm_limit:
            logger.warning(
                "RPM limit reached for feature '%s': %d/%d calls in last 60 seconds (mode: %s).",
                feature, current_feature_rpm, feature_rpm_limit, mode
            )
            raise RateLimitError(f"{feature} limit hit")

    def record_call(self, feature: str):
        """Record a successful API call in the sliding window limiters."""
        self._global_limiter.record_call()
        if feature in self._feature_limiters:
            self._feature_limiters[feature].record_call()

    def get_today_global_usage(self) -> int:
        today = date.today()
        mode = current_app.config.get("GEMINI_MODE", "free").lower()
        suffix = f"% [{mode}]"
        try:
            return db.session.query(db.func.sum(DailyAPIUsage.call_count)).filter(
                DailyAPIUsage.feature != 'email_verification',
                DailyAPIUsage.model_name.like(suffix),
                DailyAPIUsage.usage_date == today
            ).scalar() or 0
        except Exception as e:
            logger.error("Error reading global daily usage: %s", e)
            return 0

    def get_today_feature_usage(self, feature: str, model_name: str) -> int:
        today = date.today()
        mode = current_app.config.get("GEMINI_MODE", "free").lower()
        db_model_name = f"{model_name} [{mode}]"
        try:
            row = DailyAPIUsage.query.filter_by(feature=feature, model_name=db_model_name, usage_date=today).first()
            return row.call_count if row else 0
        except Exception as e:
            logger.error("Error reading daily usage for '%s' (%s): %s", feature, db_model_name, e)
            return 0

    def get_feature_daily_limit(self, feature: str, model_name: str, billing_on: bool) -> int:
        if billing_on:
            if feature == FEATURE_MCQ:
                return current_app.config.get("GEMINI_DAILY_LIMIT_MCQ_PAID", 2000)
            if feature == FEATURE_ASSISTANT:
                return current_app.config.get("GEMINI_DAILY_LIMIT_ASSISTANT_PRIMARY_PAID", 1000)
        else:
            if feature == FEATURE_MCQ:
                return current_app.config.get("GEMINI_DAILY_LIMIT_MCQ", 450)
            if feature == FEATURE_ASSISTANT:
                primary_model = current_app.config.get("GEMINI_MODEL_ASSISTANT_PRIMARY", "gemini-3.6-flash")
                fallback_model = current_app.config.get("GEMINI_MODEL_ASSISTANT_FALLBACK", "gemini-3.5-flash-lite")

                if model_name == primary_model:
                    return current_app.config.get("GEMINI_DAILY_LIMIT_ASSISTANT_PRIMARY", 18)
                elif model_name == fallback_model:
                    return current_app.config.get("GEMINI_DAILY_LIMIT_ASSISTANT_FALLBACK", 450)
        return 999

    def get_feature_rpm_limit(self, feature: str, billing_on: bool) -> int:
        if billing_on:
            if feature == FEATURE_MCQ:
                return current_app.config.get("GEMINI_RPM_LIMIT_MCQ_PAID", 60)
            if feature == FEATURE_ASSISTANT:
                return current_app.config.get("GEMINI_RPM_LIMIT_ASSISTANT_PRIMARY_PAID", 30)
        else:
            if feature == FEATURE_MCQ:
                return current_app.config.get("GEMINI_RPM_LIMIT_MCQ", 15)
            if feature == FEATURE_ASSISTANT:
                return current_app.config.get("GEMINI_RPM_LIMIT_ASSISTANT_PRIMARY", 5)
        return 999


def _get_adaptive_quiz_difficulty(profile) -> str:
    """
    System-calculated quiz difficulty based on the student's mastery/risk level.
    """
    if not profile:
        return "Medium"
    risk = getattr(profile, '_risk_summary', None)
    if not risk:
        try:
            from app.models import Prediction
            latest_pred = (
                Prediction.query
                .filter_by(student_id=profile.user_id)
                .order_by(Prediction.predicted_at.desc())
                .first()
            )
            if latest_pred:
                label = (latest_pred.result or "").lower()
                if "fail" in label:
                    risk = "high"
                elif "risk" in label or "at risk" in label:
                    risk = "medium"
                else:
                    risk = "low"
        except Exception:
            risk = "medium"
    mapping = {"high": "Easy", "medium": "Medium", "low": "Hard"}
    return mapping.get(risk or "medium", "Medium")


def _get_system_response_length(profile) -> str:
    """
    System-determined response length.
    """
    if not profile:
        return "Medium"
    risk = getattr(profile, '_risk_summary', None)
    if risk == "high":
        return "Short"
    exp = getattr(profile, 'explanation_level', 'Intermediate') or 'Intermediate'
    if exp == "Master":
        return "Detailed"
    return "Medium"


class AIService:
    def __init__(self):
        self._provider = None
        self._claude_provider = None
        self._initialized = False
        self.quota_manager = CentralQuotaManager()
        self._last_error_type = "None"
        self._last_error_time = "Never"

    # ── Provider helpers ───────────────────────────────────────────────────────

    def _get_claude(self):
        """Lazy-initialize the Claude (Anthropic) provider."""
        if self._claude_provider is None:
            api_key = current_app.config.get("ANTHROPIC_API_KEY")
            if api_key:
                try:
                    from app.services.providers.claude import ClaudeProvider
                    self._claude_provider = ClaudeProvider(api_key)
                    logger.info("ClaudeProvider initialized successfully.")
                except Exception as e:
                    logger.error(f"Failed to initialize ClaudeProvider: {e}")
        return self._claude_provider

    def _get_provider(self):
        mode = current_app.config.get("GEMINI_MODE", "free").lower()
        billing_on = (mode == "paid")
        
        # Select correct key with fallback to GEMINI_API_KEY from config and env
        if billing_on:
            api_key = (
                current_app.config.get("GEMINI_API_KEY_PAID") or
                os.getenv("GEMINI_API_KEY_PAID") or
                current_app.config.get("GEMINI_API_KEY") or
                os.getenv("GEMINI_API_KEY")
            )
        else:
            api_key = (
                current_app.config.get("GEMINI_API_KEY_FREE") or
                os.getenv("GEMINI_API_KEY_FREE") or
                current_app.config.get("GEMINI_API_KEY") or
                os.getenv("GEMINI_API_KEY")
            )
            
        # Cross-key fallback validation (only if allowed)
        allow_cross_fallback = current_app.config.get("GEMINI_ALLOW_CROSS_KEY_FALLBACK", False)
        if not api_key and allow_cross_fallback:
            if billing_on:
                api_key = current_app.config.get("GEMINI_API_KEY_FREE") or os.getenv("GEMINI_API_KEY_FREE")
            else:
                api_key = current_app.config.get("GEMINI_API_KEY_PAID") or os.getenv("GEMINI_API_KEY_PAID")

        current_key = getattr(self._provider, 'api_key', None) if self._provider else None
        if not self._provider or current_key != api_key:
            if api_key:
                try:
                    from app.services.providers.gemini import GeminiProvider
                    self._provider = GeminiProvider(api_key)
                    masked = f"{api_key[:4]}...{api_key[-4:]}" if len(api_key) >= 8 else "set"
                    logger.info("Initialized GeminiProvider (active_mode=%s, key_configured=yes, key_masked=%s)", mode, masked)
                except Exception as e:
                    logger.error("Failed to initialize GeminiProvider (active_mode=%s, key_configured=yes): %s", mode, e)
                    self._provider = None
            else:
                logger.warning("GEMINI API key not configured for active_mode='%s' (key_configured=no). Running in fallback/offline mode.", mode)
                self._provider = None

        return self._provider

    # ── Daily quota helpers ────────────────────────────────────────────────────

    def _quota_limit(self, feature: str, model_name: str) -> int:
        mode = current_app.config.get("GEMINI_MODE", "free").lower()
        billing_on = (mode == "paid")
        return self.quota_manager.get_feature_daily_limit(feature, model_name, billing_on)

    def _today_usage(self, feature: str, model_name: str) -> int:
        return self.quota_manager.get_today_feature_usage(feature, model_name)

    def _check_quota(self, feature: str, model_name: str):
        self.quota_manager.check_rpm_and_quota(feature, model_name)

    def _increment_usage(self, feature: str, model_name: str):
        """
        Atomically increment the daily call counter for *feature* and *model_name*.
        Uses the suffix '[free]' or '[paid]' to keep pools isolated.
        """
        today = date.today()
        mode = current_app.config.get("GEMINI_MODE", "free").lower()
        db_model_name = f"{model_name} [{mode}]"
        try:
            with db.session.begin_nested():
                db.session.add(
                    DailyAPIUsage(feature=feature, model_name=db_model_name, usage_date=today, call_count=1)
                )
            db.session.commit()
        except Exception:
            try:
                db.session.execute(
                    db.update(DailyAPIUsage)
                    .where(
                        DailyAPIUsage.feature    == feature,
                        DailyAPIUsage.model_name == db_model_name,
                        DailyAPIUsage.usage_date == today,
                    )
                    .values(call_count=DailyAPIUsage.call_count + 1)
                )
                db.session.commit()
            except Exception as e:
                logger.error("Failed to atomically increment usage for '%s' (%s): %s", feature, db_model_name, e)

    # ── Cache helpers ──────────────────────────────────────────────────────────

    def _get_cache(self, prompt: str) -> str:
        prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        try:
            cached = AICache.query.filter_by(prompt_hash=prompt_hash).first()
            if cached:
                logger.info("AICache hit.")
                return cached.response_text
        except Exception as e:
            logger.error(f"Failed to read from AICache: {e}")
        return None

    def _set_cache(self, prompt: str, response_text: str):
        prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        try:
            exists = AICache.query.filter_by(prompt_hash=prompt_hash).first()
            if exists:
                logger.debug("AICache: entry already present, skipping insert.")
                return
            with db.session.begin_nested():
                cached = AICache(prompt_hash=prompt_hash, prompt=prompt, response_text=response_text)
                db.session.add(cached)
            db.session.commit()
            logger.info("Saved to AICache.")
        except Exception as e:
            logger.error(f"Failed to save to AICache: {e}")

    def invalidate_cache(self, prompt: str):
        """Delete a cache entry from AICache to force regeneration on the next call."""
        prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        try:
            cached = AICache.query.filter_by(prompt_hash=prompt_hash).first()
            if cached:
                db.session.delete(cached)
                db.session.commit()
                logger.info("AICache: invalidated/deleted entry successfully.")
        except Exception as e:
            logger.error(f"Failed to invalidate AICache: {e}")

    def _record_error(self, e: Exception):
        self._last_error_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")

    def _classify_exception(self, e: Exception) -> AIServiceError:
        err_str = str(e)
        if any(t in err_str for t in ["API_KEY_INVALID", "API key not valid", "invalid API key", "key invalid"]):
            return ConfigurationError("Invalid or missing API key")
        if any(t in err_str for t in ["429", "ResourceExhausted", "Quota", "quota", "exhausted"]):
            return QuotaExceededError("global_limit")
        if any(t in err_str for t in ["500", "503", "ServiceUnavailable", "InternalServerError", "overloaded", "busy"]):
            return RateLimitError("AI service temporarily overloaded")
        return AIServiceError(err_str)

    def get_provider_quota_reference(self, mode: str, model: str) -> dict:
        if mode == "free":
            meta = PROVIDER_QUOTA_METADATA["free"].get(model)
            if meta:
                return {"rpm": meta["rpm"], "rpd": meta["rpd"]}
            return {"rpm": 5, "rpd": 20}
        else:
            rpm = current_app.config.get("GEMINI_PAID_PROVIDER_RPM", "Unrestricted")
            rpd = current_app.config.get("GEMINI_PAID_PROVIDER_RPD", "Unrestricted")
            return {"rpm": rpm, "rpd": rpd}

    def get_ai_health_status(self) -> dict:
        mode = current_app.config.get("GEMINI_MODE", "free").lower()
        billing_on = (mode == "paid")
        
        # Check active key configured
        if billing_on:
            key = current_app.config.get("GEMINI_API_KEY_PAID") or current_app.config.get("GEMINI_API_KEY")
        else:
            key = current_app.config.get("GEMINI_API_KEY_FREE") or current_app.config.get("GEMINI_API_KEY")
        has_key = bool((key or "").strip())
        
        mcq_model = current_app.config.get("GEMINI_MODEL_MCQ", "gemini-3.5-flash-lite")
        assistant_model = current_app.config.get("GEMINI_MODEL_ASSISTANT_PRIMARY", "gemini-3.6-flash")
        fallback_model = current_app.config.get("GEMINI_MODEL_ASSISTANT_FALLBACK", "gemini-3.5-flash-lite")

        
        mcq_provider_quota = self.get_provider_quota_reference(mode, mcq_model)
        assistant_provider_quota = self.get_provider_quota_reference(mode, assistant_model)
        
        if billing_on:
            global_daily_limit = current_app.config.get("GEMINI_GLOBAL_DAILY_LIMIT_PAID", 5000)
            global_rpm_limit = current_app.config.get("GEMINI_GLOBAL_RPM_LIMIT_PAID", 60)
            mcq_daily_limit = current_app.config.get("GEMINI_DAILY_LIMIT_MCQ_PAID", 2000)
            mcq_rpm_limit = current_app.config.get("GEMINI_RPM_LIMIT_MCQ_PAID", 60)
            assistant_daily_limit = current_app.config.get("GEMINI_DAILY_LIMIT_ASSISTANT_PRIMARY_PAID", 1000)
            assistant_rpm_limit = current_app.config.get("GEMINI_RPM_LIMIT_ASSISTANT_PRIMARY_PAID", 30)
        else:
            global_daily_limit = current_app.config.get("GEMINI_GLOBAL_DAILY_LIMIT_FREE", 450)
            global_rpm_limit = current_app.config.get("GEMINI_GLOBAL_RPM_LIMIT_FREE", 12)
            mcq_daily_limit = current_app.config.get("GEMINI_DAILY_LIMIT_MCQ", 450)
            mcq_rpm_limit = current_app.config.get("GEMINI_RPM_LIMIT_MCQ", 15)
            assistant_daily_limit = current_app.config.get("GEMINI_DAILY_LIMIT_ASSISTANT_PRIMARY", 18)
            assistant_rpm_limit = current_app.config.get("GEMINI_RPM_LIMIT_ASSISTANT_PRIMARY", 5)
            
        global_usage = self.quota_manager.get_today_global_usage()
        mcq_usage = self.quota_manager.get_today_feature_usage(FEATURE_MCQ, mcq_model)
        assistant_usage = self.quota_manager.get_today_feature_usage(FEATURE_ASSISTANT, assistant_model)
        
        fallback_status = "Ready"
        if not billing_on:
            if assistant_usage >= assistant_daily_limit or self.quota_manager._feature_limiters[FEATURE_ASSISTANT].get_count() >= assistant_rpm_limit:
                fallback_status = f"Active (Fallback to {fallback_model})"
        
        status = "Available"
        if global_usage >= global_daily_limit:
            status = "Temporarily Limited (Daily Quota Exhausted)"
        elif self.quota_manager._global_limiter.get_count() >= global_rpm_limit:
            status = "Temporarily Limited (Rate Limit / RPM Protection)"
        elif not has_key:
            status = "Temporarily Limited (API Key Missing)"

        return {
            "mode": mode.upper(),
            "mcq_model": mcq_model,
            "assistant_model": assistant_model,
            "fallback_model": fallback_model,
            "api_config": "Configured" if has_key else "Missing",
            "status": status,
            "global_usage": global_usage,
            "global_daily_limit": global_daily_limit,
            "global_rpm_limit": global_rpm_limit,
            "global_rpm_usage": self.quota_manager._global_limiter.get_count(),
            
            "mcq_usage": mcq_usage,
            "mcq_daily_limit": mcq_daily_limit,
            "mcq_rpm_limit": mcq_rpm_limit,
            "mcq_rpm_usage": self.quota_manager._feature_limiters[FEATURE_MCQ].get_count(),
            "mcq_provider_quota": mcq_provider_quota,
            
            "assistant_usage": assistant_usage,
            "assistant_daily_limit": assistant_daily_limit,
            "assistant_rpm_limit": assistant_rpm_limit,
            "assistant_rpm_usage": self.quota_manager._feature_limiters[FEATURE_ASSISTANT].get_count(),
            "assistant_provider_quota": assistant_provider_quota,
            
            "last_error_type": self._last_error_type,
            "last_error_time": self._last_error_time,
            "fallback_status": fallback_status,
        }

    # ── Core generation ────────────────────────────────────────────────────────

    def generate_content(self, prompt: str, feature: str = FEATURE_ASSISTANT, **kwargs) -> str:
        cached_response = self._get_cache(prompt)
        if cached_response:
            return cached_response

        mode = current_app.config.get("GEMINI_MODE", "free").lower()
        billing_on = (mode == "paid")

        if feature == FEATURE_MCQ:
            model = current_app.config.get("GEMINI_MODEL_MCQ", "gemini-3.1-flash-lite")
            
            try:
                self._check_quota(FEATURE_MCQ, model)

                provider = self._get_provider()
                if not provider:
                    raise ConfigurationError("AI Provider is not configured or unavailable.")

                kwargs_mcq = dict(kwargs)
                kwargs_mcq["model"] = model
                response_text = provider.generate_content(prompt, **kwargs_mcq)

                self._increment_usage(FEATURE_MCQ, model)
                self.quota_manager.record_call(FEATURE_MCQ)
                self._set_cache(prompt, response_text)
                return response_text
            except AIServiceError as e:
                self._record_error(e)
                raise e
            except Exception as e:
                classified = self._classify_exception(e)
                self._record_error(classified)
                raise classified

        else:  # FEATURE_ASSISTANT
            primary_model = current_app.config.get("GEMINI_MODEL_ASSISTANT_PRIMARY", "gemini-3.6-flash")
            fallback_model = current_app.config.get("GEMINI_MODEL_ASSISTANT_FALLBACK", "gemini-3.5-flash-lite")


            use_primary = True
            if not billing_on:
                p_usage = self._today_usage(FEATURE_ASSISTANT, primary_model)
                p_limit = self._quota_limit(FEATURE_ASSISTANT, primary_model)
                p_rpm = self.quota_manager._feature_limiters[FEATURE_ASSISTANT].get_count()
                p_rpm_limit = current_app.config.get("GEMINI_RPM_LIMIT_ASSISTANT_PRIMARY", 5)

                if p_usage >= p_limit or p_rpm >= p_rpm_limit:
                    use_primary = False
                    logger.info(
                        "Assistant primary model limit reached (usage: %d/%d, RPM: %d/%d). "
                        "Falling back to %s.",
                        p_usage, p_limit, p_rpm, p_rpm_limit, fallback_model
                    )

            if use_primary:
                try:
                    self._check_quota(FEATURE_ASSISTANT, primary_model)

                    provider = self._get_provider()
                    if not provider:
                        raise ConfigurationError("AI Provider is not configured or unavailable.")

                    kwargs_primary = dict(kwargs)
                    kwargs_primary["model"] = primary_model

                    response_text = provider.generate_content(prompt, **kwargs_primary)

                    self._increment_usage(FEATURE_ASSISTANT, primary_model)
                    self.quota_manager.record_call(FEATURE_ASSISTANT)
                    self._set_cache(prompt, response_text)
                    return response_text

                except AIServiceError as e:
                    if isinstance(e, ConfigurationError) or (isinstance(e, QuotaExceededError) and e.feature == "global"):
                        self._record_error(e)
                        raise e
                    logger.warning("Primary assistant failed with AI error. Retrying with fallback model %s: %s", fallback_model, e)
                except Exception as e:
                    classified = self._classify_exception(e)
                    if isinstance(classified, ConfigurationError):
                        self._record_error(classified)
                        raise classified
                    logger.warning("Primary assistant failed. Retrying with fallback model %s: %s", fallback_model, e)

            # Fallback model execution
            try:
                self._check_quota(FEATURE_ASSISTANT, fallback_model)

                provider = self._get_provider()
                if not provider:
                    raise ConfigurationError("AI Provider is not configured or unavailable.")

                kwargs_fallback = dict(kwargs)
                kwargs_fallback["model"] = fallback_model

                response_text = provider.generate_content(prompt, **kwargs_fallback)

                self._increment_usage(FEATURE_ASSISTANT, fallback_model)
                self.quota_manager.record_call(FEATURE_ASSISTANT)
                self._set_cache(prompt, response_text)
                return response_text
            except AIServiceError as e:
                self._record_error(e)
                raise e
            except Exception as e:
                classified = self._classify_exception(e)
                self._record_error(classified)
                raise classified  # Fallback model execution


    # ── Tutor helpers ──────────────────────────────────────────────────────────

    def chat_with_tutor(self, user_query: str, subject_id: int = None, profile=None) -> str:
        try:
            subj_name = ""
            if subject_id:
                s = Subject.query.get(subject_id)
                if s:
                    subj_name = f" in the context of {s.name} ({s.level_of_study})"
            
            adaptive_difficulty = _get_adaptive_quiz_difficulty(profile)
            response_length     = _get_system_response_length(profile)

            context = ""
            if profile:
                context += f"\n- Education Level: {profile.level_of_study}"
                context += f"\n- Country: {profile.country}"
                context += f"\n- Curriculum: {profile.curriculum}"
                if profile.program:
                    context += f"\n- Faculty/Program: {profile.program}"
                if profile.semester:
                    context += f"\n- Semester/Year: {profile.semester}"
                context += f"\n- Preferred Explanation Level: {profile.explanation_level}"
                context += f"\n- Study Goal: {profile.study_goal}"
                context += f"\n- Preferred Output Language: {profile.preferred_language}"
                context += f"\n- [System] Adaptive Response Length: {response_length}"
                context += f"\n- [System] Adaptive Quiz Difficulty: {adaptive_difficulty}"
            
            system_prompt = (
                "You are Antigravity, a highly personalized, elite Academic AI Tutor. "
                "Help the student by explaining concepts, summarizing chapters, generating quizzes/flashcards, "
                "outlining revision notes, recommending study plans, explaining mistakes, or giving motivational study advice.\n"
                f"Student Profile Context: {context}\n\n"
                "Conform strictly to the explanation level, output language, and study goals listed above. "
                "When generating quizzes, use the [System] Adaptive Quiz Difficulty level specified."
            )
            
            prompt = f"Subject: {subj_name}\nQuestion: {user_query}"
            return self.call_gemini_reusable(
                prompt,
                feature=FEATURE_ASSISTANT,
                system_instruction=system_prompt,
                context="assistant_chat_tutor"
            )
        except QuotaExceededError:
            return (
                "### ⏳ AI Assistant Temporarily at Capacity\n"
                "We've reached today's AI Assistant limit. "
                "Please try again tomorrow — your questions will be answered then!"
            )
        except Exception as e:
            logger.error(f"Tutor chat failed. Engaging local fallback: {e}")
            return self._local_fallback_tutor(user_query, subject_id)

    def chat_with_history(self, history: list, user_query: str,
                          subject_id: int = None, profile=None) -> str:
        """Multi-turn conversation — Claude primary, Gemini fallback."""
        subj_name = ""
        if subject_id:
            s = Subject.query.get(subject_id)
            if s:
                subj_name = f" — Focus on: {s.name} ({s.level_of_study})"

        adaptive_difficulty = _get_adaptive_quiz_difficulty(profile)
        response_length     = _get_system_response_length(profile)

        ctx_lines = []
        if profile:
            ctx_lines += [
                f"Education Level: {getattr(profile, 'level_of_study', 'N/A')}",
                f"Curriculum: {getattr(profile, 'curriculum', 'N/A')}",
                f"Explanation Level: {getattr(profile, 'explanation_level', 'Intermediate')}",
                f"Study Goal: {getattr(profile, 'study_goal', 'Improve Grades')}",
                f"Language Preference: {getattr(profile, 'preferred_language', 'English')}",
                f"[System] Adaptive Response Length: {response_length}",
                f"[System] Adaptive Quiz Difficulty: {adaptive_difficulty}",
            ]
            if getattr(profile, 'program', None):
                ctx_lines.append(f"Program/Faculty: {profile.program}")
            if getattr(profile, 'semester', None):
                ctx_lines.append(f"Semester/Year: {profile.semester}")

        system_prompt = (
            "You are SmartStudy AI — a highly personalized academic tutor built for students "
            "from Class 6 to Master level following Nepal's CDC/NEB/University curriculum.\n\n"
            "Your responsibilities:\n"
            "• Explain concepts clearly and concisely\n"
            "• Generate quizzes, flashcards, revision notes on request\n"
            "• Provide step-by-step worked solutions\n"
            "• Give motivational study advice when needed\n"
            "• Respond in the student's preferred language (English/Nepali/Bilingual)\n"
            "• When generating quizzes, match the [System] Adaptive Quiz Difficulty level\n\n"
            f"Student Profile:\n" + "\n".join(f"  - {l}" for l in ctx_lines) +
            f"\n{subj_name}"
        )

        messages = list(history)
        messages.append({"role": "user", "content": user_query})

        # 1. Primary: Claude (no quota guard — has its own provider key)
        try:
            claude = self._get_claude()
            if claude:
                return claude.chat(messages, system=system_prompt)
        except Exception as e:
            logger.warning(f"Claude unavailable, falling back to Gemini: {e}")

        # 2. Fallback: Gemini (quota-guarded)
        try:
            context_history = ""
            for turn in messages:
                role = "Student" if turn["role"] == "user" else "Tutor"
                context_history += f"\n{role}: {turn['content']}"

            return self.call_gemini_reusable(
                prompt=f"Conversation Context:{context_history}\n\nTutor:",
                feature=FEATURE_ASSISTANT,
                system_instruction=system_prompt,
                context="assistant_chat_history"
            )
        except QuotaExceededError:
            return (
                "### ⏳ AI Assistant Temporarily at Capacity\n"
                "We've reached today's AI Assistant limit. "
                "Please try again tomorrow — your questions will be answered then!"
            )
        except Exception as e:
            logger.error(f"All AI providers failed: {e}")
            return self._local_fallback_tutor(user_query, subject_id)

    def _local_fallback_tutor(self, user_query: str, subject_id: int = None) -> str:
        return (
            "### ⚠️ Local Sync Mode Active\n"
            "Your SmartStudy engine cannot process cloud requests right now. "
            "Please review your saved local materials, textbook outlines, or try sending your chat query again shortly!"
        )

    # ── Quota status helper (for templates/admin) ──────────────────────────────

    def get_quota_status(self, feature: str) -> dict:
        """Return current usage and limit for *feature* (useful in admin views)."""
        billing_on = current_app.config.get("GEMINI_BILLING_ENABLED", False)
        if feature == FEATURE_MCQ:
            model = current_app.config.get("GEMINI_MODEL_MCQ", "gemini-3.5-flash-lite")
            usage = self._today_usage(feature, model)
            limit = self._quota_limit(feature, model)
        else:  # FEATURE_ASSISTANT
            model = current_app.config.get("GEMINI_MODEL_ASSISTANT_PRIMARY", "gemini-3.6-flash")
            usage = self._today_usage(feature, model)
            limit = self._quota_limit(feature, model)


        return {
            "feature":     feature,
            "used":        usage,
            "limit":       limit,
            "remaining":   max(0, limit - usage),
            "billing_on":  billing_on,
            "capped":      not billing_on and usage >= limit,
        }

    # ── On-demand Hierarchical Generation Methods ─────────────────────────────

    def _parse_json(self, response_text: str, context: str = ""):
        """
        Robustly parse a JSON response from Gemini.

        Strategy (in order):
          1. Strip markdown code fences and leading/trailing whitespace.
          2. Fix common issues: trailing commas, escaped single-quotes.
          3. Try stdlib json.loads on the full cleaned string.
          4. Try extracting the first JSON array [...] or object {...} block.
          5. Try json_repair (handles truncated / malformed JSON).
          6. Raise with a diagnostic snippet of the raw response.
        """
        if not response_text:
            raise ValueError(f"AI returned empty response{' [' + context + ']' if context else ''}.")

        raw_snippet = response_text[:200].replace('\n', ' ')
        cleaned = response_text.strip()

        # ── Step 1: Strip markdown code fences ─────────────────────────────
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            lines = lines[1:]  # drop opening fence line (```json or ```)
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()

        # ── Step 2: Common JSON fixups ──────────────────────────────────────
        # Remove trailing commas before ] or }
        cleaned = re.sub(r',\s*([\]}])', r'\1', cleaned)
        # Remove non-printable control characters that break the parser
        cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', cleaned)

        # ── Step 3: Direct parse ────────────────────────────────────────────
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as first_err:
            logger.debug(
                "_parse_json: direct parse failed%s — %s | snippet: %r",
                f' [{context}]' if context else '', first_err, raw_snippet
            )

        # ── Step 4: Extract first array or object block ─────────────────────
        for pattern in (r'\[.*\]', r'\{.*\}'):
            m = re.search(pattern, cleaned, re.DOTALL)
            if m:
                candidate = re.sub(r',\s*([\]}])', r'\1', m.group(0))
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    pass

        # ── Step 5: json_repair (handles truncation, mismatched quotes, etc.) ─
        try:
            import json_repair
            repaired = json_repair.repair_json(cleaned, return_objects=True)
            if repaired or repaired == [] or repaired == {}:
                logger.info(
                    "_parse_json: json_repair recovered response%s.",
                    f' [{context}]' if context else ''
                )
                return repaired
        except Exception as repair_err:
            logger.debug("_parse_json: json_repair also failed%s: %s", f' [{context}]' if context else '', repair_err)

        # ── Step 6: Give up with diagnostics ───────────────────────────────
        logger.error(
            "_parse_json: ALL parse strategies failed%s. Raw snippet: %r",
            f' [{context}]' if context else '', raw_snippet
        )
        raise ValueError(
            f"AI response is not valid JSON{' [' + context + ']' if context else ''}. "
            f"Raw snippet: {raw_snippet!r}"
        )

    def call_gemini_reusable(
        self,
        prompt: str,
        feature: str = FEATURE_ASSISTANT,
        is_json: bool = False,
        check_headings: bool = False,
        context: str = "",
        **kwargs
    ):
        """
        Single reusable function for Gemini calls with robust retry logic,
        JSON parsing correction, and content validation.
        """
        response_text = None

        # ── API Call Retries on 429/500 (up to 2 retries, 3 attempts total) ──
        for attempt in range(1, 4):
            try:
                logger.info("[REUSABLE AI] Stage 1: API Call. Attempt %d/3 for Context: %s", attempt, context)
                response_text = self.generate_content(prompt, feature=feature, **kwargs)
                break
            except Exception as e:
                err_str = str(e)
                # Check for 429 or 500 status indicators in error message
                is_retryable = any(status in err_str for status in ["429", "500", "503", "ResourceExhausted", "ServiceUnavailable", "InternalServerError"])
                if is_retryable and attempt < 3:
                    delay = 1.0 if attempt == 1 else 3.0
                    logger.warning("[REUSABLE AI] Retryable API error: %s. Sleeping %.1fs before attempt %d...", err_str, delay, attempt + 1)
                    time.sleep(delay)
                else:
                    logger.error("[REUSABLE AI] Permanent API error or max attempts reached: %s. Context: %s", err_str, context)
                    raise e

        # ── Validation before saving / returning ──
        if not response_text:
            logger.error("[REUSABLE AI] Rejection: Generated content is empty. Context: %s", context)
            raise ValueError("Generated content is empty")

        # Reject if under 100 characters for saved/structured generated content (materials & quizzes)
        if len(response_text) < 100 and (check_headings or is_json):
            logger.error("[REUSABLE AI] Rejection: Content length %d is under 100 characters limit. Context: %s", len(response_text), context)
            raise ValueError("Generated content is under 100 characters")

        if check_headings and not re.search(r'^#+\s+', response_text, re.MULTILINE):
            logger.error("[REUSABLE AI] Rejection: Content contains no markdown headings. Context: %s", context)
            raise ValueError("Generated content contains no markdown headings")

        # ── JSON Parsing and Self-Correction ──
        if is_json:
            parsed_data = None
            json_succeeded = False
            retry_needed = False

            # Attempt 1: Direct JSON load
            try:
                parsed_data = json.loads(response_text.strip())
                json_succeeded = True
                logger.info("[REUSABLE AI] Stage 2: JSON parsing succeeded on first try. Context: %s", context)
            except Exception as parse_err:
                logger.warning("[REUSABLE AI] Direct JSON parse failed: %s. Attempting markdown fence strip. Context: %s", parse_err, context)
                retry_needed = True

                # Attempt 2: Strip fences & trailing commas
                cleaned = response_text.strip()
                if cleaned.startswith("```"):
                    lines = cleaned.splitlines()
                    lines = lines[1:]  # drop opening fence line
                    if lines and lines[-1].strip().startswith("```"):
                        lines = lines[:-1]
                    cleaned = "\n".join(lines).strip()
                cleaned = re.sub(r',\s*([\]}])', r'\1', cleaned) # remove trailing commas
                cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', cleaned) # remove control characters
                
                try:
                    parsed_data = json.loads(cleaned)
                    json_succeeded = True
                    logger.info("[REUSABLE AI] Stage 2: JSON parsing succeeded after stripping markdown fences. Context: %s", context)
                except Exception as strip_err:
                    logger.warning("[REUSABLE AI] Stage 2: Markdown fence strip also failed: %s. Starting Gemini self-correction. Context: %s", strip_err, context)
                    
                    # Attempt 3: Send back to Gemini for correction
                    correction_prompt = (
                        f"Here is a raw response that was supposed to be valid JSON, but failed to parse:\n\n"
                        f"{response_text}\n\n"
                        f"Parse Error: {strip_err}\n\n"
                        f"Please correct this invalid JSON and return the corrected valid JSON only. "
                        f"Do not include any preamble, explanations, markdown code block formatting (like ```json), or text outside the JSON block."
                    )
                    
                    corrected_response = None
                    for corr_attempt in range(1, 4):
                        try:
                            corrected_response = self.generate_content(
                                correction_prompt,
                                feature=feature,
                                system_instruction="You are a JSON correction assistant. Output valid JSON only, without markdown fences or wrapping."
                            )
                            break
                        except Exception as corr_e:
                            err_str = str(corr_e)
                            is_retryable = any(status in err_str for status in ["429", "500", "503", "ResourceExhausted", "ServiceUnavailable", "InternalServerError"])
                            if is_retryable and corr_attempt < 3:
                                delay = 1.0 if corr_attempt == 1 else 3.0
                                time.sleep(delay)
                            else:
                                raise corr_e

                    # Parse corrected response
                    try:
                        cleaned_corrected = corrected_response.strip()
                        if cleaned_corrected.startswith("```"):
                            lines = cleaned_corrected.splitlines()
                            lines = lines[1:]
                            if lines and lines[-1].strip().startswith("```"):
                                lines = lines[:-1]
                            cleaned_corrected = "\n".join(lines).strip()
                        cleaned_corrected = re.sub(r',\s*([\]}])', r'\1', cleaned_corrected)
                        cleaned_corrected = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', cleaned_corrected)
                        
                        parsed_data = json.loads(cleaned_corrected)
                        json_succeeded = True
                        logger.info("[REUSABLE AI] Stage 2: JSON parsing succeeded after Gemini self-correction. Context: %s", context)
                    except Exception as corr_parse_err:
                        logger.error("[REUSABLE AI] Stage 2: JSON parsing failed permanently even after Gemini self-correction. Context: %s", context)
                        raise ValueError(f"Failed to correct invalid JSON: {corr_parse_err}")

            logger.info(
                "[REUSABLE AI] Stage 3: Summary. Succeeded: %s, Retry Needed: %s, Save Status: Success. Context: %s",
                json_succeeded, retry_needed, context
            )
            return parsed_data

        logger.info("[REUSABLE AI] Stage 3: Summary. Save Status: Success. Context: %s", context)
        return response_text

    def _call_ai_with_json_retry(
        self,
        prompt: str,
        context: str,
        feature: str = FEATURE_ASSISTANT,
        max_parse_retries: int = 2,
        **kwargs
    ):
        return self.call_gemini_reusable(
            prompt,
            feature=feature,
            is_json=True,
            context=context,
            **kwargs
        )

    def generate_chapters_for_subject(self, subject_id: int) -> list:
        subject = Subject.query.get(subject_id)
        if not subject:
            raise ValueError("Subject not found")
            
        prompt = (
            f"Generate a list of academic chapters for the subject '{subject.name}'.\n"
            f"Subject Code: {subject.code or 'N/A'}\n"
            f"Level of Study: {subject.level_of_study or 'N/A'}\n"
            f"Program/Faculty: {subject.program or 'General'}\n"
            f"Semester/Year: {subject.semester or 'N/A'}\n"
            f"Country Context: {subject.country or 'Nepal'}\n"
            f"Curriculum Context: {subject.curriculum or 'National Curriculum'}\n\n"
            "Generate a logical progression of 5 to 10 chapters matching the academic standards of this curriculum. "
            "For each chapter, provide a sequential chapter number and a concise name.\n"
            "Return the list strictly in valid JSON format. Do not include any preamble, markdown code blocks, or text outside the JSON."
        )
        
        system_instruction = (
            "You are an expert curriculum designer and AI academic advisor. "
            "You must output a JSON list of chapters. The format MUST be a valid JSON array of objects:\n"
            "[\n"
            "  {\n"
            '    "chapter_number": 1,\n'
            '    "name": "Introduction to Chapter Name"\n'
            "  },\n"
            "  ...\n"
            "]"
        )
        
        chapters_data = self._call_ai_with_json_retry(
            prompt=prompt,
            context=f"chapters:subject:{subject_id}",
            feature=FEATURE_ASSISTANT,
            system_instruction=system_instruction,
            max_parse_retries=2,
        )
        if not isinstance(chapters_data, list):
            raise ValueError(f"Expected a list of chapters from AI, got: {type(chapters_data)}")

        chapters = []
        for item in chapters_data:
            ch_num = int(item.get("chapter_number", 1))
            name = item.get("name", "").strip()
            if name:
                chapter = Chapter(
                    subject_id=subject.id,
                    name=name,
                    chapter_number=ch_num
                )
                db.session.add(chapter)
                chapters.append(chapter)
                
        db.session.commit()
        return sorted(chapters, key=lambda c: c.chapter_number)

    def generate_topics_for_chapter(self, chapter_id: int) -> list:
        chapter = Chapter.query.get(chapter_id)
        if not chapter:
            raise ValueError("Chapter not found")
            
        subject = Subject.query.get(chapter.subject_id)
        
        prompt = (
            f"Generate a list of academic topics for the chapter '{chapter.name}' (Chapter {chapter.chapter_number}) "
            f"within the subject '{subject.name}'.\n"
            f"Level of Study: {subject.level_of_study or 'N/A'}\n"
            f"Program/Faculty: {subject.program or 'General'}\n"
            f"Country/Curriculum: {subject.country or 'Nepal'} / {subject.curriculum or 'National Curriculum'}\n\n"
            "Generate a logical sequence of 4 to 8 distinct topics covering the subtopics of this chapter. "
            "For each topic, provide a sequential topic number and a name.\n"
            "Return the list strictly in valid JSON format. Do not include any preamble, markdown code blocks, or text outside the JSON."
        )
        
        system_instruction = (
            "You are an expert curriculum designer and AI academic advisor. "
            "You must output a JSON list of topics. The format MUST be a valid JSON array of objects:\n"
            "[\n"
            "  {\n"
            '    "topic_number": 1,\n'
            '    "name": "Topic Name Here"\n'
            "  },\n"
            "  ...\n"
            "]"
        )
        
        topics_data = self._call_ai_with_json_retry(
            prompt=prompt,
            context=f"topics:chapter:{chapter_id}",
            feature=FEATURE_ASSISTANT,
            system_instruction=system_instruction,
            max_parse_retries=2,
        )
        if not isinstance(topics_data, list):
            raise ValueError(f"Expected a list of topics from AI, got: {type(topics_data)}")

        topics = []
        for item in topics_data:
            t_num = int(item.get("topic_number", 1))
            name = item.get("name", "").strip()
            if name:
                topic = Topic(
                    chapter_id=chapter.id,
                    name=name,
                    topic_number=t_num
                )
                db.session.add(topic)
                topics.append(topic)
                
        db.session.commit()
        return sorted(topics, key=lambda t: t.topic_number)

    def generate_lesson_material(self, topic_id: int) -> LearningMaterial:
        """
        Generate lesson material for a topic.

        ARCHITECTURE NOTE
        -----------------
        We deliberately split the generation into TWO independent AI calls:

        Call 1 — Prose content (Markdown)
            Gemini writes plain Markdown with labelled sections.  Markdown is
            parsed with simple string splitting — zero JSON involved — so it
            never fails due to escaped quotes or special characters inside
            HTML strings.

        Call 2 — Structured lists (small JSON)
            MCQs, flashcards, and question lists are compact and contain no
            embedded HTML, so JSON is reliable here.  The call uses
            _call_ai_with_json_retry for automatic parse-retry.

        This replaces the previous single-call approach that embedded HTML
        inside a giant JSON string, which caused recurring parse failures.
        """
        topic = Topic.query.get(topic_id)
        if not topic:
            raise ValueError("Topic not found")

        chapter = Chapter.query.get(topic.chapter_id)
        subject = Subject.query.get(chapter.subject_id)

        from flask_login import current_user
        from app.models import StudentProfile
        profile = StudentProfile.query.filter_by(user_id=current_user.id).first()

        study_level = (
            profile.study_level if (profile and profile.study_level)
            else (subject.level_of_study or "Class 9")
        )
        curriculum = (
            profile.curriculum if (profile and profile.curriculum)
            else (subject.curriculum or "National Curriculum")
        )
        pref_lang = (
            profile.preferred_language if (profile and profile.preferred_language)
            else "English"
        )

        ctx_label = f"lesson:{topic.id}:{topic.name[:30]}"
        topic_ctx = (
            f"Topic: '{topic.name}' (Topic {topic.topic_number})\n"
            f"Chapter: '{chapter.name}' (Chapter {chapter.chapter_number})\n"
            f"Subject: '{subject.name}'\n"
            f"Study Level: {study_level}\n"
            f"Curriculum: {curriculum}\n"
            f"Language: {pref_lang}"
        )

        # ── Call 1: Prose content as Markdown ──────────────────────────────
        prose_prompt = (
            f"Write comprehensive academic study notes for the following:\n{topic_ctx}\n\n"
            "Use EXACTLY the section headers below (copy them verbatim, including the ## prefix).\n"
            "Write each section in clear, structured Markdown. Use bullet points, numbered lists, "
            "bold text, and sub-headings freely. Do NOT output JSON.\n\n"
            "## Title\n"
            "## Learning Objectives\n"
            "## Introduction\n"
            "## Detailed Explanation\n"
            "## Important Definitions\n"
            "## Key Concepts\n"
            "## Examples\n"
            "## Worked Examples\n"
            "## Real-Life Applications\n"
            "## Diagrams\n"
            "## Key Points\n"
            "## Important Facts\n"
            "## Formulae\n"
            "## Common Mistakes\n"
            "## Summary\n"
            "## Revision Notes\n"
            "## Learning Outcomes"
        )

        prose_system = (
            "You are an elite Academic AI Tutor writing study notes for a student. "
            "Always use the exact section headers provided. Write in plain Markdown only — "
            "do not output JSON or HTML tags."
        )

        logger.info("generate_lesson_material: starting prose call [%s]", ctx_label)
        t0 = time.time()
        prose_text = self.call_gemini_reusable(
            prose_prompt,
            feature=FEATURE_ASSISTANT,
            is_json=False,
            check_headings=True,
            context=f"prose_notes:topic:{topic_id}",
            system_instruction=prose_system,
            max_output_tokens=8192,
        )
        logger.info(
            "generate_lesson_material: prose call done [%s] elapsed=%.2fs chars=%d",
            ctx_label, time.time() - t0, len(prose_text)
        )

        # Parse Markdown sections — no JSON needed
        sections = self._parse_markdown_sections(prose_text)

        # ── Call 2: Structured lists as small JSON ─────────────────────────
        lists_prompt = (
            f"Generate practice material for:\n{topic_ctx}\n\n"
            "Return ONLY a valid JSON object with exactly these keys:\n"
            "{\n"
            '  "mcqs": [\n'
            '    { "q": "Question text?", "a": "Option A", "b": "Option B", '
            '"c": "Option C", "d": "Option D", "ans": "A", "exp": "Explanation" }\n'
            '    ... (5 to 8 items)\n'
            '  ],\n'
            '  "short_answer_questions": ["1. Question text", "2. ..."],\n'
            '  "long_answer_questions": ["1. Question text", "2. ..."],\n'
            '  "critical_thinking_questions": ["1. Question text", "2. ..."],\n'
            '  "flashcards": [\n'
            '    { "front": "Term or question", "back": "Definition or answer" }\n'
            '    ... (5 to 8 items)\n'
            '  ]\n'
            "}\n\n"
            "Rules:\n"
            "- No markdown code fences. Output only the JSON object.\n"
            "- No HTML tags inside any string value.\n"
            "- MCQ 'ans' must be exactly one of: A, B, C, D.\n"
            "- All strings must use double quotes."
        )

        lists_system = (
            "You are an expert curriculum examiner. "
            "Output strictly valid JSON only — no markdown, no extra text, no HTML."
        )

        logger.info("generate_lesson_material: starting lists call [%s]", ctx_label)
        try:
            lists_data = self._call_ai_with_json_retry(
                prompt=lists_prompt,
                context=ctx_label + ":lists",
                feature=FEATURE_ASSISTANT,
                system_instruction=lists_system,
                max_output_tokens=4096,
                max_parse_retries=2,
            )
        except Exception as lists_err:
            logger.warning(
                "generate_lesson_material: lists call failed [%s] — using empty defaults: %s",
                ctx_label, lists_err
            )
            lists_data = {}

        # ── Combine and persist ────────────────────────────────────────────
        def _md_to_html(md_text: str) -> str:
            """Minimal Markdown → HTML for common patterns (no external lib required)."""
            if not md_text:
                return ""
            # Bold
            html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', md_text)
            # Italic
            html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)
            # ### heading → <h4>
            html = re.sub(r'^### (.+)$', r'<h4>\1</h4>', html, flags=re.MULTILINE)
            # ## heading → <h3>
            html = re.sub(r'^## (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
            # Numbered list items
            html = re.sub(r'^\d+\.\s+(.+)$', r'<li>\1</li>', html, flags=re.MULTILINE)
            # Bullet list items
            html = re.sub(r'^[\-\*]\s+(.+)$', r'<li>\1</li>', html, flags=re.MULTILINE)
            # Wrap consecutive <li> blocks in <ul>
            html = re.sub(r'(<li>.*?</li>\n?)+', lambda m: '<ul>' + m.group(0) + '</ul>', html, flags=re.DOTALL)
            # Paragraphs: blank-line separated blocks
            paras = re.split(r'\n{2,}', html)
            result = []
            for p in paras:
                p = p.strip()
                if p and not p.startswith('<'):
                    p = f'<p>{p}</p>'
                result.append(p)
            return '\n'.join(result)

        g = sections.get
        material = LearningMaterial(
            topic_id=topic.id,
            title=g("title") or topic.name,
            learning_objectives=_md_to_html(g("learning objectives") or g("learning_objectives") or ""),
            introduction=_md_to_html(g("introduction") or ""),
            detailed_explanation=_md_to_html(g("detailed explanation") or g("detailed_explanation") or ""),
            important_definitions=_md_to_html(g("important definitions") or g("important_definitions") or ""),
            concepts=_md_to_html(g("key concepts") or g("concepts") or ""),
            examples=_md_to_html(g("examples") or ""),
            worked_examples=_md_to_html(g("worked examples") or g("worked_examples") or ""),
            real_life_applications=_md_to_html(g("real-life applications") or g("real_life_applications") or ""),
            diagrams=g("diagrams") or "",
            key_points=_md_to_html(g("key points") or g("key_points") or ""),
            important_facts=_md_to_html(g("important facts") or g("important_facts") or ""),
            formulae=_md_to_html(g("formulae") or g("formulas") or ""),
            common_mistakes=_md_to_html(g("common mistakes") or g("common_mistakes") or ""),
            summary=_md_to_html(g("summary") or ""),
            revision_notes=_md_to_html(g("revision notes") or g("revision_notes") or ""),
            learning_outcomes=_md_to_html(g("learning outcomes") or g("learning_outcomes") or ""),
            mcqs_json=json.dumps(lists_data.get("mcqs", []) if isinstance(lists_data, dict) else []),
            short_questions_json=json.dumps(lists_data.get("short_answer_questions", []) if isinstance(lists_data, dict) else []),
            long_questions_json=json.dumps(lists_data.get("long_answer_questions", []) if isinstance(lists_data, dict) else []),
            critical_thinking_questions_json=json.dumps(lists_data.get("critical_thinking_questions", []) if isinstance(lists_data, dict) else []),
            estimated_reading_time=15,
            difficulty_level="Intermediate",
        )
        db.session.add(material)

        # Save flashcards
        flashcards_data = lists_data.get("flashcards", []) if isinstance(lists_data, dict) else []
        for fc in flashcards_data:
            if isinstance(fc, dict):
                front = fc.get("front")
                back = fc.get("back")
                if front and back:
                    db.session.add(Flashcard(
                        subject_id=subject.id,
                        chapter_id=chapter.id,
                        front=str(front),
                        back=str(back),
                    ))

        db.session.commit()
        logger.info("generate_lesson_material: committed to DB [%s]", ctx_label)
        return material

    def _parse_markdown_sections(self, text: str) -> dict:
        """
        Split a Markdown document into a dict keyed by lowercased section name.

        Handles both '## Section Name' and '# Section Name' headings.
        Strips leading/trailing whitespace from each section body.
        """
        sections = {}
        current_key = None
        current_lines = []

        for line in text.splitlines():
            if line.startswith('## ') or line.startswith('# '):
                # Save the previous section
                if current_key is not None:
                    sections[current_key] = '\n'.join(current_lines).strip()
                # Start new section
                current_key = line.lstrip('#').strip().lower()
                current_lines = []
            else:
                if current_key is not None:
                    current_lines.append(line)

        # Save the last section
        if current_key is not None:
            sections[current_key] = '\n'.join(current_lines).strip()

        logger.debug("_parse_markdown_sections: parsed %d sections: %s", len(sections), list(sections.keys()))
        return sections


# --- INSTANTIATE THE GLOBAL SERVICE OBJECT FOR ROUTE IMPORTS ---
ai_service = AIService()


def call_ai_model(prompt: str) -> str:
    """Helper function to invoke Gemini model via AIService with graceful fallback."""
    try:
        return ai_service.generate_content(prompt)
    except Exception as e:
        return f"Hello! I am your AI Study Assistant. Here is an explanation for your question:\n\n{prompt[:120]}..."

