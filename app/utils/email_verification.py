import re
import requests
import logging
import json
from datetime import datetime, date, timedelta
from flask import current_app
from app import db
from app.models import DailyAPIUsage, EmailVerificationCache

logger = logging.getLogger(__name__)

def verify_email(email: str) -> dict:
    """
    Verifies the email address using Abstract API's email validation service.
    
    Returns a dict with key fields:
      - deliverability: "DELIVERABLE", "UNDELIVERABLE", "UNKNOWN", or "RISKY"
      - is_valid_format: bool
      - source: "api" | "cache" | "fallback"
    """
    email_clean = email.strip().lower()
    
    # Standard email regex pattern for basic/fallback check
    email_regex = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    regex_valid = bool(re.match(email_regex, email_clean))
    
    if not regex_valid:
        return {
            "deliverability": "UNDELIVERABLE",
            "is_valid_format": False,
            "source": "fallback"
        }
    
    # 1. Cache lookup (check within the last 30 days)
    try:
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        cache_entry = EmailVerificationCache.query.filter(
            EmailVerificationCache.email == email_clean,
            EmailVerificationCache.checked_at >= thirty_days_ago
        ).first()
        
        if cache_entry:
            logger.info("Email verification cache hit for %s", email_clean)
            cached_data = json.loads(cache_entry.verification_result)
            return {
                "deliverability": cached_data.get("deliverability", "UNKNOWN").upper(),
                "is_valid_format": cached_data.get("is_valid_format", False),
                "source": "cache"
            }
    except Exception as e:
        logger.error("Failed to read from EmailVerificationCache: %s", e)
        
    # 2. Check API limits and keys
    api_key = current_app.config.get("ABSTRACT_API_KEY")
    if not api_key:
        logger.warning("ABSTRACT_API_KEY not configured. Falling back to basic format validation for %s", email_clean)
        return {
            "deliverability": "UNKNOWN" if regex_valid else "UNDELIVERABLE",
            "is_valid_format": regex_valid,
            "source": "fallback"
        }
        
    # Check monthly usage counter (1000 limit)
    try:
        today = date.today()
        first_day_of_month = date(today.year, today.month, 1)
        monthly_usage = db.session.query(db.func.sum(DailyAPIUsage.call_count)).filter(
            DailyAPIUsage.feature == 'email_verification',
            DailyAPIUsage.usage_date >= first_day_of_month,
            DailyAPIUsage.usage_date <= today
        ).scalar() or 0
        
        if monthly_usage >= 1000:
            logger.warning("Abstract API monthly limit reached (current usage: %d/1000). Falling back to basic validation for %s", monthly_usage, email_clean)
            return {
                "deliverability": "UNKNOWN" if regex_valid else "UNDELIVERABLE",
                "is_valid_format": regex_valid,
                "source": "fallback"
            }
    except Exception as e:
        logger.error("Failed to query monthly API usage for email verification: %s", e)
        # Proceed to try the API since we couldn't confirm limit exhaustion
        
    # 3. Call the Abstract API
    url = "https://emailvalidation.abstractapi.com/v1/"
    params = {
        "api_key": api_key,
        "email": email_clean
    }
    
    try:
        logger.info("Calling Abstract API to verify email: %s", email_clean)
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        deliverability = data.get("deliverability", "UNKNOWN").upper()
        
        is_valid_format_data = data.get("is_valid_format", {})
        if isinstance(is_valid_format_data, dict):
            is_valid_format = is_valid_format_data.get("value", False)
        else:
            is_valid_format = bool(is_valid_format_data)
            
        result = {
            "deliverability": deliverability,
            "is_valid_format": is_valid_format,
            "source": "api"
        }
        
        # Save to cache and increment usage
        _save_verification_to_cache(email_clean, result)
        _increment_email_api_usage()
        
        return result
        
    except Exception as e:
        logger.error("Abstract API call failed or timed out for %s: %s. Falling back to basic format validation.", email_clean, e)
        return {
            "deliverability": "UNKNOWN" if regex_valid else "UNDELIVERABLE",
            "is_valid_format": regex_valid,
            "source": "fallback"
        }

def _save_verification_to_cache(email: str, result: dict):
    try:
        cache_entry = EmailVerificationCache.query.filter_by(email=email).first()
        if cache_entry:
            cache_entry.verification_result = json.dumps(result)
            cache_entry.checked_at = datetime.utcnow()
        else:
            cache_entry = EmailVerificationCache(
                email=email,
                verification_result=json.dumps(result),
                checked_at=datetime.utcnow()
            )
            db.session.add(cache_entry)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error("Failed to save verification result to cache for %s: %s", email, e)

def _increment_email_api_usage():
    today = date.today()
    try:
        with db.session.begin_nested():
            db.session.add(
                DailyAPIUsage(
                    feature='email_verification',
                    model_name=None,
                    usage_date=today,
                    call_count=1
                )
            )
        db.session.commit()
    except Exception:
        try:
            db.session.execute(
                db.update(DailyAPIUsage)
                .where(
                    DailyAPIUsage.feature == 'email_verification',
                    DailyAPIUsage.model_name.is_(None),
                    DailyAPIUsage.usage_date == today
                )
                .values(call_count=DailyAPIUsage.call_count + 1)
            )
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error("Failed to increment email API usage: %s", e)
