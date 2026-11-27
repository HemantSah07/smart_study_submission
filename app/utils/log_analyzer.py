from datetime import date, datetime, timedelta
import json
from app import db
from app.models import StudyLog, StudyPlan, LearningProgress, StudyLogAnalysis, Topic, Chapter
from app.utils.timezone_utils import local_now_for_user, local_today_for_user

def analyze_student_logs(user_id):
    """
    Analyzes study logs for the past 7 days against the active study plan.
    Saves and returns a StudyLogAnalysis record.
    """
    today = local_today_for_user(user_id)
    start_date = today - timedelta(days=7)
    local_now_naive = local_now_for_user(user_id).replace(tzinfo=None)
    
    # 1. Gather logged hours in past 7 days
    logs = StudyLog.query.filter(
        StudyLog.user_id == user_id,
        StudyLog.date >= start_date
    ).all()
    total_logged_hours = sum(l.duration_hours for l in logs)
    
    # 2. Gather active planner data
    active_plan = StudyPlan.query.filter_by(student_id=user_id).order_by(StudyPlan.generated_at.desc()).first()
    total_planned_hours = 0.0
    planned_sessions_count = 0
    
    if active_plan and active_plan.plan_data:
        try:
            plan_dict = json.loads(active_plan.plan_data)
            schedule = plan_dict.get("schedule", {})
            for day, slots in schedule.items():
                for slot in slots:
                    planned_sessions_count += 1
                    total_planned_hours += float(slot.get("hours", 1.0))
        except Exception:
            pass
            
    if total_planned_hours == 0:
        total_planned_hours = 15.0 # fallback target
        
    # 3. Gather completed topics in past 7 days
    recent_progress = LearningProgress.query.filter(
        LearningProgress.user_id == user_id,
        LearningProgress.is_completed == True,
        LearningProgress.completed_at >= local_now_naive - timedelta(days=7)
    ).all()
    completed_topics_count = len(recent_progress)
    
    # 4. Calculate missed sessions (Planned sessions - Logged sessions count)
    logged_sessions_count = len(logs)
    missed_sessions = max(0, planned_sessions_count - logged_sessions_count)
    
    # 5. Study speed (hours spent per completed topic)
    if completed_topics_count > 0:
        study_speed = round(total_logged_hours / completed_topics_count, 2)
    else:
        study_speed = 0.0
        
    # 6. Productivity score
    productivity_score = round((total_logged_hours / total_planned_hours) * 100.0, 2)
    productivity_score = min(100.0, productivity_score)
    
    # 7. Check if planner regeneration is recommended
    # Diverges if productivity score < 70% or missed sessions > 3
    diverges_significantly = (productivity_score < 70.0) or (missed_sessions > 3)
    
    # Save analysis record
    analysis = StudyLogAnalysis.query.filter_by(user_id=user_id).first()
    if not analysis:
        analysis = StudyLogAnalysis(
            user_id=user_id,
            total_logged_hours=total_logged_hours,
            total_planned_hours=total_planned_hours,
            completed_topics=completed_topics_count,
            missed_sessions=missed_sessions,
            study_speed=study_speed,
            diverges_significantly=diverges_significantly,
            analyzed_at=local_now_naive
        )
        db.session.add(analysis)
    else:
        analysis.total_logged_hours = total_logged_hours
        analysis.total_planned_hours = total_planned_hours
        analysis.completed_topics = completed_topics_count
        analysis.missed_sessions = missed_sessions
        analysis.study_speed = study_speed
        analysis.diverges_significantly = diverges_significantly
        analysis.analyzed_at = local_now_naive
        
    db.session.commit()
    return analysis
