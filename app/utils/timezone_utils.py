from datetime import datetime
from zoneinfo import ZoneInfo

from app.models import StudentProfile


COUNTRY_DEFAULT_TIMEZONES = {
    "Nepal": "Asia/Kathmandu",
    "United Kingdom": "Europe/London",
    "South Korea": "Asia/Seoul",
    "China": "Asia/Shanghai",
    "Germany": "Europe/Berlin",
    "Japan": "Asia/Tokyo",
    "Switzerland": "Europe/Zurich",
    "Singapore": "Asia/Singapore",
    "Finland": "Europe/Helsinki",
    "Netherlands": "Europe/Amsterdam",
    "Sweden": "Europe/Stockholm",
    "Denmark": "Europe/Copenhagen",
    "Norway": "Europe/Oslo",
    "Ireland": "Europe/Dublin",
    "Belgium": "Europe/Brussels",
    "France": "Europe/Paris",
    "Italy": "Europe/Rome",
    "India": "Asia/Kolkata",
}

MULTI_TIMEZONE_OPTIONS = {
    "United States": [
        "America/New_York",
        "America/Chicago",
        "America/Denver",
        "America/Los_Angeles",
        "America/Anchorage",
        "Pacific/Honolulu",
    ],
    "Canada": [
        "America/Toronto",
        "America/Winnipeg",
        "America/Edmonton",
        "America/Vancouver",
        "America/Halifax",
        "America/St_Johns",
    ],
    "Australia": [
        "Australia/Sydney",
        "Australia/Melbourne",
        "Australia/Brisbane",
        "Australia/Adelaide",
        "Australia/Perth",
    ],
}


def default_timezone_for_country(country):
    country = country or "Nepal"
    if country in MULTI_TIMEZONE_OPTIONS:
        return MULTI_TIMEZONE_OPTIONS[country][0]
    return COUNTRY_DEFAULT_TIMEZONES.get(country, "UTC")


def timezone_for_user(user_id):
    profile = StudentProfile.query.filter_by(user_id=user_id).first()
    tz_name = getattr(profile, "timezone", None) or default_timezone_for_country(getattr(profile, "country", None))
    try:
        return ZoneInfo(tz_name), tz_name
    except Exception:
        return ZoneInfo("UTC"), "UTC"


def local_now_for_user(user_id):
    tz, _ = timezone_for_user(user_id)
    return datetime.now(tz)


def local_today_for_user(user_id):
    return local_now_for_user(user_id).date()
