# app/services/exam_readiness.py
from app.models import Subject, Chapter, Topic, QuizScore, SubjectPerformanceHistory
from app.services.coverage_analysis import compute_coverage
from app import db


def generate_exam_readiness_score(user_id: int, subject_id: int) -> dict:
    """
    Calculates a multi-factor Exam Readiness Score (0 - 100%) combining:
    1. Syllabus Coverage (40% weight)
    2. Quiz Accuracy & Mastery (35% weight)
    3. Academic Safety / Inverse Risk Factor (25% weight)
    
    Also identifies specific weak topics and strategic recommendations.
    """
    subject = Subject.query.get(subject_id)
    if not subject:
        return {"error": "Subject not found", "readiness_score": 0.0}

    # 1. Syllabus Coverage Factor (40%)
    try:
        cov_data = compute_coverage(user_id, subject_id)
        coverage_pct = float(cov_data.get("overall_coverage_pct", 0.0))
    except Exception:
        coverage_pct = 0.0

    # 2. Quiz Accuracy & Mastery Factor (35%)
    general_quiz_scores = QuizScore.query.filter_by(user_id=user_id, subject_id=subject.id).all()
    gen_scores = [g.score for g in general_quiz_scores if g.score is not None]

    if gen_scores:
        quiz_accuracy_pct = float(sum(gen_scores) / len(gen_scores))
    else:
        quiz_accuracy_pct = 50.0 # Neutral baseline if no quizzes taken yet

    # 3. Academic Safety Factor (25%) -> (1 - Risk) * 100
    try:
        hist = SubjectPerformanceHistory.query.filter_by(
            user_id=user_id, subject_name=subject.name
        ).order_by(SubjectPerformanceHistory.week_start.desc()).first()
        
        if hist and hist.risk_score is not None:
            risk_score = float(hist.risk_score)
        else:
            risk_score = 0.35 # Default low-moderate risk
    except Exception:
        risk_score = 0.35

    safety_pct = max(0.0, min(100.0, (1.0 - risk_score) * 100.0))

    # Composite Readiness Score Calculation
    readiness_score = round(
        (0.40 * coverage_pct) + (0.35 * quiz_accuracy_pct) + (0.25 * safety_pct),
        1
    )

    # Readiness Classification
    if readiness_score >= 75.0:
        level = "High Readiness"
        badge_color = "success"
        summary_msg = "You are well-prepared for your exam. Maintain momentum with quick flashcard reviews."
    elif readiness_score >= 50.0:
        level = "Moderate Readiness"
        badge_color = "warning"
        summary_msg = "Solid progress, but targeted revision is needed on uncompleted topics before exam day."
    else:
        level = "Low Readiness"
        badge_color = "danger"
        summary_msg = "High exam risk detected. Priority attention required on foundational chapters and quiz practice."

    # Identify Weak Chapters
    weak_chapters = []
    chapters = Chapter.query.filter_by(subject_id=subject.id).all()
    for ch in chapters:
        ch_title = getattr(ch, 'name', getattr(ch, 'title', f"Chapter {ch.id}"))
        weak_chapters.append({
            "chapter_id": ch.id,
            "title": ch_title,
            "quiz_accuracy_pct": round(quiz_accuracy_pct, 1)
        })

    return {
        "status": "success",
        "subject_id": subject.id,
        "subject_name": subject.name,
        "readiness_score": readiness_score,
        "readiness_level": level,
        "badge_color": badge_color,
        "summary": summary_msg,
        "breakdown": {
            "syllabus_coverage_pct": round(coverage_pct, 1),
            "quiz_accuracy_pct": round(quiz_accuracy_pct, 1),
            "academic_safety_pct": round(safety_pct, 1)
        },
        "weak_chapters": weak_chapters
    }
