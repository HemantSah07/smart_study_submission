# app/services/notification_service.py
from datetime import datetime, date, timedelta
from app import db
from app.models import Notification, Subject, Exam, StudyLog, StudentProfile, SubjectPerformanceHistory
from app.services.coverage_analysis import compute_coverage

def generate_student_notifications(user_id: int):
    """
    Evaluates rule triggers for a student and creates real-time Notification records:
    1. High Academic Risk Alert (Subject risk_score >= 0.65)
    2. Upcoming Exam Proximity Alert (< 7 days away and subject coverage < 50%)
    3. Missing Study Log Gap Alert (No log yesterday & target_weekly_hours > 0)
    
    Wrapped in comprehensive try...except blocks to guarantee zero unhandled runtime exceptions.
    """
    try:
        profile = StudentProfile.query.filter_by(user_id=user_id).first()
        if not profile:
            return

        today = date.today()
        created_count = 0

        def add_notification_if_new(msg_text):
            nonlocal created_count
            try:
                existing = Notification.query.filter_by(user_id=user_id, message=msg_text, is_read=False).first()
                if not existing:
                    n = Notification(user_id=user_id, message=msg_text, is_read=False, date=datetime.utcnow())
                    db.session.add(n)
                    created_count += 1
            except Exception as e:
                print(f"[Notification Engine] add_notification_if_new warning: {e}")

        # 1. Risk Alert: Check SubjectPerformanceHistory
        try:
            high_risk_rows = SubjectPerformanceHistory.query.filter(
                SubjectPerformanceHistory.user_id == user_id,
                SubjectPerformanceHistory.risk_score >= 0.65
            ).all()

            for row in high_risk_rows:
                if row and row.subject_name:
                    msg = f"Warning: High academic risk detected in {row.subject_name}. Consider increasing your daily study allocation."
                    add_notification_if_new(msg)
        except Exception as e:
            print(f"[Notification Engine] Risk check warning: {e}")

        # 2. Exam Proximity Alert (Within 7 days & coverage < 50%)
        try:
            next_week = today + timedelta(days=7)
            upcoming_exams = Exam.query.filter(
                Exam.user_id == user_id,
                Exam.date >= today,
                Exam.date <= next_week
            ).all()

            for exam in upcoming_exams:
                if not exam or not exam.date:
                    continue
                days_left = (exam.date - today).days
                cov_pct = 0.0
                if exam.subject_id:
                    try:
                        cov_items = compute_coverage(user_id, exam.subject_id)
                        if cov_items and isinstance(cov_items, list):
                            covered_cnt = sum(1 for c in cov_items if isinstance(c, dict) and c.get('covered'))
                            cov_pct = (covered_cnt / len(cov_items)) * 100.0 if len(cov_items) > 0 else 0.0
                    except Exception:
                        cov_pct = 0.0

                if cov_pct < 50.0:
                    subj_name = exam.name or "Upcoming Exam"
                    if exam.subject_id:
                        s = Subject.query.get(exam.subject_id)
                        if s and s.name:
                            subj_name = s.name
                    days_str = "today" if days_left == 0 else (f"tomorrow" if days_left == 1 else f"in {days_left} days")
                    msg = f"Upcoming Exam: {subj_name} exam is {days_str}. Syllabus coverage is currently at {int(cov_pct)}%."
                    add_notification_if_new(msg)
        except Exception as e:
            print(f"[Notification Engine] Exam check warning: {e}")

        # 3. Study Log Gap Alert (No log yesterday & target_weekly_hours > 0)
        try:
            target_hours = float(profile.target_weekly_hours or 0.0)
            if target_hours > 0:
                yesterday = today - timedelta(days=1)
                logged_yesterday = StudyLog.query.filter_by(user_id=user_id, date=yesterday).first()
                if not logged_yesterday:
                    msg = "Planner Notice: No study hours logged yesterday. Click here to adapt and regenerate your schedule."
                    add_notification_if_new(msg)
        except Exception as e:
            print(f"[Notification Engine] Log gap warning: {e}")

        if created_count > 0:
            db.session.commit()
    except Exception as outer_err:
        db.session.rollback()
        print(f"[Notification Engine] Outer exception caught safely: {outer_err}")

def get_unread_notifications(user_id: int):
    try:
        return Notification.query.filter_by(user_id=user_id, is_read=False).order_by(Notification.date.desc()).all()
    except Exception as e:
        print(f"[Notification Engine] get_unread_notifications warning: {e}")
        return []

def mark_notification_as_read(notification_id: int, user_id: int):
    try:
        n = Notification.query.filter_by(id=notification_id, user_id=user_id).first()
        if n:
            n.is_read = True
            db.session.commit()
            return True
        return False
    except Exception as e:
        print(f"[Notification Engine] mark_notification_as_read warning: {e}")
        return False

def mark_all_notifications_as_read(user_id: int):
    try:
        Notification.query.filter_by(user_id=user_id, is_read=False).update({"is_read": True})
        db.session.commit()
        return True
    except Exception as e:
        print(f"[Notification Engine] mark_all_notifications_as_read warning: {e}")
        return False
