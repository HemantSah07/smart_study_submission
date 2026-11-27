from flask import Blueprint, render_template, request, flash, redirect, url_for, session, jsonify, current_app
from flask_login import login_required, current_user
from app.models import (Prediction, StudyLog, Goal, Subject, AssessmentQuestion, 
                        StudentAssessment, AssessmentResponse, AcademicDocument, 
                        ExtractedMark, StudentProfile, Schedule, Assignment, StudyPlan,
                        Chapter, Topic, Subtopic, LearningMaterial, Flashcard, QuizScore, 
                        StudentNote, LearningProgress, AvailabilitySlot, AIStudyMaterial,
                        SubjectPerformanceHistory, StudentSubject,
                        ReviewedChapter, ChapterQuizScore, BookmarkedChapter, ChapterNote, PastQuestion,
                        StudentSeenQuestion, TopicSeenQuestion, ChapterQuizResult)
from app import db
from datetime import date, datetime, time, timedelta
import joblib
import os
import shutil
import numpy as np
from app.utils.ocr_processor import MarksheetProcessor
from werkzeug.utils import secure_filename
import json
import re
import io
from difflib import SequenceMatcher
from app.utils.planner_generator import generate_study_planner
from app.utils.timezone_utils import local_now_for_user, local_today_for_user, default_timezone_for_country, MULTI_TIMEZONE_OPTIONS
from app.services.ai_service import (
    ai_service,
    AIServiceError,
    QuotaExceededError,
    RateLimitError,
    ConfigurationError,
    FEATURE_ASSISTANT,
    FEATURE_MCQ,
)
import logging

logger = logging.getLogger(__name__)

# ── Centralized Student Learning Context ──────────────────────────────────────
# Single source of truth for all student data. Every module reads from and
# writes to this context instead of issuing independent, isolated DB queries.
from app.context.learning_context import get_learning_context

student_bp = Blueprint("student", __name__)

# ── Country → Curriculum mapping (internal only, never shown to user) ─────────
COUNTRY_CURRICULUM_MAP = {
    "Nepal":           "NEB/CTEVT",
    "United States":   "US Common Core/AP",
    "United Kingdom":  "A-Levels/GCSE",
    "South Korea":     "CSAT/National",
    "China":           "Gaokao/National",
    "Germany":         "Abitur/National",
    "Australia":       "HSC/VCE/SACE",
    "Canada":          "Provincial/IB",
    "Japan":           "NSAT/National",
    "Switzerland":     "Matura/National",
    "Singapore":       "A-Levels/IB",
    "Finland":         "Matriculation/National",
    "Netherlands":     "VWO/HAVO",
    "Sweden":          "Gymnasieexamen",
    "Denmark":         "STX/HHX/HTX",
    "Norway":          "Vitnemål",
    "Ireland":         "Leaving Certificate",
    "Belgium":         "CESS/National",
    "France":          "Baccalauréat",
    "Italy":           "Maturità",
    "India":           "CBSE/ICSE/State Boards",
}

# ── Nepal Faculty → Subject-DB level+program mapping (replaced by DB query) ───
# All curriculum mapping is now resolved dynamically from database entries.

SUBJECT_NAME_ALIASES = {
    "scienceandtechnology": "science",
    "socialstudiesandpopulationeducation": "socialstudies",
    "environmentpopulationandhealth": "healthandpopulation",
    "environmenthealthandpopulation": "healthandpopulation",
    "healthphysicalandcreativearts": "healthandpopulation",
    "healthandphysicaleducation": "healthandpopulation",
    "healthphysicaleducation": "healthandpopulation",
    "computer": "computerscience",
    "optionalmath": "optionalmathematics",
    "optmath": "optionalmathematics",
}


def normalize_subject_name(value):
    key = re.sub(r"[^a-z0-9]+", "", (value or "").lower())
    return SUBJECT_NAME_ALIASES.get(key, key)


def _dedupe_subjects_by_name(subjects):
    deduped = []
    seen = set()
    for subject in subjects or []:
        if not subject:
            continue
        key = normalize_subject_name(subject.name)
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(subject)
    return deduped


def _is_fixed_nepal_class(profile):
    if not profile:
        return False
    country = (profile.country or "Nepal").strip()
    study_level = (profile.study_level or "").strip()
    return country == "Nepal" and study_level in ("Class 6", "Class 7", "Class 8", "Class 9", "Class 10")


def get_valid_subjects_for_profile(profile):
    """
    Returns the list of active Subject objects valid for this student's
    country + study_level + program + semester combination.
    Loads dynamically from database-backed curriculum tables (CurriculumProgram & ProgramSubject).
    """
    if not profile:
        return []

    from app.models import CurriculumProgram, ProgramSubject

    country     = (profile.country     or "Nepal").strip()
    study_level = (profile.study_level or "").strip()
    program     = (profile.program     or "").strip()
    semester    = (profile.semester    or "").strip()
    curriculum  = COUNTRY_CURRICULUM_MAP.get(country, "National")

    # 1. Query database single source of truth: CurriculumProgram & ProgramSubject
    if program and study_level:
        prog_rec = CurriculumProgram.query.filter_by(
            name=program, level_name=study_level, is_active=True
        ).first()
        if not prog_rec:
            prog_rec = CurriculumProgram.query.filter(
                CurriculumProgram.name.ilike(program),
                CurriculumProgram.is_active == True
            ).first()

        if prog_rec:
            query = db.session.query(Subject).join(
                ProgramSubject, Subject.id == ProgramSubject.subject_id
            ).filter(
                ProgramSubject.program_id == prog_rec.id,
                ProgramSubject.is_active == True,
                Subject.is_active == True
            )
            if semester:
                sem_query = query.filter(
                    (ProgramSubject.semester == semester) | (Subject.semester == semester)
                )
                sem_subjects = sem_query.order_by(ProgramSubject.sort_order, Subject.name).all()
                if sem_subjects:
                    return _dedupe_subjects_by_name(sem_subjects)

            subjects = query.order_by(ProgramSubject.sort_order, Subject.name).all()
            if subjects:
                return _dedupe_subjects_by_name(subjects)

    # 2. Query Subject table directly for active subjects matching level, program, country
    query = Subject.query.filter_by(
        level_of_study=study_level,
        program=program,
        country=country,
        is_active=True
    )
    if semester:
        sem_subs = query.filter_by(semester=semester).all()
        if sem_subs:
            return _dedupe_subjects_by_name(sem_subs)

    subjects = query.all()

    # 3. If no subjects found for specific program, look for general/empty program subjects for this level and country
    if not subjects:
        subjects = Subject.query.filter(
            Subject.level_of_study == study_level,
            Subject.country == country,
            Subject.is_active == True,
            (Subject.program == "General") | (Subject.program == None) | (Subject.program == "")
        ).all()

    # 4. Fallback: look for level/program match ignoring country constraint or with country=None
    if not subjects:
        subjects = Subject.query.filter(
            Subject.level_of_study == study_level,
            Subject.is_active == True,
            (Subject.program == program) | (Subject.program == "General") | (Subject.program == None) | (Subject.program == "")
        ).filter(
            (Subject.country == country) | (Subject.country == None)
        ).all()

    # 5. If still empty, seed placeholders dynamically using canonical names
    if not subjects:
        subjects = _seed_placeholder_subjects(country, study_level, program, curriculum)

    return _dedupe_subjects_by_name(subjects)


def _seed_placeholder_subjects(country, study_level, program, curriculum):
    """
    Inserts generic placeholder Subject rows for country+level+program
    combos not yet in the DB, then returns them.
    This keeps the subject picker functional for any combination.
    """
    lvl = study_level
    prog = program or "General"
    prefix = f"{country[:3].upper()}-{lvl[:3].upper().replace(' ', '')}-{prog[:3].upper()}"

    if lvl in ["Bachelors", "Masters"]:
        if prog and prog not in ["", "General"]:
            names = [f"{prog} Core I", f"{prog} Core II", f"{prog} Core III", "Research Methodology", "Elective Course"]
        else:
            names = ["Major Core I", "Major Core II", "Research Methods", "Elective I", "Elective II"]
        db_level = "Bachelors" if lvl == "Bachelors" else "Masters"
        db_prog  = prog
    elif lvl in ["Class 11", "Class 12"]:
        names = ["Mathematics", "English", "Core Subject I", "Core Subject II", "Optional Subject"]
        db_level = lvl
        db_prog  = prog
    else:
        names = ["Mathematics", "Science", "English", "Social Studies",
                 "Nepali" if country == "Nepal" else "Second Language"]
        db_level = lvl
        db_prog  = "General"

    placeholders = []
    for i, name in enumerate(names, 1):
        code = f"{prefix}-{i}"
        existing = Subject.query.filter_by(code=code).first()
        if existing:
            placeholders.append(existing)
            continue
        sub = Subject(
            code=code,
            name=name,
            level_of_study=db_level,
            program=db_prog,
            country=country,
            curriculum=curriculum,
            credit_hours=3,
            difficulty_level=3,
            is_active=True,
        )
        db.session.add(sub)
        placeholders.append(sub)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
    return placeholders


def get_subject_performance_snapshot(user_id, subject_id):
    """
    Retrieves the assessment/performance score (0-100) for a student and subject.
    Sources:
    1. Latest ExtractedMark for this subject (from uploaded marksheets).
    2. Latest StudentAssessment (quiz) score and/or Chapter quiz scores.
    Missing data returns None so the predictor can disable that subject.
    """
    subj = Subject.query.get(subject_id)
    if subj:
        latest_mark = (
            ExtractedMark.query
            .join(AcademicDocument)
            .filter(AcademicDocument.student_id == user_id)
            .filter((ExtractedMark.subject_name_mapped == subj.name) | (ExtractedMark.subject_name_original == subj.name))
            .order_by(AcademicDocument.uploaded_at.desc())
            .first()
        )
        if latest_mark and latest_mark.percentage is not None:
            return {
                "score": max(0.0, min(100.0, float(latest_mark.percentage))),
                "source": "marksheet",
                "source_label": "from marksheet",
            }

    assessment_score = None
    latest_quiz = (
        StudentAssessment.query
        .filter_by(student_id=user_id, subject_id=subject_id)
        .order_by(StudentAssessment.completed_at.desc())
        .first()
    )
    if latest_quiz:
        if getattr(latest_quiz, 'weighted_score', 0) > 0:
            assessment_score = latest_quiz.weighted_score
        else:
            assessment_score = latest_quiz.total_score

    chapter_quizzes = ChapterQuizScore.query.join(Topic).join(Chapter).filter(
        ChapterQuizScore.student_id == user_id,
        Chapter.subject_id == subject_id
    ).all()
    avg_chapter_score = None
    if chapter_quizzes:
        percentages = [(cs.score / cs.total_questions) * 100.0 for cs in chapter_quizzes]
        avg_chapter_score = sum(percentages) / len(percentages)

    final_quiz_score = None
    source_label = ""
    if assessment_score is not None and avg_chapter_score is not None:
        final_quiz_score = (assessment_score + avg_chapter_score) / 2.0
        source_label = "from assessment & chapter quizzes"
    elif assessment_score is not None:
        final_quiz_score = assessment_score
        source_label = "from assessment"
    elif avg_chapter_score is not None:
        final_quiz_score = avg_chapter_score
        source_label = "from chapter quizzes"

    if final_quiz_score is not None:
        return {
            "score": max(0.0, min(100.0, float(final_quiz_score))),
            "source": "assessment",
            "source_label": source_label,
        }

    return {
        "score": None,
        "source": "missing",
        "source_label": "No assessment",
    }


def get_subject_performance_score(user_id, subject_id):
    return get_subject_performance_snapshot(user_id, subject_id)["score"]

def get_subject_profile_details(user_id, subject_id, subject_name):
    score = get_subject_performance_score(user_id, subject_id)
    today_local = local_today_for_user(user_id)
    
    attendance = 85.0
    study_hours = 6.0
    days_until_exam = 30
    
    try:
        hist = SubjectPerformanceHistory.query.filter_by(
            user_id=user_id, subject_name=subject_name
        ).order_by(SubjectPerformanceHistory.logged_at.desc()).first()
        if hist:
            if hist.attendance is not None:
                attendance = float(hist.attendance)
            if hist.study_hours is not None:
                study_hours = float(hist.study_hours)
            if hist.days_until_exam is not None:
                days_until_exam = int(hist.days_until_exam)
    except Exception:
        pass

    try:
        from app.models import Exam
        upcoming_exam = Exam.query.filter(
            Exam.user_id == user_id,
            Exam.subject_id == subject_id,
            Exam.date >= today_local
        ).order_by(Exam.date.asc()).first()
        if upcoming_exam and upcoming_exam.date:
            days_until_exam = max(1, min(365, (upcoming_exam.date - today_local).days))
    except Exception:
        pass

    return {
        "score": score,
        "attendance": attendance,
        "study_hours": study_hours,
        "days_until_exam": days_until_exam
    }

def grade_from_score(score):
    if score >= 90.0: return "A"
    if score >= 85.0: return "A-"
    if score >= 80.0: return "B+"
    if score >= 75.0: return "B"
    if score >= 70.0: return "B-"
    if score >= 65.0: return "C+"
    if score >= 60.0: return "C"
    if score >= 50.0: return "C-"
    return "F"


def latest_prediction_rows(user_id):
    """Return one latest prediction row per subject from raw_inputs JSON."""
    latest_by_subject = {}
    predictions = Prediction.query.filter_by(user_id=user_id).order_by(Prediction.date.desc()).all()
    for pred in predictions:
        try:
            raw = json.loads(pred.raw_inputs or "{}")
        except Exception:
            raw = {}
        subject_name = raw.get("subject_name")
        if not subject_name or subject_name in latest_by_subject:
            continue
        latest_by_subject[subject_name] = {
            "subject_name": subject_name,
            "subject_id": raw.get("subject_id"),
            "performance_score": float(raw.get("performance_score", pred.avg_exam_score_pct or 0.0)),
            "attendance": float(raw.get("attendance", pred.attendance_pct or 90.0)),
            "weekly_study_hours": float(raw.get("weekly_study_hours", pred.weekly_study_hours or 14.0)),
            "subject_difficulty": float(raw.get("subject_difficulty", pred.subject_difficulty or 3.0)),
            "days_until_exam": int(raw.get("days_until_exam", 30)),
            "days_since_last_studied": int(raw.get("days_since_last_studied", 7)),
            "risk_score": float(raw.get("risk_score", 0.5)),
            "risk_pct": float(raw.get("risk_pct", 50.0)),
            "risk_level": pred.predicted_risk_level,
            "prediction_result": ["Pass", "At Risk", "Fail"][{"low": 0, "medium": 1, "high": 2}.get(pred.predicted_risk_level, 1)],
        }
    return list(latest_by_subject.values())


def load_ml_model(model_name):
    path = os.path.join(os.path.abspath(os.path.dirname(__file__)), '../../models', f'{model_name}.pkl')
    try:
        return joblib.load(path)
    except Exception:
        return None


def get_level_slug(lvl_string):
    if not lvl_string:
        return "bachelors"
    lvl = lvl_string.lower()
    if "class 8" in lvl:
        return "class8"
    elif "see" in lvl or "class 10" in lvl:
        return "see"
    elif "class 11" in lvl:
        return "class11"
    elif "class 12" in lvl:
        return "class12"
    elif "bachelor" in lvl:
        return "bachelors"
    elif "master" in lvl:
        return "masters"
    return "bachelors"


def calculate_subject_hour_allocations(subjects_info, total_available_hours):
    """
    Shared hour allocation calculation for ML Predictor and Study Planner.
    Applies a 0.5-hour floor per subject first, then redistributes the remaining
    pool across subjects proportional to their risk score & difficulty weights.
    Uses the largest-remainder method (Hamilton/Hare-Niemeyer) for 1-decimal
    rounding so the sum of allocations matches total_available_hours exactly.
    """
    if not subjects_info:
        return {}

    total_avail = max(0.0, float(total_available_hours or 0.0))
    if total_avail <= 0:
        return {(s.get("name") or s.get("subject_name") or s.get("subject")): 0.0 for s in subjects_info if (s.get("name") or s.get("subject_name") or s.get("subject"))}

    valid_subjects = []
    seen_names = set()
    for s in subjects_info:
        name = s.get("name") or s.get("subject_name") or s.get("subject")
        if not name or name in seen_names:
            continue
        seen_names.add(name)
        diff = float(s.get("difficulty") or s.get("subject_difficulty") or 3.0)
        risk_score = float(s.get("risk_score") if s.get("risk_score") is not None else 0.5)
        perf_score = s.get("previous_grade") or s.get("performance_score") or s.get("score")

        base_weight = 1.0 + (diff * 0.3)
        risk_weight = risk_score * (diff * 0.7)
        gap_weight = max(0.0, (100.0 - float(perf_score)) / 100.0) * 0.5 if perf_score is not None else 0.2

        tw = max(0.1, base_weight + risk_weight + gap_weight)
        valid_subjects.append({
            "name": name,
            "weight": tw
        })

    num_subjects = len(valid_subjects)
    if num_subjects == 0:
        return {}

    # If total pool is less than (num_subjects * 0.5), divide total_avail equally with largest-remainder rounding
    if total_avail < (num_subjects * 0.5):
        raw_share = total_avail / num_subjects
        base_allocs = {}
        remainders = []
        for vs in valid_subjects:
            base = float(int(raw_share * 10)) / 10.0
            rem = raw_share - base
            base_allocs[vs["name"]] = base
            remainders.append((rem, vs["name"]))

        target_tenths = int(round(total_avail * 10))
        if total_avail > 0 and target_tenths == 0:
            target_tenths = 1
        current_tenths = int(round(sum(base_allocs.values()) * 10))
        missing_tenths = max(0, target_tenths - current_tenths)

        remainders.sort(key=lambda x: x[0], reverse=True)
        for i in range(min(missing_tenths, len(remainders))):
            name = remainders[i][1]
            base_allocs[name] = round(base_allocs[name] + 0.1, 1)

        return base_allocs

    # Pass 1: Unrounded raw allocation (0.5h floor + weighted share of remaining pool)
    floor = 0.5
    remaining_pool = total_avail - (num_subjects * floor)
    sum_weights = sum(vs["weight"] for vs in valid_subjects) or 1.0

    raw_allocs = {}
    base_allocs = {}
    remainders = []

    for vs in valid_subjects:
        name = vs["name"]
        raw_val = floor + (vs["weight"] / sum_weights) * remaining_pool
        raw_allocs[name] = raw_val
        base_val = float(int(raw_val * 10)) / 10.0
        rem = raw_val - base_val
        base_allocs[name] = base_val
        remainders.append((rem, name))

    # Pass 2: Largest-remainder distribution for 1-decimal rounding alignment
    target_tenths = int(round(total_avail * 10))
    current_tenths = int(round(sum(base_allocs.values()) * 10))
    missing_tenths = max(0, target_tenths - current_tenths)

    remainders.sort(key=lambda x: x[0], reverse=True)
    for i in range(min(missing_tenths, len(remainders))):
        name = remainders[i][1]
        base_allocs[name] = round(base_allocs[name] + 0.1, 1)

    return base_allocs


def derive_subject_difficulty(score_pct):
    """
    Single source of truth helper to derive 1-5 difficulty rating from
    assessment performance score percentage (matching 5-tier standard scale).
    """
    if score_pct is None:
        return 3.0
    try:
        score = float(score_pct)
        if score < 35.0: return 5.0      # Level 5 · Very Hard
        elif score < 50.0: return 4.0    # Level 4 · Hard
        elif score < 70.0: return 3.0    # Level 3 · Moderate
        elif score < 85.0: return 2.0    # Level 2 · Light
        else: return 1.0                 # Level 1 · Easy
    except (TypeError, ValueError):
        return 3.0


def get_subject_features(user_id, subject_name, input_grade, input_attendance, input_weekly_hours, input_difficulty, input_days_until_exam=30, input_days_since_last_studied=None):
    """Build the 7-feature vector used by the Random Forest model."""
    subject = Subject.query.filter_by(name=subject_name).first()
    subject_id = subject.id if subject else None
    today_local = local_today_for_user(user_id)

    # ── Feature 1: previous_grade ─────────────────────────────────────────────
    previous_grade = float(input_grade)

    # ── Feature 2: attendance ─────────────────────────────────────────────────
    attendance = float(input_attendance)

    # ── Feature 3: difficulty ─────────────────────────────────────────────────
    # Server-side recomputed from previous_grade for single source of truth
    difficulty = float(derive_subject_difficulty(previous_grade))
    if subject and subject.difficulty_level != int(difficulty):
        try:
            subject.difficulty_level = int(difficulty)
            db.session.add(subject)
            db.session.commit()
        except Exception:
            db.session.rollback()

    # ── Feature 4: study_hours (weekly) ──────────────────────────────────────
    study_hours = float(input_weekly_hours)

    # ── Feature 5: days_until_exam ────────────────────────────────────────────
    days_until_exam = int(input_days_until_exam) if input_days_until_exam is not None else 30
    # Try to derive from Exam table if possible
    if subject_id:
        try:
            from app.models import Exam
            upcoming_exams = Exam.query.filter(
                Exam.user_id == user_id,
                Exam.subject_id == subject_id,
                Exam.date >= today_local
            ).order_by(Exam.date.asc()).all()
            if upcoming_exams:
                days_until_exam = (upcoming_exams[0].date - today_local).days
        except Exception:
            pass
    days_until_exam = max(0, min(90, days_until_exam))

    # ── Feature 6: days_since_last_studied ────────────────────────────────────
    days_since_last_studied = int(input_days_since_last_studied) if input_days_since_last_studied is not None else 7
    if input_days_since_last_studied is None and subject_id:
        try:
            last_log = StudyLog.query.filter_by(
                user_id=user_id, subject_id=subject_id
            ).order_by(StudyLog.date.desc()).first()
            last_review = ReviewedChapter.query.join(Topic).join(Chapter).filter(ReviewedChapter.student_id == user_id, Chapter.subject_id == subject_id, ReviewedChapter.status == "completed").order_by(ReviewedChapter.last_accessed_at.desc()).first()
            if (last_log and last_log.date) or last_review:
                # last_review query already run above
                last_review_date = last_review.last_accessed_at.date() if (last_review and last_review.last_accessed_at) else None
                last_log_date = last_log.date if (last_log and last_log.date) else None
                most_recent_date = max(last_log_date, last_review_date) if (last_log_date and last_review_date) else (last_log_date or last_review_date)
                delta = today_local - most_recent_date if most_recent_date else timedelta(days=7)
                days_since_last_studied = max(0, delta.days)
        except Exception:
            pass
    days_since_last_studied = min(60, days_since_last_studied)

    # ── Feature 7: completion_rate (prior week plan vs actual) ────────────────
    completion_rate = 1.0  # optimistic default
    if subject_id:
        try:
            week_ago = today_local - timedelta(days=7)
            history = SubjectPerformanceHistory.query.filter(
                SubjectPerformanceHistory.user_id == user_id,
                SubjectPerformanceHistory.subject_name == subject_name,
                SubjectPerformanceHistory.week_start >= week_ago
            ).order_by(SubjectPerformanceHistory.logged_at.desc()).first()
            if history:
                completion_rate = float(history.completion_rate)
        except Exception:
            pass

    features = [
        previous_grade,          # 0: previous_grade
        attendance,              # 1: attendance
        difficulty,              # 2: difficulty
        study_hours,             # 3: study_hours
        float(days_until_exam),  # 4: days_until_exam
        float(days_since_last_studied),  # 5: days_since_last_studied
        completion_rate,         # 6: completion_rate
    ]
    return features



def get_level_slug(lvl_string):
    """Convert a study_level string to a model filename slug."""
    if not lvl_string:
        return "bachelors"
    lvl_lower = lvl_string.lower()
    if "class 6" in lvl_lower or "class 7" in lvl_lower:
        return "see"   # use same model as lower school
    if "class 8" in lvl_lower:
        return "class8"
    if "class 9" in lvl_lower:
        return "see"
    if "class 10" in lvl_lower or "see" in lvl_lower:
        return "see"
    if "class 11" in lvl_lower:
        return "class11"
    if "class 12" in lvl_lower or "neb" in lvl_lower:
        return "class12"
    if lvl_lower == "bachelors" or "bachelor" in lvl_lower:
        return "bachelors"
    if lvl_lower == "masters" or "master" in lvl_lower:
        return "masters"
    if "university" in lvl_lower or "year" in lvl_lower:
        return "bachelors"
    return "bachelors"


def get_profile_subjects(profile):
    """Return subjects the student has selected, seeding from valid curriculum if none yet."""
    if not profile:
        return []

    from app.models import StudentSubject

    if not profile.study_level:
        return []

    valid_subs = get_valid_subjects_for_profile(profile)
    valid_by_key = {normalize_subject_name(s.name): s for s in valid_subs}
    valid_by_id = {s.id: s for s in valid_subs}
    enforce_full_curriculum = _is_fixed_nepal_class(profile)

    user_subs = StudentSubject.query.filter_by(user_id=profile.user_id).all()
    selected_subjects = []
    seen_keys = set()
    changed = False

    for mapping in user_subs:
        subject = mapping.subject
        if not subject:
            db.session.delete(mapping)
            changed = True
            continue

        key = normalize_subject_name(subject.name)
        canonical_subject = valid_by_key.get(key)
        if not canonical_subject or key in seen_keys:
            db.session.delete(mapping)
            changed = True
            continue

        if mapping.subject_id != canonical_subject.id:
            mapping.subject_id = canonical_subject.id
            changed = True

        selected_subjects.append(canonical_subject)
        seen_keys.add(key)

    if enforce_full_curriculum:
        for subject in valid_subs:
            key = normalize_subject_name(subject.name)
            if key in seen_keys:
                continue
            db.session.add(StudentSubject(user_id=profile.user_id, subject_id=subject.id))
            selected_subjects.append(subject)
            seen_keys.add(key)
            changed = True

    if selected_subjects:
        if changed:
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
        return _dedupe_subjects_by_name(selected_subjects)

    for ds in valid_subs:
        if ds.id in valid_by_id:
            mapping = StudentSubject(user_id=profile.user_id, subject_id=ds.id)
            db.session.add(mapping)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()

    return valid_subs

@student_bp.route("/dashboard")
@login_required
def dashboard():
    if current_user.role != 'student':
        return redirect(url_for('admin.dashboard'))

    # ── Context: read all data via the shared analytics service (avoids duplicate queries)
    ctx = get_learning_context(current_user.id)
    from app.services.analytics_service import StudentAnalyticsService
    analytics = StudentAnalyticsService(current_user.id)

    # Subject hours chart — read from context
    subject_hours = ctx.subject_hours_chart
    chart_labels = list(subject_hours.keys())
    chart_data = list(subject_hours.values())
    total_scheduled = sum(chart_data)

    # Risk counts — read from context
    risk = ctx.schedule_risk_counts
    high_risk, medium_risk, low_risk = risk["high"], risk["medium"], risk["low"]

    # Today's tasks — read from context
    today_slots = ctx.current_tasks
    today_idx = local_now_for_user(current_user.id).weekday()

    # Study hours & streak — read from context
    logged_hours = ctx.study_hours
    streak = ctx.streak

    # Run study log analysis against planner targets
    from app.utils.log_analyzer import analyze_student_logs
    log_analysis = None
    try:
        log_analysis = analyze_student_logs(current_user.id)
    except Exception:
        pass

    # Bookmarked chapters recommendation if days_until_exam is under 7 days
    from app.models import Exam, BookmarkedChapter
    today_local = local_today_for_user(current_user.id)
    week_away = today_local + timedelta(days=7)
    
    upcoming_exams = Exam.query.filter(
        Exam.user_id == current_user.id,
        Exam.date >= today_local,
        Exam.date <= week_away
    ).all()
    urgent_subject_ids = [ex.subject_id for ex in upcoming_exams]
    
    recommended_review_bookmarks = []
    if urgent_subject_ids:
        recommended_review_bookmarks = BookmarkedChapter.query.join(Topic).join(Chapter).filter(
            BookmarkedChapter.student_id == current_user.id,
            Chapter.subject_id.in_(urgent_subject_ids)
        ).all()
        
    recent_study_history = ReviewedChapter.query.filter_by(
        student_id=current_user.id
    ).order_by(ReviewedChapter.last_accessed_at.desc()).limit(5).all()

    # Weekly commitments category summary widget
    slots = AvailabilitySlot.query.filter_by(user_id=current_user.id).all()
    commitment_summary = {}
    for s in slots:
        cat = s.category or s.slot_type or "Other"
        try:
            sh = int(s.start_time.split(":")[0]) * 60 + int(s.start_time.split(":")[1])
            eh = int(s.end_time.split(":")[0]) * 60 + int(s.end_time.split(":")[1])
            dur = ((1440 - sh) + eh) / 60.0 if sh > eh else (eh - sh) / 60.0
        except Exception:
            dur = 0.0
        commitment_summary[cat] = commitment_summary.get(cat, 0.0) + dur
    for cat in list(commitment_summary.keys()):
        commitment_summary[cat] = round(commitment_summary[cat], 1)
    available_study_hours = round(get_available_study_hours_total(current_user.id), 1)

    # Get compact assessment summary
    summary = analytics.assessment_summary(limit=3)

    # Trigger smart real-time notifications
    unread_notifications = []
    try:
        from app.services.notification_service import generate_student_notifications, get_unread_notifications
        generate_student_notifications(current_user.id)
        unread_notifications = get_unread_notifications(current_user.id)
    except Exception as ne:
        print(f"[Notifications Error]: {ne}")

    return render_template("student/dashboard.html",
                           user=current_user,
                           profile=ctx.profile,
                           today_idx=today_idx,
                           logged_hours=logged_hours,
                           log_analysis=log_analysis,
                           streak=streak,
                           commitment_summary=commitment_summary,
                           available_study_hours=available_study_hours,
                           chart_labels=chart_labels,
                           chart_data=chart_data,
                           total_scheduled=total_scheduled,
                           risk_data=[high_risk, medium_risk, low_risk],
                           today_slots=today_slots,
                           recommended_review_bookmarks=recommended_review_bookmarks,
                           recent_study_history=recent_study_history,
                           unread_notifications=unread_notifications,
                           recent_assessments=summary["recent"],
                           overall_stats={
                               "total_attempted": summary["total_attempted"],
                               "correct": summary["total_correct"],
                               "incorrect": summary["total_incorrect"],
                               "accuracy": summary["accuracy"]
                           })

@student_bp.route("/api/notifications/mark-read/<int:notif_id>", methods=["POST"])
@login_required
def api_mark_notification_read(notif_id):
    from app.services.notification_service import mark_notification_as_read
    ok = mark_notification_as_read(notif_id, current_user.id)
    return jsonify({"status": "success" if ok else "error"}), 200


@student_bp.route("/api/notifications/mark-all-read", methods=["POST"])
@login_required
def api_mark_all_notifications_read():
    from app.services.notification_service import mark_all_notifications_as_read
    mark_all_notifications_as_read(current_user.id)
    return jsonify({"status": "success"}), 200


@student_bp.route("/api/flashcards/review", methods=["POST"])
@login_required
def api_flashcard_review():
    data = request.get_json() or {}
    flashcard_id = data.get("flashcard_id")
    quality_rating = data.get("quality_rating")
    user_answer = data.get("user_answer")

    if not flashcard_id:
        return jsonify({"status": "error", "message": "Missing flashcard_id"}), 400

    try:
        from app.services.spaced_repetition import process_sm2_review
        res = process_sm2_review(
            user_id=current_user.id,
            flashcard_id=int(flashcard_id),
            quality_rating=int(quality_rating) if quality_rating is not None else None,
            user_answer=str(user_answer) if user_answer else None
        )
        return jsonify(res), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400


@student_bp.route("/api/study-log/auto-add", methods=["POST"])
@login_required
def api_study_log_auto_add():
    from datetime import date
    data = request.get_json() or {}
    subject_id = data.get("subject_id")
    duration_minutes = float(data.get("duration_minutes", 25.0))
    hours = round(duration_minutes / 60.0, 2)

    from app.models import StudyLog, Notification, Subject
    today = date.today()

    if not subject_id:
        sub = Subject.query.first()
        subject_id = sub.id if sub else 1

    log = StudyLog(
        user_id=current_user.id,
        subject_id=subject_id,
        duration_hours=hours,
        date=today,
        notes=f"Auto-logged via {int(duration_minutes)}-minute Pomodoro focus session."
    )
    db.session.add(log)

    # Dismiss missing study log notifications
    try:
        Notification.query.filter(
            Notification.user_id == current_user.id,
            Notification.message.like("%No study hours logged yesterday%")
        ).update({"is_read": True}, synchronize_session=False)
    except Exception:
        pass

    db.session.commit()

    return jsonify({
        "status": "success",
        "message": f"Successfully logged {hours}h study time!",
        "logged_hours": hours
    })


@student_bp.route("/api/quiz/generate-weak-spots", methods=["POST"])
@login_required
def api_generate_weak_spot_quiz():
    data = request.get_json() or {}
    subject_id = data.get("subject_id")
    try:
        from app.services.weak_spot_quiz import generate_weak_spot_quiz
        res = generate_weak_spot_quiz(current_user.id, int(subject_id) if subject_id else None)
        return jsonify(res), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400


@student_bp.route("/api/knowledge-graph/<int:subject_id>", methods=["GET"])
@login_required
def api_knowledge_graph(subject_id):
    from app.services.knowledge_graph import build_subject_graph
    res = build_subject_graph(current_user.id, subject_id)
    return jsonify(res), 200


@student_bp.route("/api/exam-readiness/<int:subject_id>", methods=["GET"])
@login_required
def api_exam_readiness(subject_id):
    from app.services.exam_readiness import generate_exam_readiness_score
    res = generate_exam_readiness_score(current_user.id, subject_id)
    return jsonify(res), 200


@student_bp.route("/evaluation", methods=["GET", "POST"])
@login_required
def evaluation():
    flash("The legacy ML Evaluation simulator has been replaced by the Random Forest Predictor.", "info")
    return redirect(url_for("student.predict"))

    profile = StudentProfile.query.filter_by(user_id=current_user.id).first()
    if request.method == "POST":
        try:
            features = [
                float(request.form.get("attendance_pct", 0)),
                float(request.form.get("assignment_completion_pct", 0)),
                float(request.form.get("weekly_study_hours", 0)),
                float(request.form.get("total_logged_study_hours", 0)),
                int(request.form.get("study_days_last_240", 0)),
                float(request.form.get("subject_difficulty", 0)),
                float(request.form.get("avg_exam_score_pct", 0)),
                float(request.form.get("midterm_score_pct", 0)),
                float(request.form.get("final_score_pct", 0)),
                float(request.form.get("assignment_avg_pct", 0)),
                int(request.form.get("year_of_study", 1)),
                float(request.form.get("cumulative_gpa", 0))
            ]

            model = load_ml_model("random_forest")
            scaler = load_ml_model('scaler')
            
            if model and scaler:
                f_array = np.array([features])
                f_scaled = scaler.transform(f_array)
                risk_pred = model.predict(f_scaled)[0]
                
                # Dynamic and realistic predicted grade calculation
                gpa = features[11]
                avg_exam = features[6]
                assignments = features[1]
                attendance = features[0]
                
                # Weight elements realistically to estimate academic score (0-100)
                perf_score = 0.4 * (gpa * 25.0) + 0.3 * avg_exam + 0.2 * assignments + 0.1 * attendance
                
                if perf_score >= 90.0:
                    predicted_grade = "A"
                elif perf_score >= 85.0:
                    predicted_grade = "A-"
                elif perf_score >= 80.0:
                    predicted_grade = "B+"
                elif perf_score >= 75.0:
                    predicted_grade = "B"
                elif perf_score >= 70.0:
                    predicted_grade = "B-"
                elif perf_score >= 65.0:
                    predicted_grade = "C+"
                elif perf_score >= 60.0:
                    predicted_grade = "C"
                elif perf_score >= 50.0:
                    predicted_grade = "C-"
                else:
                    predicted_grade = "F"
                    
                risk_level = ["low", "medium", "high"][min(2, max(0, int(risk_pred)))]
            else:
                risk_level = "medium"
                predicted_grade = "B"
                flash("Model not trained yet, using placeholder prediction.", "warning")
            
            pred_record = Prediction(
                user_id=current_user.id,
                attendance_pct=features[0],
                assignment_completion_pct=features[1],
                weekly_study_hours=features[2],
                total_logged_study_hours=features[3],
                study_days_last_240=features[4],
                subject_difficulty=features[5],
                avg_exam_score_pct=features[6],
                midterm_score_pct=features[7],
                final_score_pct=features[8],
                assignment_avg_pct=features[9],
                year_of_study=features[10],
                cumulative_gpa=features[11],
                predicted_risk_level=risk_level,
                predicted_grade=predicted_grade
            )
            db.session.add(pred_record)
            db.session.commit()
            
            flash("Prediction generated successfully!", "success")
        except Exception as e:
            flash(f"Error making prediction: {str(e)}", "danger")
            
    past_predictions = Prediction.query.filter_by(user_id=current_user.id).order_by(Prediction.date.desc()).all()
    docs = AcademicDocument.query.filter_by(student_id=current_user.id).order_by(AcademicDocument.uploaded_at.desc()).all()
    latest_prediction = past_predictions[0] if past_predictions else None
    avg_confidence = (
        round(sum(d.extraction_confidence for d in docs) / len(docs) * 100, 1) if docs else 0
    )
    return render_template(
        "student/evaluation.html",
        past_predictions=past_predictions,
        latest_prediction=latest_prediction,
        profile=profile,
        documents=docs,
        doc_count=len(docs),
        avg_confidence=avg_confidence,
    )

@student_bp.route("/study_log", methods=["GET", "POST"])
@student_bp.route("/study-log", methods=["GET", "POST"])
@login_required
def study_log():

    # ── Context: shared learning state for this request
    ctx = get_learning_context(current_user.id)

    if request.method == "POST":
        duration = request.form.get("duration_hours")
        notes_text = request.form.get("notes")
        subject_id = request.form.get("subject_id")

        if duration:
            # If a specific subject was chosen by id, log by name lookup;
            # otherwise fall back to direct DB insert with subject_id
            subj_name = None
            sub_id_int = None
            if subject_id and subject_id.isdigit():
                sub_id_int = int(subject_id)
                s = Subject.query.get(sub_id_int)
                subj_name = s.name if s else None

            if subj_name:
                # ── Context mutation: log_study_hours invalidates study_hours/streak/recent_activity
                log = StudyLog(
                    user_id=current_user.id,
                    date=local_today_for_user(current_user.id),
                    duration_hours=float(duration),
                    notes=notes_text,
                    subject_id=sub_id_int,
                )
                db.session.add(log)
                db.session.commit()
                # Invalidate context caches after direct write
                ctx._study_logs = None
                ctx._streak = None
                ctx._recent_activity = None
            else:
                log = StudyLog(
                    user_id=current_user.id,
                    date=local_today_for_user(current_user.id),
                    duration_hours=float(duration),
                    notes=notes_text,
                    subject_id=sub_id_int,
                )
                db.session.add(log)
                db.session.commit()
                ctx._study_logs = None
                ctx._streak = None
                ctx._recent_activity = None

            flash("Study log added!", "success")

    # Read from context — already aggregated, no extra queries
    logs = StudyLog.query.filter_by(user_id=current_user.id).order_by(StudyLog.date.desc()).all()
    total_logged = ctx.study_hours
    subjects = ctx.subjects

    return render_template("student/study_log.html", logs=logs, total_logged=total_logged, subjects=subjects)

# ── Study Planner Input Validation Constants ─────────────────────────────────────
MIN_ATTENDANCE_PCT = 0.0
MAX_ATTENDANCE_PCT = 100.0

MIN_DAYS_UNTIL_EXAM = 1
MAX_DAYS_UNTIL_EXAM = 365

MIN_STUDY_HOURS_PER_WEEK = 0.0
MAX_STUDY_HOURS_PER_WEEK = 84.0

ALLOWED_SESSION_LENGTHS = {30, 45, 60, 90, 120}

def validate_study_planner_subject_input(name, previous_grade, attendance, study_hours, days_until_exam, user_id=None):
    """
    Sanitizes and validates individual subject input fields for Study Planner.
    Returns (is_valid, sanitized_dict, error_message).
    """
    if not name or not str(name).strip():
        return False, None, "Subject selection is required."

    name = str(name).strip()

    # Validate subject exists globally or in user's curriculum
    subj_obj = Subject.query.filter_by(name=name).first()
    if not subj_obj:
        return False, None, f"Invalid subject selection '{name}'. Subject does not exist."

    # Validate previous grade
    try:
        grade = float(previous_grade)
        if grade < 0.0 or grade > 100.0:
            return False, None, f"Validation failed: Grade % for '{name}' must be between 0 and 100."
    except (TypeError, ValueError):
        return False, None, f"Validation failed: Invalid Grade % value for '{name}'."

    # Validate attendance %
    try:
        att = float(attendance)
        if att < MIN_ATTENDANCE_PCT or att > MAX_ATTENDANCE_PCT:
            return False, None, f"Validation failed: Attendance % for '{name}' must be between 0 and 100."
    except (TypeError, ValueError):
        return False, None, f"Validation failed: Invalid Attendance % value for '{name}'."

    # Validate current study hours / week
    try:
        hrs = float(study_hours)
        if hrs < MIN_STUDY_HOURS_PER_WEEK or hrs > MAX_STUDY_HOURS_PER_WEEK:
            return False, None, f"Validation failed: Study hrs/wk for '{name}' must be between 0 and 84."
    except (TypeError, ValueError):
        return False, None, f"Validation failed: Invalid Study hrs/wk value for '{name}'."

    # Validate days until exam (must be positive integer between 1 and 365)
    try:
        days_str = str(days_until_exam).strip()
        if not days_str.isdigit() or "." in days_str:
            return False, None, f"Validation failed: Days until exam for '{name}' must be a positive whole number between 1 and 365."
        days_int = int(days_str)
        if days_int < MIN_DAYS_UNTIL_EXAM or days_int > MAX_DAYS_UNTIL_EXAM:
            return False, None, f"Validation failed: Days until exam for '{name}' must be between {MIN_DAYS_UNTIL_EXAM} and {MAX_DAYS_UNTIL_EXAM} days."
    except (TypeError, ValueError):
        return False, None, f"Validation failed: Invalid Days until exam value for '{name}'."

    return True, {
        "name": name,
        "previous_grade": grade,
        "attendance": att,
        "study_hours": hrs,
        "days_until_exam": days_int,
    }, None

def validate_session_length(session_len_raw):
    """
    Validates session_length in minutes against allowed options {30, 45, 60, 90, 120}.
    Returns (is_valid, sanitized_int, error_message).
    """
    try:
        sess = int(session_len_raw)
        if sess in ALLOWED_SESSION_LENGTHS:
            return True, sess, None
        return False, None, f"Validation failed: Invalid session length '{session_len_raw}'. Allowed options: 30 min, 45 min, 60 min, 90 min, 2 h."
    except (TypeError, ValueError):
        return False, None, f"Validation failed: Invalid session length '{session_len_raw}'."


@student_bp.route("/schedule", methods=["GET"])
@login_required
def schedule():
    # ── Context: read schedule data from shared state
    ctx = get_learning_context(current_user.id)

    weekly_schedule = ctx.weekly_schedule
    risk = ctx.schedule_risk_counts
    total_week_hours = ctx.total_week_hours
    schedules = ctx._schedule_list  # reuse already-loaded list for count

    subjects = ctx.subjects
    today_idx = local_now_for_user(current_user.id).weekday()
    draft_subjects = session.pop("draft_schedule_form_data", None)

    return render_template(
        "student/schedule.html",
        weekly_schedule=weekly_schedule,
        subjects=subjects,
        today_idx=today_idx,
        total_week_hours=total_week_hours,
        schedule_count=len(schedules),
        risk_counts=risk,
        profile=ctx.profile,
        get_subject_performance_score=get_subject_performance_score,
        get_subject_profile_details=get_subject_profile_details,
        draft_subjects=draft_subjects,
    )

@student_bp.route("/api/risk-analysis", methods=["POST"])
@login_required
def risk_analysis():
    if request.is_json:
        data = request.json
        raw_subjects = data.get("subjects", [])
    else:
        subject_names = request.form.getlist("subject_name[]")
        previous_grades = request.form.getlist("previous_grade[]")
        attendances = request.form.getlist("attendance[]")
        study_hours = request.form.getlist("study_hours[]")
        difficulties = request.form.getlist("difficulty[]")
        exam_days_list = request.form.getlist("days_until_exam[]")
        
        raw_subjects = []
        for i in range(len(subject_names)):
            sname = subject_names[i]
            if not sname:
                return jsonify({"status": "error", "message": "Validation failed: Subject selection is required for all rows."}), 400
            if i >= len(previous_grades) or not str(previous_grades[i]).strip():
                return jsonify({"status": "error", "message": f"Validation failed: Grade % missing for subject '{sname}'."}), 400
            if i >= len(attendances) or not str(attendances[i]).strip():
                return jsonify({"status": "error", "message": f"Validation failed: Attendance % missing for subject '{sname}'."}), 400
            if i >= len(study_hours) or not str(study_hours[i]).strip():
                return jsonify({"status": "error", "message": f"Validation failed: Study hours missing for subject '{sname}'."}), 400
            if i >= len(exam_days_list) or not str(exam_days_list[i]).strip():
                return jsonify({"status": "error", "message": f"Validation failed: Days until exam missing for subject '{sname}'."}), 400

            raw_subjects.append({
                "name": sname,
                "previous_grade": previous_grades[i],
                "attendance": attendances[i],
                "study_hours": study_hours[i],
                "difficulty": difficulties[i] if i < len(difficulties) else 3.0,
                "days_until_exam": exam_days_list[i],
            })
            
    if not raw_subjects:
        return jsonify({"status": "error", "message": "No subjects provided for analysis."}), 400

    subjects_list = []
    # Server-side validation before ML prediction pipeline
    for s in raw_subjects:
        name = s.get("name")
        if not name:
            return jsonify({"status": "error", "message": "Validation failed: Subject selection is required for all rows."}), 400
        
        is_ok, sanitized, err_msg = validate_study_planner_subject_input(
            name=name,
            previous_grade=s.get("previous_grade", 70.0),
            attendance=s.get("attendance", 85.0),
            study_hours=s.get("study_hours", 6.0),
            days_until_exam=s.get("days_until_exam", 30),
            user_id=current_user.id
        )
        if not is_ok:
            return jsonify({"status": "error", "message": err_msg}), 400
        
        sanitized["difficulty"] = float(s.get("difficulty", 3.0))
        subjects_list.append(sanitized)
        
    model = load_ml_model('random_forest')
    scaler = load_ml_model('scaler')
    if not model or not scaler:
        return jsonify({"status": "error", "message": "ML Risk prediction models are not trained yet."}), 500
        
    results = []
    total_allocated_hours = 0.0
    
    for s in subjects_list:
        name = s.get("name")
        subj_obj = Subject.query.filter_by(name=name).first()
        real_grade = None
        if subj_obj:
            snap = get_subject_performance_snapshot(current_user.id, subj_obj.id)
            if snap["source"] != "missing" and snap["score"] is not None:
                real_grade = float(snap["score"])

        form_grade = float(s.get("previous_grade", 70.0))
        if real_grade is not None:
            grade = real_grade
            is_self_reported = False
        else:
            grade = form_grade
            is_self_reported = True

        diff = float(derive_subject_difficulty(grade))
        att = float(s.get("attendance", 85.0))
        hrs = float(s.get("study_hours", 6.0))
        exam_days = int(s.get("days_until_exam", 30))
        
        features = get_subject_features(current_user.id, name, grade, att, hrs, diff, exam_days)
        
        f_scaled = scaler.transform([features])

        # ── Use predict_proba for continuous risk score ───────────────────────
        risk_score = 0.5  # fallback
        risk_pred = 1     # fallback medium
        if hasattr(model, "predict_proba"):
            try:
                probs = model.predict_proba(f_scaled)[0]  # [P_low, P_med, P_high]
                # risk_score is the weighted mean: 0*P_low + 0.5*P_med + 1.0*P_high
                risk_score = float(0.0 * probs[0] + 0.5 * probs[1] + 1.0 * probs[2])
                risk_pred = int(np.argmax(probs))
            except Exception:
                risk_pred = int(model.predict(f_scaled)[0])
        else:
            risk_pred = int(model.predict(f_scaled)[0])

        # Boost risk score by 15% if last completion_rate < 0.7
        try:
            week_ago = local_today_for_user(current_user.id) - timedelta(days=7)
            history = SubjectPerformanceHistory.query.filter(
                SubjectPerformanceHistory.user_id == current_user.id,
                SubjectPerformanceHistory.subject_name == name,
                SubjectPerformanceHistory.week_start >= week_ago
            ).order_by(SubjectPerformanceHistory.logged_at.desc()).first()
            if history and history.completion_rate < 0.7:
                risk_score = min(1.0, risk_score * 1.15)
        except Exception:
            pass

        risk_pct = round(risk_score * 100, 1)
        
        risk_label = "Low"
        if risk_score >= 0.6:
            risk_label = "High"
        elif risk_score >= 0.35:
            risk_label = "Medium"
            
        results.append({
            "name": name,
            "difficulty": diff,
            "previous_grade": grade,
            "risk_numeric": risk_pred,
            "risk_level": risk_label,
            "risk_score": round(risk_score, 3),
            "risk_pct": risk_pct,
            "allocated_hours": 0.0,
        })

    available_hours = get_available_study_hours_total(current_user.id)
    allocations = calculate_subject_hour_allocations(results, available_hours)
    total_allocated_hours = 0.0

    for item in results:
        item["allocated_hours"] = allocations.get(item["name"], 2.0)
        total_allocated_hours += item["allocated_hours"]

    warning = ""
    if total_allocated_hours > available_hours:
        warning = f"⚠️ Alert: Recommended study hours ({round(total_allocated_hours, 1)} hrs) exceed your available weekly study slots ({round(available_hours, 1)} hrs). Please configure more study slots in your availability dashboard."

    return jsonify({
        "status": "success",
        "analysis": results,
        "total_allocated_hours": round(total_allocated_hours, 1),
        "available_hours": round(available_hours, 1),
        "warning": warning
    })


def _build_planner_advice(sd: dict, session_idx: int = 1, total_sessions: int = 1) -> str:
    """
    Return a context-aware, dynamic advice string for a planner schedule entry.
    Interpolates subject name, exact grade %, session sequence (Session X of Y),
    and a rotating study focus area so card text varies naturally.
    """
    name  = sd.get('name', 'Subject')
    raw_g = sd.get('grade') if sd.get('grade') is not None else sd.get('previous_grade', 70.0)
    grade = float(raw_g)
    att   = float(sd.get('attendance', 85.0))
    diff  = float(sd.get('difficulty', 3.0))
    risk  = int(sd.get('risk', 1))   # 0=Low, 1=Medium, 2=High

    grade_concern = max(0.0, (70.0 - grade) / 70.0) * 1.5
    att_concern   = max(0.0, (80.0 - att)   / 80.0) * 1.2
    diff_concern  = max(0.0, (diff - 3.0)   / 2.0)

    worst = max(grade_concern, att_concern, diff_concern)

    if worst == grade_concern and grade_concern > 0:
        weak_metric_phrase = f"low grade ({grade:.1f}%)"
    elif worst == att_concern and att_concern > 0:
        weak_metric_phrase = f"low attendance ({att:.1f}%)"
    elif diff_concern > 0:
        weak_metric_phrase = f"high difficulty level ({diff:.0f}/5)"
    else:
        weak_metric_phrase = None

    focus_areas = [
        "core concept drill & worked examples",
        "past paper practice & formula review",
        "weak topic flashcards & active recall",
        "timed problem solving & self-testing"
    ]
    focus = focus_areas[(session_idx - 1) % len(focus_areas)]

    seq_prefix = f"Session {session_idx}/{total_sessions} for {name}"

    if risk == 2:
        if weak_metric_phrase:
            return f"{seq_prefix}: High Risk due to {weak_metric_phrase}. Target {focus}."
        return f"{seq_prefix}: High Risk — urgent review focusing on {focus}."
    elif risk == 1:
        if weak_metric_phrase:
            return f"{seq_prefix}: Moderate Risk ({weak_metric_phrase}). Reinforce progress via {focus}."
        return f"{seq_prefix}: Moderate Risk — steady effort on {focus}."
    else:
        return f"{seq_prefix}: Low Risk ({grade:.1f}% grade) — light maintenance of {focus}."


@student_bp.route("/schedule/generate", methods=["POST"])
@login_required
def generate_schedule():
    subject_names   = request.form.getlist("subject_name[]")
    previous_grades = request.form.getlist("previous_grade[]")
    attendances     = request.form.getlist("attendance[]")
    study_hours     = request.form.getlist("study_hours[]")
    difficulties    = request.form.getlist("difficulty[]")
    exam_days_list  = request.form.getlist("days_until_exam[]")
    session_length_raw = request.form.get("session_length", "60")

    if not subject_names:
        rows = latest_prediction_rows(current_user.id)
        subject_names = [row["subject_name"] for row in rows]
        previous_grades = [str(row["performance_score"]) for row in rows]
        attendances = [str(row["attendance"]) for row in rows]
        study_hours = [str(row["weekly_study_hours"]) for row in rows]
        difficulties = [str(row["subject_difficulty"]) for row in rows]
        exam_days_list = [str(row["days_until_exam"]) for row in rows]

    if not subject_names:
        flash("Run ML Predictor for at least one assessed subject before generating a schedule.", "warning")
        return redirect(url_for('student.schedule'))

    def fail_validation(msg):
        draft_payload = []
        for j, sname in enumerate(subject_names):
            if not sname:
                continue
            draft_payload.append({
                "name": sname,
                "previous_grade": previous_grades[j] if j < len(previous_grades) else "",
                "attendance": attendances[j] if j < len(attendances) else "85",
                "study_hours": study_hours[j] if j < len(study_hours) else "6",
                "days_until_exam": exam_days_list[j] if j < len(exam_days_list) else "30",
                "difficulty": difficulties[j] if j < len(difficulties) else "3",
            })
        session["draft_schedule_form_data"] = draft_payload
        flash(msg, "danger")
        return redirect(url_for('student.schedule'))

    # Validate session length
    sess_ok, sess_val, sess_err = validate_session_length(session_length_raw)
    if not sess_ok:
        return fail_validation(sess_err)

    # Server-side validation of subject inputs
    for i, name in enumerate(subject_names):
        if not name:
            return fail_validation("Validation failed: Subject selection is required for all rows.")

        raw_grade = previous_grades[i] if i < len(previous_grades) else ""
        raw_att = attendances[i] if i < len(attendances) else ""
        raw_hrs = study_hours[i] if i < len(study_hours) else ""
        raw_days = exam_days_list[i] if i < len(exam_days_list) else ""

        is_ok, _, err_msg = validate_study_planner_subject_input(
            name=name,
            previous_grade=raw_grade,
            attendance=raw_att,
            study_hours=raw_hrs,
            days_until_exam=raw_days,
            user_id=current_user.id
        )
        if not is_ok:
            return fail_validation(err_msg)


    # ── 1. Snapshot previous week actual hours for feedback loop ──────────────
    today_local = local_today_for_user(current_user.id)
    week_start = today_local - timedelta(days=today_local.weekday())  # Monday
    for i, name in enumerate(subject_names):
        try:
            subj_obj = Subject.query.filter_by(name=name).first()
            subject_id = subj_obj.id if subj_obj else None
            grade = float(previous_grades[i]) if i < len(previous_grades) else 70.0
            att   = float(attendances[i])      if i < len(attendances)     else 85.0
            hrs   = float(study_hours[i])      if i < len(study_hours)     else 6.0
            diff  = float(difficulties[i])     if i < len(difficulties)    else 3.0
            exam_d = int(exam_days_list[i])    if i < len(exam_days_list) and exam_days_list[i] else 30

            # How many hours did student actually log this past week?
            prev_week_start = week_start - timedelta(days=7)
            actual_hours = 0.0
            if subject_id:
                logs_this_week = StudyLog.query.filter(
                    StudyLog.user_id == current_user.id,
                    StudyLog.subject_id == subject_id,
                    StudyLog.date >= prev_week_start,
                    StudyLog.date < week_start
                ).all()
                actual_hours = sum(l.duration_hours for l in logs_this_week if l.duration_hours)

            # What was planned last week? Check last history record
            last_hist = SubjectPerformanceHistory.query.filter(
                SubjectPerformanceHistory.user_id == current_user.id,
                SubjectPerformanceHistory.subject_name == name,
                SubjectPerformanceHistory.week_start == prev_week_start
            ).first()
            planned_hours = last_hist.planned_hours if last_hist else hrs

            completion_rate = min(1.0, actual_hours / planned_hours) if planned_hours > 0 else 1.0

            # Get days_since_last_studied
            days_since = 7
            if subject_id:
                last_log = StudyLog.query.filter_by(
                    user_id=current_user.id, subject_id=subject_id
                ).order_by(StudyLog.date.desc()).first()
                if last_log and last_log.date:
                    days_since = max(0, (today_local - last_log.date).days)

            # risk score for history (use predict_proba)
            risk_score_hist = 0.5
            try:
                model_h  = load_ml_model('random_forest')
                scaler_h = load_ml_model('scaler')
                if model_h and scaler_h:
                    feat_h = get_subject_features(current_user.id, name, grade, att, hrs, diff, exam_d)
                    fs_h = scaler_h.transform([feat_h])
                    probs_h = model_h.predict_proba(fs_h)[0]
                    risk_score_hist = float(0.0*probs_h[0] + 0.5*probs_h[1] + 1.0*probs_h[2])
            except Exception:
                pass

            hist_record = SubjectPerformanceHistory(
                user_id=current_user.id,
                week_start=week_start,
                subject_name=name,
                grade=grade, attendance=att, difficulty=diff,
                study_hours=hrs, days_until_exam=exam_d,
                days_since_last_studied=days_since,
                planned_hours=planned_hours, actual_hours=actual_hours,
                completion_rate=completion_rate, risk_score=risk_score_hist
            )
            db.session.add(hist_record)
        except Exception:
            pass
    db.session.flush()

    # ── 2. Clear existing schedule ────────────────────────────────────────────
    Schedule.query.filter_by(user_id=current_user.id).delete()

    model  = load_ml_model('random_forest')
    scaler = load_ml_model('scaler')
    if not model or not scaler:
        flash("Machine Learning models are not trained yet!", "danger")
        return redirect(url_for('student.schedule'))

    # ── 3. Predict risk & compute per-subject allocated hours ─────────────────
    subject_data = []
    total_recommended_hours = 0.0

    for i in range(len(subject_names)):
        name  = subject_names[i]
        subj_obj = Subject.query.filter_by(name=name).first()
        real_grade = None
        if subj_obj:
            snap = get_subject_performance_snapshot(current_user.id, subj_obj.id)
            if snap["source"] != "missing" and snap["score"] is not None:
                real_grade = float(snap["score"])

        raw_grade = previous_grades[i] if i < len(previous_grades) else 70.0
        try:
            form_grade = float(raw_grade)
        except (ValueError, TypeError):
            form_grade = 70.0

        if real_grade is not None:
            grade = real_grade
        else:
            grade = form_grade

        diff = float(derive_subject_difficulty(grade))
        att   = float(attendances[i])      if i < len(attendances)     else 85.0
        hrs   = float(study_hours[i])      if i < len(study_hours)     else 6.0
        exam_d = int(exam_days_list[i])    if i < len(exam_days_list) and exam_days_list[i] else 30

        features = get_subject_features(current_user.id, name, grade, att, hrs, diff, exam_d)
        f_scaled = scaler.transform([features])

        # Continuous risk score via predict_proba
        risk_score = 0.5
        risk_pred  = 1
        if hasattr(model, "predict_proba"):
            try:
                probs = model.predict_proba(f_scaled)[0]
                risk_score = float(0.0*probs[0] + 0.5*probs[1] + 1.0*probs[2])
                risk_pred  = int(np.argmax(probs))
            except Exception:
                risk_pred = int(model.predict(f_scaled)[0])
        else:
            risk_pred = int(model.predict(f_scaled)[0])

        # Boost score if low completion history
        try:
            week_ago = local_today_for_user(current_user.id) - timedelta(days=7)
            hist = SubjectPerformanceHistory.query.filter(
                SubjectPerformanceHistory.user_id == current_user.id,
                SubjectPerformanceHistory.subject_name == name,
                SubjectPerformanceHistory.week_start >= week_ago
            ).order_by(SubjectPerformanceHistory.logged_at.desc()).first()
            if hist and hist.completion_rate < 0.7:
                risk_score = min(1.0, risk_score * 1.15)
        except Exception:
            pass

        risk_label = "Low Risk"
        if risk_score >= 0.6:
            risk_label = "High Risk"
        elif risk_score >= 0.35:
            risk_label = "Medium Risk"

        subj = Subject.query.filter_by(name=name).first()
        if not subj:
            subj = Subject(name=name, difficulty_level=int(diff))
            db.session.add(subj)
            db.session.flush()

        subject_data.append({
            'id': subj.id,
            'name': name,
            'risk': risk_pred,
            'risk_label': risk_label,
            'risk_score': risk_score,
            'score': risk_score * diff,
            'allocated_hours': 0.0,
            'grade': grade,
            'attendance': att,
            'difficulty': diff,
        })

    # Compute risk-weighted proportional hour allocations using shared function
    available_hours = get_available_study_hours_total(current_user.id)
    if available_hours <= 0:
        available_hours = float(ctx.profile.target_weekly_hours if ctx.profile and ctx.profile.target_weekly_hours else 14.0)

    allocations = calculate_subject_hour_allocations(subject_data, available_hours)
    total_recommended_hours = 0.0
    for sd in subject_data:
        sd['allocated_hours'] = allocations.get(sd['name'], 2.0)
        total_recommended_hours += sd['allocated_hours']

    logger.info(
        "Schedule generation subjects considered user=%s subjects=%s",
        current_user.id,
        [
            {
                "name": sd["name"],
                "risk_score": round(sd["risk_score"], 3),
                "risk_label": sd["risk_label"],
                "allocated_hours": round(sd["allocated_hours"], 2),
            }
            for sd in subject_data
        ],
    )

    # ── 4. Parse availability slots from JSON submitted by form ───────────────
    free_slots_json = request.form.get("free_slots_json", "{}")
    raw_slots = {}
    try:
        raw_slots = json.loads(free_slots_json)
    except Exception:
        pass

    DAYS_MAP = {
        'Monday': 0, 'Tuesday': 1, 'Wednesday': 2, 'Thursday': 3,
        'Friday': 4, 'Saturday': 5, 'Sunday': 6
    }

    # Build per-day lists of free hours. Study time is derived as time not covered
    # by Sleep/Class/Sports/Social/Entertainment/Personal/Other commitments.
    day_study_hours = {i: [] for i in range(7)}
    day_blocked_hours = {i: set() for i in range(7)}  # Sleep/Busy hours

    for key, status in raw_slots.items():
        if "-" not in key:
            continue
        parts    = key.split("-")
        day_name = parts[0]
        if day_name not in DAYS_MAP:
            continue
        try:
            hour    = int(parts[1])
            day_idx = DAYS_MAP[day_name]
            if status == "free":
                day_study_hours[day_idx].append(hour)
            elif status in ("sleep", "busy"):
                day_blocked_hours[day_idx].add(hour)
        except ValueError:
            pass

    # Use DB-derived inverse availability as the source of truth.
    db_available_hours = get_available_study_hours_by_day(current_user.id)
    for i in range(7):
        raw_free = set(day_study_hours[i]) if any(day_study_hours.values()) else set(db_available_hours[i])
        day_study_hours[i] = sorted(raw_free - day_blocked_hours[i])

    logger.info(
        "Schedule generation availability user=%s available_hours_by_day=%s",
        current_user.id,
        {day: len(hours) for day, hours in day_study_hours.items()},
    )

    has_any_slots = any(len(hrs) > 0 for hrs in day_study_hours.values())

    # ── 5. Session Length block-partitioning allocation ───────────────────────
    try:
        session_len = int(request.form.get("session_length", 60))
    except ValueError:
        session_len = 60
    session_hours = session_len / 60.0

    # ── 5. Session Length block-partitioning allocation & Placement Engine ─────────
    try:
        session_len = int(request.form.get("session_length", 60))
    except ValueError:
        session_len = 60
    session_hours = session_len / 60.0

    import math
    from datetime import time

    if has_any_slots:
        # Caps & Limits
        WEEKDAY_MAX_HOURS = 4.5       # Mon-Fri max total study hours across all subjects
        WEEKEND_MAX_HOURS = 2.0       # Sat-Sun max total study hours (50%+ lighter weekend capacity)
        SUBJECT_DAILY_MAX_HOURS = 2.0 # Max hours per subject per day (distributes subject across multiple days)
        GAP_MINUTES = 15              # 15-minute rest break between consecutive sessions

        # Compute realistic discrete block capacity considering daily caps and session block size
        total_capacity_hours = 0.0
        for d in range(7):
            f_hrs = len(day_study_hours[d])
            cap = WEEKEND_MAX_HOURS if d in (5, 6) else WEEKDAY_MAX_HOURS
            max_daily = min(float(f_hrs), cap)
            max_blocks_for_day = int(max_daily // session_hours)
            total_capacity_hours += max_blocks_for_day * session_hours

        total_target_hours = sum(sd['allocated_hours'] for sd in subject_data)

        # Option A: Proportional Overflow Scaling if target hours exceed capacity
        if total_target_hours > total_capacity_hours and total_target_hours > 0:
            scale_factor = total_capacity_hours / total_target_hours
            for sd in subject_data:
                sd['allocated_hours'] = max(0.5, round(sd['allocated_hours'] * scale_factor, 1))
            scaled_sum = sum(sd['allocated_hours'] for sd in subject_data)
            flash(
                f"ℹ️ Notice: Target study hours ({round(total_target_hours, 1)} hrs) exceeded your weekly schedule capacity ({round(total_capacity_hours, 1)} hrs). "
                f"Schedules have been scaled proportionally to fit your available time while preserving subject priority.",
                "info"
            )

        # Sort subjects: highest risk_score first
        sorted_subjects = sorted(subject_data, key=lambda x: x['risk_score'], reverse=True)

        # Calculate number of session blocks needed per subject
        remaining_blocks = {sd['name']: max(1, int(round(sd['allocated_hours'] / session_hours))) for sd in sorted_subjects}
        total_blocks_target = {sd['name']: remaining_blocks[sd['name']] for sd in sorted_subjects}
        session_counter = {sd['name']: 0 for sd in sorted_subjects}

        scheduled_slots = []  # list of (day_idx, start_time, end_time, subject_dict, session_idx, total_sessions)
        day_total_scheduled = {d: 0.0 for d in range(7)}
        day_subject_scheduled = {d: {sd['name']: 0.0 for sd in sorted_subjects} for d in range(7)}

        num_subjects = len(sorted_subjects)

        # Place sessions day by day, using day-by-day subject rotation to prevent low-priority starvation
        for day_idx in range(7):
            free_hrs = day_study_hours[day_idx]
            if not free_hrs:
                continue

            day_cap = WEEKEND_MAX_HOURS if day_idx in (5, 6) else WEEKDAY_MAX_HOURS
            current_mins = None

            for hour in free_hrs:
                if day_total_scheduled[day_idx] + session_hours > day_cap:
                    break

                block_start_mins = hour * 60
                if current_mins is not None and block_start_mins < current_mins:
                    block_start_mins = current_mins

                placed = False
                # Rotate starting subject index by day_idx so every subject gets top priority on different days
                for offset in range(num_subjects):
                    s_rot_idx = (day_idx + offset) % num_subjects
                    sd = sorted_subjects[s_rot_idx]
                    name = sd['name']
                    if remaining_blocks[name] <= 0:
                        continue
                    if day_subject_scheduled[day_idx][name] + session_hours > SUBJECT_DAILY_MAX_HOURS:
                        continue

                    session_counter[name] += 1
                    s_idx = session_counter[name]
                    tot_s = total_blocks_target[name]

                    s_h = (block_start_mins // 60) % 24
                    s_m = block_start_mins % 60
                    e_mins = block_start_mins + int(session_len)
                    e_h = (e_mins // 60) % 24
                    e_m = e_mins % 60

                    start_t = time(s_h, s_m)
                    end_t = time(e_h, e_m)

                    scheduled_slots.append((day_idx, start_t, end_t, sd, s_idx, tot_s))

                    day_total_scheduled[day_idx] += session_hours
                    day_subject_scheduled[day_idx][name] += session_hours
                    remaining_blocks[name] -= 1

                    # Next session starts after GAP_MINUTES
                    current_mins = e_mins + GAP_MINUTES
                    placed = True
                    break

                if not placed and all(remaining_blocks[sd['name']] <= 0 for sd in sorted_subjects):
                    break

        # ── 6. Validation & Summary Logging ─────────────────────────────────
        total_planned = len(scheduled_slots)
        logger.info(
            "Schedule generation summary user=%s planned_sessions=%s per_day_scheduled=%s per_day_subject_scheduled=%s",
            current_user.id,
            total_planned,
            day_total_scheduled,
            day_subject_scheduled,
        )

        # ── 7. Write schedule to DB ───────────────────────────────────────────
        for (day_idx, start_t, end_t, sd, s_idx, tot_s) in scheduled_slots:
            tip = _build_planner_advice(sd, session_idx=s_idx, total_sessions=tot_s)
            new_schedule = Schedule(
                user_id=current_user.id,
                day_of_week=day_idx,
                start_time=start_t,
                end_time=end_t,
                subject_id=sd['id'],
                description=f"[{sd['risk_label']}] - {tip}"
            )
            db.session.add(new_schedule)

        # Update planned hours in performance history
        planned_by_subject = {}
        for (_, __, ___, sd, ____, _____) in scheduled_slots:
            planned_by_subject[sd['name']] = planned_by_subject.get(sd['name'], 0.0) + session_hours
        for h_rec in SubjectPerformanceHistory.query.filter_by(
            user_id=current_user.id, week_start=week_start
        ).all():
            if h_rec.subject_name in planned_by_subject:
                h_rec.planned_hours = planned_by_subject[h_rec.subject_name]

    else:
        # Fallback: sequential scheduling when no availability grid was provided
        current_day  = 0
        current_hour = 17
        
        sorted_subjects = sorted(subject_data, key=lambda x: x['risk_score'], reverse=True)
        remaining_blocks = {sd['name']: max(1, int(round(sd['allocated_hours'] / session_hours))) for sd in sorted_subjects}
        blocks_per_session = int(math.ceil(session_len / 60.0))

        for sd in sorted_subjects:
            assigned = remaining_blocks[sd['name']]
            tip = _build_planner_advice(sd)

            while assigned > 0:
                if current_hour + blocks_per_session > 23:
                    current_day  = (current_day + 1) % 7
                    current_hour = 17 if current_day < 5 else 10

                start_t = time(current_hour, 0)
                end_hour = (current_hour + int(session_len // 60)) % 24
                end_min = int(session_len % 60)
                end_t = time(end_hour, end_min)

                new_schedule = Schedule(
                    user_id=current_user.id,
                    day_of_week=current_day,
                    start_time=start_t,
                    end_time=end_t,
                    subject_id=sd['id'],
                    description=f"[{sd['risk_label']}] - {tip}"
                )
                db.session.add(new_schedule)
                current_hour += blocks_per_session
                assigned -= 1

    db.session.commit()
    flash("Adaptive Study Plan generated successfully based on ML predictions!", "success")
    return redirect(url_for('student.schedule'))


import logging as _logging
_gen_logger = _logging.getLogger('smart_study.question_gen')


def generate_assessment_questions_for_subject(subject_id, student_id=None):
    """
    Generate 15 assessment questions (5 easy / 5 medium / 5 hard) for *subject_id*
    via Gemini AI (structured JSON) with automatic JSON-text fallback.

    Works for EVERY class level, faculty, and program stored in the Subject table.
    Returns the number of questions actually saved to the database (0 on failure).
    """
    from app.services.ai_service import ai_service, AIServiceError, QuotaExceededError, ConfigurationError, FEATURE_MCQ

    subject = Subject.query.get(subject_id)
    if not subject:
        _gen_logger.error("generate_questions: subject_id=%s not found.", subject_id)
        return 0

    level   = subject.level_of_study or "Unknown Level"
    program = subject.program or "General"
    name    = subject.name or "Unknown Subject"

    total_existing = AssessmentQuestion.query.filter_by(subject_id=subject_id).count()
    if total_existing == 0:
        _gen_logger.info(
            "COLD START — generating first question batch for '%s' "
            "(level='%s', program='%s', subject_id=%s)",
            name, level, program, subject_id,
        )
    # ── Attempt 0: RAG Grounded MCQ Generation (from uploaded materials) ─────
    uid = student_id or (current_user.id if current_user and current_user.is_authenticated else None)
    if uid:
        try:
            from app.services.grounded_assessment import generate_grounded_mcqs
            grounded_qs, reason = generate_grounded_mcqs(user_id=uid, subject_id=subject_id, subject_name=name, count=12)
            if grounded_qs and isinstance(grounded_qs, list):
                _gen_logger.info("RAG Grounded generation succeeded for subject_id=%s (%d questions)", subject_id, len(grounded_qs))
                existing_qs = [q.question_text.lower()[:50] for q in AssessmentQuestion.query.filter_by(subject_id=subject_id).all()]
                saved_count = 0
                for q_data in grounded_qs:
                    q_text = q_data.get("q", q_data.get("question_text", ""))
                    if not q_text or len(q_text) < 10 or q_text.lower()[:50] in existing_qs:
                        continue
                    opt_a = q_data.get("a", q_data.get("option_a"))
                    opt_b = q_data.get("b", q_data.get("option_b"))
                    opt_c = q_data.get("c", q_data.get("option_c"))
                    opt_d = q_data.get("d", q_data.get("option_d"))
                    correct = q_data.get("ans", q_data.get("correct_answer", ""))
                    if not all([opt_a, opt_b, opt_c, opt_d]) or str(correct).upper() not in ["A", "B", "C", "D"]:
                        continue
                    new_q = AssessmentQuestion(
                        subject_id=subject_id,
                        question_text=q_text,
                        option_a=opt_a,
                        option_b=opt_b,
                        option_c=opt_c,
                        option_d=opt_d,
                        correct_answer=str(correct).upper(),
                        difficulty=q_data.get("diff", "medium").lower(),
                        question_type="grounded_conceptual",
                        explanation=q_data.get("explanation", ""),
                        source="rag_grounded"
                    )
                    db.session.add(new_q)
                    saved_count += 1
                if saved_count > 0:
                    db.session.commit()
                    return saved_count
        except Exception as e:
            _gen_logger.warning("RAG Grounded generation failed for subject_id=%s, falling back to generic AI: %s", subject_id, e)


    # ── Build chapter/topic context ─────────────────────────────────────────
    chapters = Chapter.query.filter_by(subject_id=subject_id).all()
    ch_info = ""
    ch_map  = {}
    if chapters:
        ch_info = "The chapters/topics for this subject are:\n"
        for ch in chapters:
            ch_info += f"- Chapter {ch.chapter_number}: {ch.name}\n"
            for t in Topic.query.filter_by(chapter_id=ch.id).all():
                ch_info += f"  - Topic {t.topic_number}: {t.name}\n"
                ch_map[t.name.lower()]  = (ch.id, t.id)
                ch_map[ch.name.lower()] = (ch.id, t.id)

    # ── Build seen-question exclusion list ──────────────────────────────────
    exclusion_text = ""
    try:
        uid = student_id or (current_user.id if current_user and current_user.is_authenticated else None)
        if uid:
            seen_q_ids = [
                sq.question_id
                for sq in StudentSeenQuestion.query.filter_by(student_id=uid).all()
            ]
            if seen_q_ids:
                seen_qs = AssessmentQuestion.query.filter(
                    AssessmentQuestion.id.in_(seen_q_ids),
                    AssessmentQuestion.subject_id == subject_id,
                ).all()
                if seen_qs:
                    exclusion_text = "\nDo not repeat any of these questions:\n" + "\n".join(
                        f"- {q.question_text}" for q in seen_qs[-50:]
                    )
    except Exception:
        pass  # Not fatal — exclusion list is best-effort

    # ── Curriculum context line (handles every level correctly) ─────────────
    if "university" in level.lower() or "bachelor" in level.lower() or "master" in level.lower():
        curriculum_ctx = f"Nepal university / higher-education curriculum for the {program} program."
    elif any(cls in level.lower() for cls in ["11", "12"]):
        curriculum_ctx = f"Nepal NEB (National Examination Board) {level} — {program}."
    elif any(cls in level.lower() for cls in ["9", "10"]):
        curriculum_ctx = f"Nepal CDC / SEE curriculum, {level}."
    else:
        curriculum_ctx = f"Nepal CDC curriculum, {level}."

    prompt = (
        f"Generate exactly 15 high-quality, distinct multiple-choice questions "
        f"covering the core syllabus topics of the subject '{name}' "
        f"for a student at the '{level}' level under the '{program}' program.\n"
        f"Curriculum context: {curriculum_ctx}\n\n"
        f"{ch_info}\n"
        "Requirements:\n"
        "1. Generate exactly 5 'easy', 5 'medium', and 5 'hard' questions.\n"
        "2. Each question must have 4 options (A, B, C, D) and exactly one correct answer.\n"
        "3. Provide distinct, subject-relevant, non-repetitive questions.\n"
        "4. Map each question to a chapter number and topic name from the list above if possible.\n"
        "5. For each question provide a concise explanation of the correct answer.\n"
        f"{exclusion_text}\n"
        "Return ONLY a JSON array. Each element must have keys: "
        "q, a, b, c, d, ans (A/B/C/D), diff (easy/medium/hard), "
        "explanation, ch_num (int or null), topic_name (string or null)."
    )

    system_instruction = (
        "You are an expert curriculum examiner who writes assessments for students "
        "across Class 6 through Master's level under Nepal's educational system. "
        "Always respond with valid JSON only — no markdown fences, no extra text."
    )

    # ── Attempt 1: Structured Gemini JSON ───────────────────────────────────
    response_schema = {
        "type": "ARRAY",
        "items": {
            "type": "OBJECT",
            "properties": {
                "q":           {"type": "STRING"},
                "a":           {"type": "STRING"},
                "b":           {"type": "STRING"},
                "c":           {"type": "STRING"},
                "d":           {"type": "STRING"},
                "ans":         {"type": "STRING"},
                "diff":        {"type": "STRING"},
                "type":        {"type": "STRING"},
                "ch_num":      {"type": "INTEGER"},
                "topic_name":  {"type": "STRING"},
                "explanation": {"type": "STRING"},
            },
            "required": ["q", "a", "b", "c", "d", "ans", "diff", "explanation"],
        },
    }

    questions_data = None
    try:
        questions_data = ai_service.call_gemini_reusable(
            prompt,
            feature=FEATURE_MCQ,
            is_json=True,
            context=f"assessment_mcq:subject:{subject_id}",
            system_instruction=system_instruction,
            response_mime_type="application/json",
            response_schema=response_schema,
        )
        if isinstance(questions_data, list) and len(questions_data) < 12:
            _gen_logger.warning(
                "Structured Gemini response has fewer than 12 questions (%d). "
                "Invalidating cache for retry.",
                len(questions_data)
            )
            ai_service.invalidate_cache(prompt)
            questions_data = None
        else:
            _gen_logger.debug(
                "Structured Gemini response parsed: %d items",
                len(questions_data) if isinstance(questions_data, list) else -1,
            )
    except (QuotaExceededError, ConfigurationError):
        raise
    except Exception as e:
        _gen_logger.warning(
            "Structured Gemini generation failed for subject_id=%s ('%s'): %s. "
            "Attempting plain-text JSON fallback.",
            subject_id, name, e,
        )

    # ── Attempt 2: Plain-text fallback (no response_schema) ─────────────────
    if not isinstance(questions_data, list) or len(questions_data) == 0:
        try:
            questions_data = ai_service.call_gemini_reusable(
                prompt,
                feature=FEATURE_MCQ,
                is_json=True,
                context=f"assessment_mcq_fallback:subject:{subject_id}",
                system_instruction=system_instruction,
            )
            if isinstance(questions_data, list) and len(questions_data) < 12:
                _gen_logger.warning(
                    "Plain-text fallback has fewer than 12 questions (%d). "
                    "Invalidating cache.",
                    len(questions_data)
                )
                ai_service.invalidate_cache(prompt)
                questions_data = None
            else:
                _gen_logger.info(
                    "Plain-text fallback parsed: %d items for subject_id=%s",
                    len(questions_data) if isinstance(questions_data, list) else -1,
                    subject_id,
                )
        except (QuotaExceededError, ConfigurationError):
            raise
        except Exception as e2:
            _gen_logger.error(
                "ALL AI generation attempts failed for subject_id=%s ('%s' / '%s' / '%s'): %s",
                subject_id, name, level, program, e2,
            )
            return 0
    
    count = 0
    if isinstance(questions_data, list):
        # Part B: Additive generation. DO NOT delete old questions!
        # Fetch existing questions to avoid near-duplicates
        existing_qs = [q.question_text.lower()[:50] for q in AssessmentQuestion.query.filter_by(subject_id=subject_id).all()]
        
        for q in questions_data:
            # Validation
            q_text = q.get("q", "")
            if not q_text or len(q_text) < 10:
                continue
            if q_text.lower()[:50] in existing_qs:
                continue # Skip near-duplicates
                
            opt_a = q.get("a")
            opt_b = q.get("b")
            opt_c = q.get("c")
            opt_d = q.get("d")
            correct = q.get("ans", q.get("correct_answer", q.get("correct", "")))
            if not all([opt_a, opt_b, opt_c, opt_d]) or correct.upper() not in ["A", "B", "C", "D"]:
                continue

            # Map chapter and topic
            chapter_id = None
            topic_id = None
            
            # Find matching chapter/topic from our map
            t_name = str(q.get("topic_name", "")).lower()
            ch_num = q.get("ch_num")
            
            # Try to match topic name
            matched = False
            for key, val in ch_map.items():
                if key in t_name or t_name in key:
                    chapter_id, topic_id = val
                    matched = True
                    break
                    
            if not matched and chapters:
                # Try to match by chapter number
                for ch in chapters:
                    if ch.chapter_number == ch_num:
                        chapter_id = ch.id
                        first_topic = Topic.query.filter_by(chapter_id=ch.id).first()
                        if first_topic:
                            topic_id = first_topic.id
                        break
                # Fallback to first chapter/topic
                if not chapter_id:
                    chapter_id = chapters[0].id
                    first_topic = Topic.query.filter_by(chapter_id=chapters[0].id).first()
                    if first_topic:
                        topic_id = first_topic.id
            
            diff_val = q.get("diff", q.get("difficulty", "medium"))
            type_val = q.get("type", q.get("question_type", "conceptual"))
            
            new_q = AssessmentQuestion(
                subject_id=subject_id,
                chapter_id=chapter_id,
                topic_id=topic_id,
                question_text=q_text,
                option_a=opt_a,
                option_b=opt_b,
                option_c=opt_c,
                option_d=opt_d,
                correct_answer=correct.upper(),
                difficulty=diff_val.lower(),
                question_type=type_val,
                source="ai_generated"
            )
            db.session.add(new_q)
            count += 1
            
        db.session.commit()
    return count


# --- ASSESSMENT ROUTES ---

@student_bp.route("/assessment/start", methods=["GET", "POST"])
@login_required
def assessment_start():
    profile = StudentProfile.query.filter_by(user_id=current_user.id).first()
    
    if not profile or not profile.study_level:
        flash("Please set your class level first", "warning")
        return redirect(url_for("student.profile"))
        
    subjects = get_profile_subjects(profile)
    active_subject_ids = {s.id for s in subjects}
    preselected_subject_id = request.args.get("subject_id", type=int)
    if preselected_subject_id and preselected_subject_id in active_subject_ids:
        subjects = [s for s in subjects if s.id == preselected_subject_id]

    if request.method == "POST":
        selected_subjects = []
        for raw_id in request.form.getlist("subjects"):
            try:
                sub_id = int(raw_id)
            except (TypeError, ValueError):
                continue
            if sub_id in active_subject_ids:
                selected_subjects.append(sub_id)

        if not selected_subjects:
            flash("Please select at least one active profile subject.", "warning")
            return redirect(url_for('student.assessment_start'))
            


        session['assessment_subjects'] = selected_subjects
        session['assessment_current_idx'] = 0
        session['assessment_scores'] = {}
        session['assessment_history'] = {}  # Track correct/wrong per subject for adaptive difficulty
        session['assessment_question_history'] = {}  # Track detailed question outcomes
        session['assessment_ids_by_subject'] = {}  # {str(subject_id): StudentAssessment.id}

        # Clear difficulty state
        for sub_id in selected_subjects:
            session.pop(f'assessment_diff_{sub_id}', None)

        first_sub = session['assessment_subjects'][0]
        return redirect(url_for('student.assessment_question', subject_id=first_sub, q_num=1))
        
    # Recent assessment history for the panel above subject selection
    from app.models import StudentAssessment, Subject as SubjectModel
    recent_assessments = (
        StudentAssessment.query
        .filter_by(student_id=current_user.id)
        .order_by(StudentAssessment.completed_at.desc())
        .all()
    )
    recent_assessment_display = []
    for sa in recent_assessments:
        # Skip incomplete attempts with 0 responses
        resp_count = AssessmentResponse.query.filter_by(assessment_id=sa.id).count()
        if resp_count == 0:
            continue
        subj = SubjectModel.query.get(sa.subject_id)
        correct = round((sa.total_score or 0.0) / 100.0 * resp_count)
        recent_assessment_display.append({
            "id": sa.id,
            "subject": subj.name if subj else "Unknown",
            "date": sa.completed_at,
            "score_pct": round(sa.weighted_score or sa.total_score or 0.0, 1),
            "correct": correct,
            "total": resp_count,
            "tier": sa.knowledge_tier or "beginner",
        })

    return render_template(
        "student/assessment_start.html",
        subjects=subjects,
        profile=profile,
        preselected_subject_id=preselected_subject_id,
        recent_assessments=recent_assessment_display,
    )

@student_bp.route("/assessment/question/<int:subject_id>/<int:q_num>")
@login_required
def assessment_question(subject_id, q_num):
    # Total 12 questions per subject (Adaptive Assessment)
    if q_num > 12:
        # Show subject summary before moving to next subject
        return redirect(url_for('student.assessment_subject_summary', subject_id=subject_id))

    # Track AI generation exception if on-demand generation fails
    last_ai_error = None

    # Ensure a healthy question pool exists for this subject
    total_existing = AssessmentQuestion.query.filter_by(subject_id=subject_id).count()
    if total_existing < 12:
        _gen_logger.info(
            "Fewer than 12 questions exist for subject_id=%s (found %d). Triggering generation/topup.",
            subject_id, total_existing
        )
        try:
            generate_assessment_questions_for_subject(subject_id)
        except (ConfigurationError, QuotaExceededError, RateLimitError, AIServiceError) as e:
            last_ai_error = e
            _gen_logger.error("AI service error during question topup for subject_id=%s: %s", subject_id, e)
        except Exception as e:
            last_ai_error = e
            _gen_logger.error("Failed to generate assessment questions on-demand: %s", e)
            
    # Adaptive logic
    history = session.get('assessment_history', {}).get(str(subject_id), [])
    current_diff = session.get(f'assessment_diff_{subject_id}', 'medium')
    
    if len(history) >= 2:
        last_two = history[-2:]
        if last_two == [True, True]:
            if current_diff == 'easy': current_diff = 'medium'
            elif current_diff == 'medium': current_diff = 'hard'
        elif last_two == [False, False]:
            if current_diff == 'hard': current_diff = 'medium'
            elif current_diff == 'medium': current_diff = 'easy'
            
    session[f'assessment_diff_{subject_id}'] = current_diff
    
    # Pick an unseen question
    import random
    seen_subquery = db.session.query(StudentSeenQuestion.question_id).filter_by(student_id=current_user.id)
    questions = AssessmentQuestion.query.filter(
        AssessmentQuestion.subject_id == subject_id,
        AssessmentQuestion.difficulty == current_diff,
        ~AssessmentQuestion.id.in_(seen_subquery)
    ).all()
    
    if not questions:
        # Fallback to any difficulty unseen
        questions = AssessmentQuestion.query.filter(
            AssessmentQuestion.subject_id == subject_id,
            ~AssessmentQuestion.id.in_(seen_subquery)
        ).all()
        
    if not questions:
        # Absolute fallback
        questions = AssessmentQuestion.query.filter_by(subject_id=subject_id).all()
        
    q = random.choice(questions) if questions else None
    
    if not q:
        # One automatic on-demand generation attempt before giving up
        _gen_logger.warning(
            "No questions available for subject_id=%s at q_num=%s. Attempting on-demand generation.",
            subject_id, q_num,
        )
        try:
            generated = generate_assessment_questions_for_subject(subject_id)
            if generated > 0:
                questions = AssessmentQuestion.query.filter_by(subject_id=subject_id).all()
                q = random.choice(questions) if questions else None
        except (ConfigurationError, QuotaExceededError, RateLimitError, AIServiceError) as e:
            last_ai_error = e
        except Exception as _gen_err:
            last_ai_error = _gen_err

        if not q:
            # Handle AI exceptions with user-friendly flash messages
            if isinstance(last_ai_error, ConfigurationError):
                flash(
                    "AI assessment generation is temporarily unavailable because the AI service configuration requires attention. Please try again later or contact the administrator.",
                    "warning",
                )
            elif isinstance(last_ai_error, QuotaExceededError):
                flash(
                    "The AI assessment generation limit has been reached temporarily. Please try again later.",
                    "warning",
                )
            elif isinstance(last_ai_error, RateLimitError):
                flash(
                    "The AI service is currently receiving too many requests. Please wait a moment and try again.",
                    "warning",
                )
            elif isinstance(last_ai_error, AIServiceError):
                flash(
                    "AI assessment generation is temporarily unavailable. Please try again later.",
                    "warning",
                )
            else:
                flash(
                    "We're preparing your assessment questions — please try again in a moment.",
                    "warning",
                )
            return redirect(url_for('student.assessment_start'))
    
    subject = Subject.query.get(subject_id)
    return render_template("student/assessment_question.html", question=q, subject=subject, q_num=q_num, total_q=12)

@student_bp.route("/assessment/answer", methods=["POST"])
@login_required
def assessment_answer():
    # ── Guard: validate required fields before casting ────────────────────────
    raw_qid  = request.form.get("question_id")
    raw_sid  = request.form.get("subject_id")
    raw_qnum = request.form.get("q_num")
    if not raw_qid or not raw_sid or not raw_qnum:
        return jsonify({"status": "error", "message": "Missing required field(s): question_id, subject_id, q_num."}), 400
    try:
        q_id  = int(raw_qid)
        sub_id = int(raw_sid)
        q_num  = int(raw_qnum)
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "question_id, subject_id, and q_num must be integers."}), 400
    answer = request.form.get("answer")
    time_taken = int(request.form.get("time_taken", 0) or 0)

    q = AssessmentQuestion.query.get(q_id)
    if q is None:
        return jsonify({"status": "error", "message": f"Question {q_id} not found."}), 400
    is_correct = (answer == q.correct_answer)
    
    # Log to StudentSeenQuestion
    seen_q = StudentSeenQuestion(
        student_id=current_user.id,
        question_id=q_id,
        was_correct=is_correct
    )
    db.session.add(seen_q)
    db.session.commit()
    
    # Track history
    history = session.get('assessment_history', {})
    if str(sub_id) not in history:
        history[str(sub_id)] = []
    history[str(sub_id)].append(is_correct)
    session['assessment_history'] = history
    
    # Track detailed question history
    q_history = session.get('assessment_question_history', {})
    q_history[str(q_id)] = is_correct
    session['assessment_question_history'] = q_history
    
    # ── Upsert StudentAssessment stub for this subject (created once per session) ──
    sa_ids = session.get('assessment_ids_by_subject', {})
    sa_id = sa_ids.get(str(sub_id))
    if not sa_id:
        sa_stub = StudentAssessment(
            student_id=current_user.id,
            subject_id=sub_id,
            total_score=0.0,
            max_score=100.0,
            weighted_score=0.0,
            knowledge_tier='beginner',
        )
        db.session.add(sa_stub)
        db.session.flush()  # get ID without full commit
        sa_id = sa_stub.id
        sa_ids[str(sub_id)] = sa_id
        session['assessment_ids_by_subject'] = sa_ids

    # ── Write AssessmentResponse row ─────────────────────────────────────────
    resp = AssessmentResponse(
        assessment_id=sa_id,
        question_id=q_id,
        selected_answer=answer if answer else None,
        is_correct=is_correct,
        response_time_seconds=time_taken,
    )
    db.session.add(resp)
    db.session.commit()

    # ── Finalize immediately if this was the last question (q_num == 12) ──
    if q_num == 12:
        try:
            responses = AssessmentResponse.query.filter_by(assessment_id=sa_id).all()
            total_q = len(responses)
            if total_q > 0:
                correct_count = sum(1 for r in responses if r.is_correct)
                w_pts = 0.0
                m_pts = 0.0
                for r in responses:
                    q_item = AssessmentQuestion.query.get(r.question_id)
                    weight = 1.0
                    if q_item:
                        diff = (q_item.difficulty or "").lower()
                        if diff in ("medium", "intermediate"):
                            weight = 1.5
                        elif diff in ("hard", "advanced"):
                            weight = 2.0
                    m_pts += weight
                    if r.is_correct:
                        w_pts += weight
                
                flat_pct = (correct_count / total_q) * 100
                weighted_pct = (w_pts / m_pts * 100) if m_pts > 0 else 0.0
                
                tier = 'beginner'
                if weighted_pct >= 70: tier = 'advanced'
                elif weighted_pct >= 40: tier = 'intermediate'
                
                sa_row = StudentAssessment.query.get(sa_id)
                if sa_row:
                    sa_row.total_score = flat_pct
                    sa_row.weighted_score = weighted_pct
                    sa_row.knowledge_tier = tier
                    sa_row.completed_at = datetime.utcnow()
                    db.session.commit()
                    current_app.logger.info(
                        f"[Assessment Finalize] Subject {sub_id} successfully finalized at q_num=12. "
                        f"Score: {flat_pct:.2f}%, Weighted: {weighted_pct:.2f}%, Tier: {tier}"
                    )
        except Exception as e:
            current_app.logger.error(f"[Assessment Finalize] Failed to finalize subject {sub_id} at q_num=12: {e}")

    return redirect(url_for('student.assessment_question', subject_id=sub_id, q_num=q_num + 1))

@student_bp.route("/assessment/subject-summary/<int:subject_id>")
@login_required
def assessment_subject_summary(subject_id):
    """One-way subject summary screen shown after finishing each subject."""
    subject = Subject.query.get_or_404(subject_id)
    sa_ids = session.get('assessment_ids_by_subject', {})
    sa_id = sa_ids.get(str(subject_id))
    
    correct = 0
    total_q = 0
    w_pts = 0.0
    m_pts = 0.0
    questions_detail = []
    
    if sa_id:
        responses = AssessmentResponse.query.filter_by(assessment_id=sa_id).all()
        total_q = len(responses)
        correct = sum(1 for r in responses if r.is_correct)
        for r in responses:
            q = AssessmentQuestion.query.get(r.question_id)
            weight = 1.0
            if q:
                diff = (q.difficulty or "").lower()
                if diff in ("medium", "intermediate"):
                    weight = 1.5
                elif diff in ("hard", "advanced"):
                    weight = 2.0
                questions_detail.append({
                    'question': q.question_text,
                    'option_a': q.option_a,
                    'option_b': q.option_b,
                    'option_c': q.option_c,
                    'option_d': q.option_d,
                    'correct': q.correct_answer,
                    'selected': r.selected_answer,
                    'is_correct': r.is_correct,
                })
            m_pts += weight
            if r.is_correct:
                w_pts += weight
                
    weighted_pct = (w_pts / m_pts * 100) if m_pts > 0 else 0.0
    flat_pct = (correct / total_q * 100) if total_q > 0 else 0.0
    tier = 'beginner'
    if weighted_pct >= 70: tier = 'advanced'
    elif weighted_pct >= 40: tier = 'intermediate'

    # Determine next destination
    subs = session.get('assessment_subjects', [])
    current_idx = session.get('assessment_current_idx', 0)
    next_idx = current_idx + 1
    is_last_subject = (next_idx >= len(subs))

    if not is_last_subject:
        next_subject_id = subs[next_idx]
    else:
        next_subject_id = None

    return render_template(
        'student/assessment_subject_summary.html',
        subject=subject,
        correct=correct,
        total_q=total_q,
        weighted_pct=round(weighted_pct, 1),
        flat_pct=round(flat_pct, 1),
        tier=tier,
        questions_detail=questions_detail,
        is_last_subject=is_last_subject,
        next_subject_id=next_subject_id,
    )


@student_bp.route("/assessment/subject-summary/<int:subject_id>/next", methods=["POST"])
@login_required
def assessment_subject_summary_next(subject_id):
    """Move to next subject or final results — called via POST from summary screen."""
    subs = session.get('assessment_subjects', [])
    current_idx = session.get('assessment_current_idx', 0)
    next_idx = current_idx + 1
    if next_idx < len(subs):
        session['assessment_current_idx'] = next_idx
        return redirect(url_for('student.assessment_question', subject_id=subs[next_idx], q_num=1))
    return redirect(url_for('student.assessment_results'))


@student_bp.route("/assessment/detail/<int:sa_id>", methods=["GET"])
@login_required
def assessment_detail(sa_id):
    """AJAX endpoint — returns per-question detail for a past assessment (modal)."""
    sa = StudentAssessment.query.get_or_404(sa_id)
    if sa.student_id != current_user.id:
        return jsonify({'status': 'error', 'message': 'Access denied'}), 403

    responses = AssessmentResponse.query.filter_by(assessment_id=sa_id).all()
    items = []
    for r in responses:
        q = AssessmentQuestion.query.get(r.question_id)
        if q:
            items.append({
                'question': q.question_text,
                'option_a': q.option_a,
                'option_b': q.option_b,
                'option_c': q.option_c,
                'option_d': q.option_d,
                'correct': q.correct_answer,
                'selected': r.selected_answer,
                'is_correct': r.is_correct,
                'explanation': getattr(q, 'explanation', None),
            })
    return jsonify({'status': 'success', 'items': items})


@student_bp.route("/assessment/results")
@login_required
def assessment_results():
    # ── Session first, DB fallback if session is missing or empty ────────────
    sa_ids = session.get('assessment_ids_by_subject', {})
    if not sa_ids:
        # Session was lost (e.g. browser restart mid-quiz). Reconstruct from DB:
        # fetch all StudentAssessment records for today that have at least one response.
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        todays_sa = (
            StudentAssessment.query
            .filter(
                StudentAssessment.student_id == current_user.id,
                StudentAssessment.completed_at >= today_start,
            )
            .all()
        )
        sa_ids = {str(sa.subject_id): sa.id for sa in todays_sa}
        logger.info(
            "[Assessment Results] Session key missing; reconstructed sa_ids from DB: %s",
            sa_ids
        )

    # ── Context: finalize SA stub scores + profile flag ─────────────────────────
    ctx = get_learning_context(current_user.id)

    results = []
    study_times = []
    total_correct_all = 0
    total_questions_all = 0
    total_pct = 0.0
    count = 0

    for sub_id_str, sa_id in sa_ids.items():
        sub_id = int(sub_id_str)
        # Query responses for this sa_id
        responses = AssessmentResponse.query.filter_by(assessment_id=sa_id).all()
        total_q = len(responses)
        
        # Skip if 0 responses (edge case of incomplete attempt)
        if total_q == 0:
            continue
            
        correct = sum(1 for r in responses if r.is_correct)
        
        # Calculate weighted points
        w_pts = 0.0
        m_pts = 0.0
        for r in responses:
            q = AssessmentQuestion.query.get(r.question_id)
            weight = 1.0
            if q:
                diff = (q.difficulty or "").lower()
                if diff in ("medium", "intermediate"):
                    weight = 1.5
                elif diff in ("hard", "advanced"):
                    weight = 2.0
            m_pts += weight
            if r.is_correct:
                w_pts += weight
                
        flat_pct = (correct / total_q) * 100
        weighted_pct = (w_pts / m_pts * 100) if m_pts > 0 else 0.0
        
        tier = 'beginner'
        if weighted_pct >= 70: tier = 'advanced'
        elif weighted_pct >= 40: tier = 'intermediate'

        # Finalize the SA stub created during the quiz
        sa_row = StudentAssessment.query.get(sa_id)
        if sa_row:
            sa_row.total_score = flat_pct
            sa_row.weighted_score = weighted_pct
            sa_row.knowledge_tier = tier
            sa_row.completed_at = datetime.utcnow()
            current_app.logger.info(
                f"[Assessment Results Finalize] sa_id={sa_id} for subject {sub_id} updated. "
                f"Score: {flat_pct:.2f}%, Weighted: {weighted_pct:.2f}%, Tier: {tier}"
            )

        subj = Subject.query.get(sub_id)
        results.append({
            'subject': subj.name if subj else 'Unknown',
            'score': weighted_pct,
            'flat_score': flat_pct,
            'tier': tier,
            'correct': correct,
            'total': total_q,
        })
        
        # Divisor fix: use dynamic total_q
        if flat_pct < 40:
            rec_hours = "3.0 hours/day (High priority)"
        elif flat_pct < 70:
            rec_hours = "2.0 hours/day (Medium priority)"
        else:
            rec_hours = "1.0 hour/day (Low priority)"
        study_times.append({
            "subject_name": subj.name if subj else "Unknown",
            "score": flat_pct,
            "recommended_hours": rec_hours,
        })

        total_correct_all += correct
        total_questions_all += total_q
        total_pct += weighted_pct
        count += 1

    # Mark profile as assessment-complete
    p = ctx.profile
    if p:
        p.has_completed_assessment = True
        if p.prior_academic_score == 0 and count > 0:
            p.prior_academic_score = total_pct / count
    db.session.commit()

    # Invalidate context caches
    ctx._assessment_history = None
    ctx._weak_chapters = None
    ctx._weak_topics = None
    ctx._strong_chapters = None
    ctx._strong_topics = None
    ctx._recommended_topics = None

    avg_score = total_pct / count if count > 0 else 0
    overall_pct = (total_correct_all / total_questions_all * 100) if total_questions_all > 0 else 0.0

    weak_chapters = ctx.weak_chapters
    recommended_topics = ctx.weak_topics

    revision_plan_steps = []
    for ch_info in weak_chapters:
        topics = Topic.query.filter_by(chapter_id=ch_info["id"]).all()
        for t in topics:
            revision_plan_steps.append(
                f"Revise '{t.name}' under Chapter {ch_info['chapter_number']} of {ch_info['subject_name']} for 45 mins."
            )

    return render_template(
        "student/assessment_results.html",
        results=results,
        avg_score=avg_score,
        overall_pct=round(overall_pct, 1),
        total_correct_all=total_correct_all,
        total_incorrect_all=total_questions_all - total_correct_all,
        total_questions_all=total_questions_all,
        weak_chapters=weak_chapters,
        recommended_topics=recommended_topics[:6],
        revision_plan_steps=revision_plan_steps[:4],
        study_times=study_times,
    )


# --- DOCUMENT UPLOAD ROUTES ---

@student_bp.route("/documents/upload", methods=["POST"])
@login_required
def upload_document():
    if 'document_file' not in request.files:
        flash("No file part", "danger")
        return redirect(url_for('student.predict'))
        
    file = request.files['document_file']
    if file.filename == '':
        flash("No selected file", "danger")
        return redirect(url_for('student.predict'))
        
    if file:
        filename = secure_filename(file.filename)
        ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
        if ext not in ['pdf', 'jpg', 'jpeg', 'png']:
            flash("Invalid file type. Only PDF and Images allowed.", "danger")
            return redirect(url_for('student.predict'))

        flash("Please use ML Predictor > Upload Marksheet to review and confirm OCR results before saving.", "warning")
        return redirect(url_for('student.predict'))
            
        upload_dir = os.path.join(os.path.abspath(os.path.dirname(__file__)), '../../app/static/uploads', str(current_user.id))
        os.makedirs(upload_dir, exist_ok=True)
        filepath = os.path.join(upload_dir, filename)
        file.save(filepath)
        
        doc_type = request.form.get("document_type")
        inst_name = request.form.get("institution_name")
        exam_year = int(request.form.get("exam_year", 2020))
        
        # Process OCR
        file_type = 'pdf' if ext == 'pdf' else 'image'
        processor = MarksheetProcessor()
        
        try:
            marks_data, confidence = processor.process_file(filepath, file_type)
        except Exception as e:
            # Handle timeout/failure
            doc = AcademicDocument(
                student_id=current_user.id, document_type=doc_type, document_name=filename,
                file_path=filepath, file_type=ext, institution_name=inst_name, exam_year=exam_year,
                overall_percentage=0, extraction_confidence=0, processed_at=datetime.utcnow()
            )
            db.session.add(doc)
            db.session.commit()
            flash(f"Processing failed: {str(e)}", "danger")
            return redirect(url_for('student.predict'))
        
        doc = AcademicDocument(
            student_id=current_user.id, document_type=doc_type, document_name=filename,
            file_path=filepath, file_type=ext, institution_name=inst_name, exam_year=exam_year,
            extraction_confidence=confidence, processed_at=datetime.utcnow()
        )
        db.session.add(doc)
        db.session.flush()
        
        total_pct = 0
        count = 0
        for m in marks_data:
            pct = processor.convert_to_percentage(m['value'], m['full_marks'])
            mapped_subject = map_to_active_subject_name(current_user.id, m['subject'])
            em = ExtractedMark(
                document_id=doc.id, subject_name_original=m['subject'],
                subject_name_mapped=mapped_subject,
                marks_obtained=float(m['value']) if m['value'].replace('.','',1).isdigit() else 0,
                full_marks=float(m['full_marks']), percentage=pct, grade=m['value'] if not m['value'].replace('.','',1).isdigit() else ""
            )
            db.session.add(em)
            total_pct += pct
            count += 1
            
        overall = total_pct / count if count > 0 else 0
        doc.overall_percentage = overall
        
        # Update Profile
        profile = StudentProfile.query.filter_by(user_id=current_user.id).first()
        if profile:
            profile.documents_uploaded += 1
            weight = 0.2
            if doc_type in ['see_class10', 'plus_two', 'a_level']: weight = 0.4
            
            if profile.prior_academic_score == 0:
                profile.prior_academic_score = overall
            else:
                profile.prior_academic_score = (profile.prior_academic_score * (1 - weight)) + (overall * weight)
                
            if profile.prior_academic_score >= 80: profile.academic_level = 'excellent'
            elif profile.prior_academic_score >= 65: profile.academic_level = 'good'
            elif profile.prior_academic_score >= 50: profile.academic_level = 'average'
            else: profile.academic_level = 'weak'
            
        db.session.commit()
        flash(f"Document uploaded! Extracted {count} subjects.", "success")
        return redirect(url_for('student.predict'))

@student_bp.route("/documents/<int:doc_id>")
@login_required
def document_detail(doc_id):
    doc = AcademicDocument.query.get_or_404(doc_id)
    if doc.student_id != current_user.id:
        return redirect(url_for('student.predict'))
    marks = ExtractedMark.query.filter_by(document_id=doc.id).all()
    return render_template("student/document_detail.html", document=doc, marks=marks)

@student_bp.route("/documents/<int:doc_id>/delete", methods=["POST"])
@login_required
def delete_document(doc_id):
    doc = AcademicDocument.query.get_or_404(doc_id)
    if doc.student_id == current_user.id:
        ExtractedMark.query.filter_by(document_id=doc.id).delete()
        db.session.delete(doc)
        db.session.commit()
        try:
            if os.path.exists(doc.file_path):
                os.remove(doc.file_path)
        except Exception as e:
            flash("Error deleting document.", "danger")
        flash("Document deleted.", "success")
    return redirect(url_for('student.predict'))


# --- NEW OCR & PREDICTION ROUTES ---

@student_bp.route("/predict", methods=["GET", "POST"])
@login_required
def predict():
    profile = StudentProfile.query.filter_by(user_id=current_user.id).first()
    student_subjects = get_profile_subjects(profile)
    active_by_id = {s.id: s for s in student_subjects}
    doc_count = AcademicDocument.query.filter_by(student_id=current_user.id).count()
    subject_snapshots = []
    for subject in student_subjects:
        snap = get_subject_performance_snapshot(current_user.id, subject.id)
        subject_snapshots.append({
            "subject": subject,
            "score": snap["score"],
            "source": snap["source"],
            "source_label": snap["source_label"],
            "has_real_score": snap["source"] != "missing",
        })
    eligible_subject_count = sum(1 for item in subject_snapshots if item["has_real_score"])

    # ── Dynamic preview values for ML Predictor header cards ──────────────────
    real_scores = [item["score"] for item in subject_snapshots if item["has_real_score"] and item["score"] is not None]
    computed_gpa = None
    gpa_source_label = ""
    if profile and profile.cumulative_gpa and profile.cumulative_gpa > 0:
        computed_gpa = profile.cumulative_gpa
        gpa_source_label = "from profile"
    elif real_scores:
        avg_score = sum(real_scores) / len(real_scores)
        computed_gpa = round((avg_score / 100.0) * 4.0, 2)
        gpa_source_label = "estimated from assessments"

    target_weekly_hours = float(profile.target_weekly_hours if profile and profile.target_weekly_hours else 14.0)
    study_hours_preview = f"{target_weekly_hours:.1f}h total (smart split)"

    today_local = local_today_for_user(current_user.id)
    sub_ids = [s.id for s in student_subjects]
    from app.models import Exam
    next_exam = Exam.query.filter(Exam.user_id == current_user.id, Exam.subject_id.in_(sub_ids), Exam.date >= today_local).order_by(Exam.date.asc()).first() if sub_ids else None
    if next_exam:
        exam_subj = Subject.query.get(next_exam.subject_id)
        days_left = (next_exam.date - today_local).days
        days_to_exam_preview = f"{days_left}d ({exam_subj.name if exam_subj else 'Exam'})"
    else:
        days_to_exam_preview = "30d (default)"

    last_log = StudyLog.query.filter_by(user_id=current_user.id).order_by(StudyLog.date.desc()).first()
    last_review = ReviewedChapter.query.filter_by(student_id=current_user.id, status="completed").order_by(ReviewedChapter.last_accessed_at.desc()).first()
    last_log_date = last_log.date if (last_log and last_log.date) else None
    last_review_date = last_review.last_accessed_at.date() if (last_review and last_review.last_accessed_at) else None
    most_recent = max(last_log_date, last_review_date) if (last_log_date and last_review_date) else (last_log_date or last_review_date)
    if most_recent:
        days_since = (today_local - most_recent).days
        days_since_study_preview = f"{days_since}d ago" if days_since > 0 else "Today"
    else:
        days_since_study_preview = "7d (no logs)"

    def render_predict(**kwargs):
        context = {
            "profile": profile,
            "doc_count": doc_count,
            "student_subjects": student_subjects,
            "subject_snapshots": subject_snapshots,
            "eligible_subject_count": eligible_subject_count,
            "computed_gpa": computed_gpa,
            "gpa_source_label": gpa_source_label,
            "study_hours_preview": study_hours_preview,
            "days_to_exam_preview": days_to_exam_preview,
            "days_since_study_preview": days_since_study_preview,
            "is_ocr": False,
            "selected_subject_ids": [],
            "batch_results": [],
            "skipped_subjects": [],
        }
        context.update(kwargs)
        return render_template("student/predict.html", **context)

    if request.method == "POST":
        try:
            selected_ids = []
            for raw_id in request.form.getlist("subject_ids[]"):
                try:
                    subject_id = int(raw_id)
                except (TypeError, ValueError):
                    continue
                if subject_id in active_by_id and subject_id not in selected_ids:
                    selected_ids.append(subject_id)

            if not selected_ids:
                flash("Select at least one profile subject.", "warning")
                return render_predict()

            raw_gpa = float(computed_gpa if computed_gpa is not None else 0.0)
            profile_grade = raw_gpa * 25 if raw_gpa <= 4.0 else raw_gpa
            attendance = float(profile.attendance_pct if profile and profile.attendance_pct is not None else 85.0)
            
            model = load_ml_model("random_forest")
            scaler = load_ml_model("scaler")
            if not model or not scaler:
                flash("Random Forest model not trained yet, using fallback prediction.", "warning")

            available_hours = get_available_study_hours_total(current_user.id)
            if available_hours <= 0:
                available_hours = target_weekly_hours

            fallback_study_hours = max(1.0, available_hours / max(1, len(selected_ids)))
            three_weeks_ago = today_local - timedelta(days=21)

            # Pass 1: Run model.predict_proba for eligible subjects to extract continuous risk_score
            eval_subjects = []
            for s_id in selected_ids:
                subj = active_by_id[s_id]
                snap = get_subject_performance_snapshot(current_user.id, subj.id)
                if snap["source"] != "missing" and snap["score"] is not None:
                    perf_score = snap["score"]
                    diff = float(subj.difficulty_level or 3.0)

                    # Check StudyLog for actual recent average weekly hours for this subject
                    subj_logs = StudyLog.query.filter(
                        StudyLog.user_id == current_user.id,
                        StudyLog.subject_id == subj.id,
                        StudyLog.date >= three_weeks_ago
                    ).all()
                    if subj_logs:
                        total_logged = sum(l.duration_hours for l in subj_logs if l.duration_hours)
                        initial_study_hours = round(max(0.5, total_logged / 3.0), 1)
                    else:
                        initial_study_hours = fallback_study_hours

                    feat_pre = get_subject_features(current_user.id, subj.name, perf_score, attendance, initial_study_hours, diff, 30, None)
                    r_score = 0.5
                    if model and scaler:
                        f_scaled = scaler.transform(np.array([feat_pre]))
                        if hasattr(model, "predict_proba"):
                            probs = model.predict_proba(f_scaled)[0]
                            r_score = float(0.0 * probs[0] + 0.5 * probs[1] + 1.0 * probs[2])
                    eval_subjects.append({
                        "id": subj.id,
                        "name": subj.name,
                        "difficulty": diff,
                        "previous_grade": perf_score,
                        "risk_score": r_score,
                    })

            # Pass 2: Calculate proportional risk-weighted hour allocations
            allocations = calculate_subject_hour_allocations(eval_subjects, available_hours)

            batch_results = []
            skipped_subjects = []
            session_subjects = []
            session_marks = []
            prediction_rank = {"low": 0, "medium": 1, "high": 2}
            highest_result = "Pass"

            for subject_id in selected_ids:
                subject = active_by_id[subject_id]
                snapshot = get_subject_performance_snapshot(current_user.id, subject.id)
                if snapshot["source"] == "missing" or snapshot["score"] is None:
                    skipped_subjects.append({
                        "subject": subject.name,
                        "reason": f"Skipped: {subject.name} (no assessment found)",
                    })
                    continue

                performance_score = snapshot["score"]
                difficulty = float(subject.difficulty_level or 3.0)
                per_subject_weekly_hours = allocations.get(subject.name, max(1.0, target_weekly_hours / max(1, len(selected_ids))))

                features = get_subject_features(
                    current_user.id,
                    subject.name,
                    performance_score,
                    attendance,
                    per_subject_weekly_hours,
                    difficulty,
                    30,
                    None,
                )
                days_until_exam = int(features[4])
                days_since_last_studied = int(features[5])

                confidence = 85.0
                risk_score = 0.5
                if model and scaler:
                    f_scaled = scaler.transform(np.array([features]))
                    if hasattr(model, "predict_proba"):
                        probs = model.predict_proba(f_scaled)[0]
                        risk_score = float(0.0 * probs[0] + 0.5 * probs[1] + 1.0 * probs[2])
                        risk_pred = int(np.argmax(probs))
                        confidence = round(float(np.max(probs)) * 100, 1)
                    else:
                        risk_pred = min(2, max(0, int(model.predict(f_scaled)[0])))
                        risk_score = [0.1, 0.5, 0.9][risk_pred]
                else:
                    risk_pred = 1

                risk_level = ["low", "medium", "high"][risk_pred]
                prediction_result = ["Pass", "At Risk", "Fail"][risk_pred]
                if prediction_rank[risk_level] > prediction_rank.get(highest_result.lower().replace("at risk", "medium").replace("pass", "low").replace("fail", "high"), 0):
                    highest_result = prediction_result
                risk_pct = round(risk_score * 100, 1)
                predicted_grade = grade_from_score(performance_score)

                raw_inputs = {
                    "subject_id": subject.id,
                    "subject_name": subject.name,
                    "performance_score": performance_score,
                    "performance_source": snapshot["source"],
                    "profile_grade": profile_grade,
                    "attendance": attendance,
                    "weekly_study_hours": per_subject_weekly_hours,
                    "subject_difficulty": difficulty,
                    "days_until_exam": days_until_exam,
                    "days_since_last_studied": days_since_last_studied,
                    "risk_score": risk_score,
                    "risk_pct": risk_pct,
                    "feature_order": [
                        "previous_grade_from_assessment",
                        "attendance",
                        "difficulty",
                        "weekly_study_hours",
                        "days_until_exam",
                        "days_since_last_studied",
                        "completion_rate",
                    ],
                    "features": features,
                }

                pred_record = Prediction(
                    user_id=current_user.id,
                    attendance_pct=attendance,
                    assignment_completion_pct=performance_score,
                    weekly_study_hours=per_subject_weekly_hours,
                    total_logged_study_hours=per_subject_weekly_hours,
                    study_days_last_240=0,
                    subject_difficulty=difficulty,
                    avg_exam_score_pct=performance_score,
                    midterm_score_pct=performance_score,
                    final_score_pct=performance_score,
                    assignment_avg_pct=performance_score,
                    year_of_study=profile.year_of_study if profile else 1,
                    cumulative_gpa=profile_grade,
                    predicted_risk_level=risk_level,
                    predicted_grade=predicted_grade,
                    level_of_study=profile.study_level if profile else None,
                    raw_inputs=json.dumps(raw_inputs),
                )
                db.session.add(pred_record)
                batch_results.append({
                    "subject": subject.name,
                    "risk_level": risk_level.title(),
                    "risk_pct": risk_pct,
                    "performance_score": round(performance_score, 1),
                    "performance_source": snapshot["source_label"],
                    "confidence": confidence,
                })
                session_subjects.append(subject.name)
                session_marks.append(round(performance_score))

            if not batch_results:
                db.session.rollback()
                flash("No selected subjects had real Assessment or marksheet scores. Run Assessment or upload a marksheet first.", "warning")
                return render_predict(
                    selected_subject_ids=selected_ids,
                    skipped_subjects=skipped_subjects,
                )

            db.session.commit()
            session["last_prediction"] = highest_result
            session["last_subjects"] = session_subjects
            session["last_marks"] = session_marks
            session["last_study_hours"] = per_subject_weekly_hours / 7.0

            flash(f"Generated {len(batch_results)} subject risk prediction(s).", "success")
            return render_predict(
                prediction_result=highest_result,
                model_used="Random Forest Classifier (random_forest.pkl)",
                batch_results=batch_results,
                skipped_subjects=skipped_subjects,
                selected_subject_ids=selected_ids,
                is_post=True,
            )
        except Exception as e:
            db.session.rollback()
            flash(f"Prediction error: {str(e)}", "danger")
            return render_predict()

    return render_predict()


@student_bp.route("/predict-legacy-disabled", methods=["GET", "POST"])
@login_required
def predict_legacy_disabled():
    return redirect(url_for("student.predict"))

def derive_features_from_marks(subjects, marks):
    """Convert extracted marksheet data into ML model input features."""
    avg_mark = sum(marks) / len(marks) if marks else 50
    lowest_mark = min(marks) if marks else 40
    highest_mark = max(marks) if marks else 80

    return {
        "previous_score": round(avg_mark, 1),       # Feature: avg mark
        "weak_subject_score": round(lowest_mark, 1), # Feature: worst subject
    }


def parse_marksheet(text):
    """
    Extracts subject names and marks from raw OCR text.
    Handles common Nepali marksheet formats (NEB, TU, Pokhara University).
    Returns two parallel lists: subjects[], marks[]
    """
    subjects = []
    marks = []

    lines = text.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Pattern 1: "Mathematics  75" or "English Language  68/100"
        match = re.search(
            r'([A-Za-z][A-Za-z\s\(\)]{3,40})\s+(\d{1,3})(?:\s*/\s*\d{1,3})?',
            line
        )
        if match:
            subject = match.group(1).strip()
            mark = int(match.group(2))

            # Filter noise — skip lines that look like headers/dates
            skip_keywords = ['date', 'roll', 'name', 'school', 'board',
                             'college', 'total', 'grand', 'serial', 'reg']
            if any(kw in subject.lower() for kw in skip_keywords):
                continue

            # Only accept realistic marks (0–100)
            if 0 <= mark <= 100:
                subjects.append(subject)
                marks.append(mark)

    return subjects, marks


def get_active_subject_match(user_id, detected_name):
    """Return the closest active profile subject plus a 0-1 confidence score."""
    detected = (detected_name or "").strip()
    if not detected:
        return None, 0.0

    profile = StudentProfile.query.filter_by(user_id=user_id).first()
    active = get_profile_subjects(profile)
    if not active:
        return None, 0.0

    detected_key = normalize_subject_name(detected)
    best_subject = None
    best_score = 0.0
    for subject in active:
        subject_key = normalize_subject_name(subject.name)
        if detected_key == subject_key:
            return subject, 1.0
        if detected_key in subject_key or subject_key in detected_key:
            score = 0.9
        else:
            score = SequenceMatcher(None, detected_key, subject_key).ratio()
        if score > best_score:
            best_subject = subject
            best_score = score
    return best_subject, best_score


def map_to_active_subject_name(user_id, detected_name):
    subject, confidence = get_active_subject_match(user_id, detected_name)
    return subject.name if subject and confidence >= 0.62 else detected_name


@student_bp.route("/ocr-extract", methods=["POST"])
@login_required
def ocr_extract():
    if 'marksheet' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
        
    file = request.files['marksheet']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
        
    filename = secure_filename(file.filename)
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    if ext not in ['pdf', 'jpg', 'jpeg', 'png']:
        return jsonify({"error": "Invalid file type. Only PDF and Images allowed."}), 400
        
    try:
        upload_dir = os.path.join(os.path.abspath(os.path.dirname(__file__)), '../../app/static/uploads', str(current_user.id))
        os.makedirs(upload_dir, exist_ok=True)
        unique_filename = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{filename}"
        filepath = os.path.join(upload_dir, unique_filename)
        file.save(filepath)
        
        file_type = 'pdf' if ext == 'pdf' else 'image'
        processor = MarksheetProcessor()
        marks_data, confidence = processor.process_file(filepath, file_type)

        profile = StudentProfile.query.filter_by(user_id=current_user.id).first()
        active_subjects = get_profile_subjects(profile)
        subject_options = [{"id": s.id, "name": s.name} for s in active_subjects]
        candidates = []
        for idx, m in enumerate(marks_data):
            pct = processor.convert_to_percentage(m['value'], m['full_marks'])
            if pct is None:
                continue
            matched_subject, match_confidence = get_active_subject_match(current_user.id, m['subject'])
            candidates.append({
                "index": idx,
                "original_subject": m["subject"],
                "matched_subject_id": matched_subject.id if matched_subject and match_confidence >= 0.62 else None,
                "matched_subject_name": matched_subject.name if matched_subject and match_confidence >= 0.62 else "",
                "extracted_value": str(m["value"]),
                "full_marks": str(m["full_marks"]),
                "percentage": pct,
                "row_confidence": float(m.get("confidence", confidence)),
                "match_confidence": round(float(match_confidence), 2),
                "raw_row": m.get("raw_row", ""),
            })

        session["pending_ocr_upload"] = {
            "filename": filename,
            "filepath": filepath,
            "file_type": ext,
            "confidence": confidence,
            "candidates": candidates,
        }

        # Bug 3: Compute low-confidence warning flag
        # Trigger when median match_confidence across all rows is below 0.50
        if candidates:
            sorted_confs = sorted(c["match_confidence"] for c in candidates)
            n = len(sorted_confs)
            median_conf = sorted_confs[n // 2] if n % 2 else (sorted_confs[n // 2 - 1] + sorted_confs[n // 2]) / 2
            low_confidence_warning = median_conf < 0.50
        else:
            low_confidence_warning = False

        return jsonify({
            "status": "preview",
            "candidates": candidates,
            "subject_options": subject_options,
            "overall_confidence": confidence,
            "low_confidence_warning": low_confidence_warning,
        })
        
    except Exception as e:
        return jsonify({
            "error": "OCR extraction failed. Please try a clearer marksheet image or PDF.",
            "details": str(e),
            "candidates": [],
        }), 200


@student_bp.route("/ocr-confirm", methods=["POST"])
@login_required
def ocr_confirm():
    pending = session.get("pending_ocr_upload")
    if not pending:
        return jsonify({"status": "error", "message": "No pending OCR upload to save."}), 400

    data = request.get_json(silent=True) or {}
    rows = data.get("rows", [])
    if not rows:
        return jsonify({"status": "error", "message": "No verified marks were submitted."}), 400

    profile = StudentProfile.query.filter_by(user_id=current_user.id).first()
    active_ids = {subject.id for subject in get_profile_subjects(profile)}
    candidate_by_index = {
        int(c["index"]): c for c in pending.get("candidates", [])
    }

    doc = AcademicDocument(
        student_id=current_user.id,
        document_type="marksheet",
        document_name=pending.get("filename"),
        file_path=pending.get("filepath"),
        file_type=pending.get("file_type"),
        institution_name="OCR Upload",
        exam_year=local_now_for_user(current_user.id).year,
        extraction_confidence=float(pending.get("confidence") or 0.0),
        processed_at=datetime.utcnow(),
        is_verified=True,
    )
    db.session.add(doc)
    db.session.flush()

    saved = []
    total_pct = 0.0
    for row in rows:
        try:
            candidate = candidate_by_index[int(row.get("index"))]
            subject_id = int(row.get("subject_id"))
            percentage = float(row.get("percentage"))
        except (TypeError, ValueError, KeyError):
            continue
        if subject_id not in active_ids or percentage < 0 or percentage > 100:
            continue
        subject = Subject.query.get(subject_id)
        if not subject:
            continue
        value = str(row.get("value") or candidate.get("extracted_value") or "")
        full_marks = str(row.get("full_marks") or candidate.get("full_marks") or "100")
        try:
            marks_obtained = float(value)
        except ValueError:
            marks_obtained = 0.0
        try:
            full_marks_num = float(full_marks)
        except ValueError:
            full_marks_num = 100.0
        em = ExtractedMark(
            document_id=doc.id,
            subject_name_original=candidate.get("original_subject"),
            subject_name_mapped=subject.name,
            marks_obtained=marks_obtained,
            full_marks=full_marks_num,
            percentage=round(percentage, 2),
            grade="" if value.replace('.', '', 1).isdigit() else value,
        )
        db.session.add(em)
        saved.append({"subject": subject.name, "percentage": round(percentage, 2)})
        total_pct += percentage

    if not saved:
        db.session.rollback()
        return jsonify({"status": "error", "message": "No valid verified subject rows were saved."}), 400

    doc.overall_percentage = round(total_pct / len(saved), 2)
    profile = StudentProfile.query.filter_by(user_id=current_user.id).first()
    if profile:
        profile.documents_uploaded = (profile.documents_uploaded or 0) + 1
        profile.prior_academic_score = doc.overall_percentage
    db.session.commit()
    session.pop("pending_ocr_upload", None)

    return jsonify({
        "status": "success",
        "message": f"Saved {len(saved)} verified marksheet score(s).",
        "saved": saved,
        "overall_percentage": doc.overall_percentage,
    })


@student_bp.route("/api/subject-performance/<int:subject_id>", methods=["GET"])
@login_required
def get_subject_performance(subject_id):
    is_active = StudentSubject.query.filter_by(
        user_id=current_user.id,
        subject_id=subject_id
    ).first()
    if not is_active:
        return jsonify({"status": "error", "message": "Subject is not active for this student."}), 403

    snapshot = get_subject_performance_snapshot(current_user.id, subject_id)
    return jsonify({
        "status": "success",
        "performance_score": snapshot["score"],
        "source": snapshot["source"],
        "source_label": snapshot["source_label"],
        "has_real_score": snapshot["source"] != "missing",
    })


@student_bp.route("/generate-planner", methods=["POST"])
@login_required
def generate_planner():
    subjects     = request.form.getlist('subjects[]')       # list of selected subjects
    marks        = request.form.getlist('marks[]')          # parallel marks list
    free_slots   = request.form.get('free_slots_json')      # JSON of {day-hour: 'free'} grid
    latest_rows = []
    if not subjects:
        latest_rows = latest_prediction_rows(current_user.id)
        subjects = [row["subject_name"] for row in latest_rows]
        marks = [str(round(row["performance_score"])) for row in latest_rows]
    
    try:
        session_min  = int(request.form.get('session_length', 60))
    except ValueError:
        session_min = 60
        
    try:
        break_min    = int(request.form.get('break_length', 10))
    except ValueError:
        break_min = 10
        
    plan_dur     = request.form.get('plan_duration', '2 weeks')
    strategy     = request.form.get('priority_strategy', 'Weakest subjects first')
    revision_day = request.form.get('revision_day', 'Saturday')
    prediction   = session.get('last_prediction', 'At Risk')
    if latest_rows:
        risk_rank = {"low": 0, "medium": 1, "high": 2}
        worst = max(latest_rows, key=lambda row: risk_rank.get(row["risk_level"], 1), default=None)
        if worst:
            prediction = worst["prediction_result"]

    # Parse JSON free slots and calculate daily average
    free_hours_per_day = 6.0
    if free_slots:
        try:
            free_slots_dict = json.loads(free_slots)
            free_hours_per_day = len([v for v in free_slots_dict.values() if v == 'free']) / 7.0
            if free_hours_per_day == 0:
                free_hours_per_day = 6.0
        except Exception:
            pass

    ctx = get_learning_context(current_user.id)
    user_weak_topics = ctx.weak_topics if hasattr(ctx, "weak_topics") else []
    peak_focus = ctx.profile.peak_focus_time if (ctx.profile and ctx.profile.peak_focus_time) else "Morning"

    # Fetch real curriculum chapters for each enrolled subject
    subject_chapters = {}
    for s_name in subjects:
        s_obj = Subject.query.filter(Subject.name.ilike(s_name)).first()
        if s_obj:
            chs = Chapter.query.filter_by(subject_id=s_obj.id).order_by(Chapter.order_index).all()
            if chs:
                subject_chapters[s_name] = [ch.title for ch in chs]

    planner_data = generate_study_planner(
        prediction_result=prediction,
        subjects=subjects,
        marks=[int(m) if m.isdigit() else 50 for m in marks],
        study_hours_per_day=free_hours_per_day,
        session_length=session_min,
        strategy=strategy,
        revision_day=revision_day,
        free_slots_json=free_slots,
        weak_topics=user_weak_topics,
        subject_chapters=subject_chapters,
        peak_focus_time=peak_focus
    )

    # Build subject_ids for click-through study room linkage — read from context
    subject_ids = {}
    if ctx.profile:
        db_subjects = Subject.query.filter_by(
            level_of_study=ctx.profile.level_of_study,
            program=ctx.profile.program
        ).all()
        for s in db_subjects:
            subject_ids[s.name] = s.id
            subject_ids[s.name.lower()] = s.id
            subject_ids[s.code] = s.id

    for name in subjects:
        if name not in subject_ids and name.lower() not in subject_ids:
            s_match = Subject.query.filter(Subject.name.ilike(name)).first()
            if s_match:
                subject_ids[name] = s_match.id
                subject_ids[name.lower()] = s_match.id

    # ── Context: persist the plan — invalidates cached plan reference
    ctx.update_study_planner(planner_data)

    log_analysis = StudyLogAnalysis.query.filter_by(user_id=current_user.id).first()
    return render_template('student/planner.html', planner=planner_data, subject_ids=subject_ids, log_analysis=log_analysis)


@student_bp.route("/planner/log-hours", methods=["POST"])
@login_required
def planner_log_hours():
    subject_name = request.form.get("subject")
    try:
        hours = float(request.form.get("hours", 1.0))
    except ValueError:
        hours = 1.0

    # ── Context: log study hours — invalidates study_hours, streak, recent_activity caches
    ctx = get_learning_context(current_user.id)
    ctx.log_study_hours(subject_name, hours)

    return jsonify({"status": "success", "message": f"Logged {hours} hours of study for {subject_name}!"})


@student_bp.route("/study/<int:subject_id>", methods=["GET", "POST"])
@login_required
def study_subject(subject_id):
    subject = Subject.query.get_or_404(subject_id)

    # ── Context: shared learning state ───────────────────────────────────────
    ctx = get_learning_context(current_user.id)

    # Retrieve all chapters for this subject
    chapters = Chapter.query.filter_by(subject_id=subject.id).order_by(Chapter.chapter_number).all()
    if not chapters:
        try:
            chapters = ai_service.generate_chapters_for_subject(subject.id)
        except Exception as e:
            flash(f"Failed to generate chapter outline: {str(e)}", "danger")
            chapters = []

    # Fetch user progress for topics of this subject — read from context
    completed_topic_ids = ctx.completed_topic_ids

    # Fetch existing notes for this subject
    user_notes = StudentNote.query.filter_by(user_id=current_user.id, subject_id=subject.id).first()
    notes_content = user_notes.notes_content if user_notes else ""

    # Retrieve flashcards
    flashcards = Flashcard.query.filter_by(subject_id=subject.id).all()

    # Retrieve active topic and chapter if passed in URL
    topic_id = request.args.get("topic_id", type=int)
    active_chapter_id = None
    if topic_id:
        topic = Topic.query.get(topic_id)
        if topic and topic.chapter.subject_id == subject.id:
            active_chapter_id = topic.chapter_id

    return render_template(
        "student/study.html",
        subject=subject,
        chapters=chapters,
        completed_topic_ids=completed_topic_ids,
        notes_content=notes_content,
        flashcards=flashcards,
        profile=ctx.profile,
        active_chapter_id=active_chapter_id,
        active_topic_id=topic_id,
    )


@student_bp.route("/study/api/chapter/<int:chapter_id>/topics", methods=["GET"])
@login_required
def get_chapter_topics(chapter_id):
    chapter = Chapter.query.get_or_404(chapter_id)
    topics = Topic.query.filter_by(chapter_id=chapter.id).order_by(Topic.topic_number).all()

    if not topics:
        try:
            topics = ai_service.generate_topics_for_chapter(chapter.id)
        except Exception as e:
            return jsonify({"status": "error", "message": f"Failed to generate topics: {str(e)}"}), 500

    ctx = get_learning_context(current_user.id)
    completed_topic_ids = ctx.completed_topic_ids

    topics_list = []
    for t in topics:
        # Check if topic has learning material
        has_material = LearningMaterial.query.filter_by(topic_id=t.id).first() is not None
        topics_list.append({
            "id": t.id,
            "name": t.name,
            "topic_number": t.topic_number,
            "completed": t.id in completed_topic_ids,
            "has_material": has_material
        })

    return jsonify({
        "status": "success",
        "topics": topics_list
    })


@student_bp.route("/study/api/topic/<int:topic_id>", methods=["GET"])
@login_required
def get_topic_material(topic_id):
    route_name = "/study/api/topic/<int:topic_id>"
    logger.info("[STUDY ROOM] Accessing topic material. Route: %s, Topic ID: %d, User ID: %d", route_name, topic_id, current_user.id)
    
    topic = Topic.query.get_or_404(topic_id)
    chapter_id = topic.chapter_id
    subject_id = topic.chapter.subject_id if topic.chapter else None
    
    material = LearningMaterial.query.filter_by(topic_id=topic.id).first()
    
    if not material:
        logger.info("[STUDY ROOM] No learning material found in DB for Topic ID: %d. Returning not_found.", topic_id)
        return jsonify({"status": "not_found", "message": "No learning materials found for this topic."})
        
    logger.info("[STUDY ROOM] Material successfully retrieved. Material ID: %d, Topic ID: %d, Content length: %d", 
                material.id, topic_id, len(material.detailed_explanation or ""))
                
    flashcards = Flashcard.query.filter_by(chapter_id=topic.chapter_id).all()
    flashcards_list = [{"front": f.front, "back": f.back} for f in flashcards]
    
    bookmark = BookmarkedChapter.query.filter_by(student_id=current_user.id, topic_id=topic_id).first()
    progress = ReviewedChapter.query.filter_by(student_id=current_user.id, topic_id=topic_id).first()
    note = ChapterNote.query.filter_by(student_id=current_user.id, topic_id=topic_id).first()
    p_questions = PastQuestion.query.filter_by(topic_id=topic_id).all()
    past_questions_list = [{"question_text": pq.question_text, "exam_year": pq.exam_year} for pq in p_questions]

    return jsonify({
        "bookmarked": bookmark is not None,
        "progress_status": progress.status if progress else "not started",
        "notes_content": note.content if note else "",
        "past_questions": past_questions_list,
        "status": "success",
        "material": {
            "title": material.title,
            "learning_objectives": material.learning_objectives,
            "introduction": material.introduction,
            "detailed_explanation": material.detailed_explanation,
            "important_definitions": material.important_definitions,
            "concepts": material.concepts,
            "examples": material.examples,
            "worked_examples": material.worked_examples,
            "real_life_applications": material.real_life_applications,
            "diagrams": material.diagrams,
            "key_points": material.key_points,
            "important_facts": material.important_facts,
            "formulae": material.formulae,
            "common_mistakes": material.common_mistakes,
            "mcqs_json": material.mcqs_json,
            "short_questions_json": material.short_questions_json,
            "long_questions_json": material.long_questions_json,
            "critical_thinking_questions_json": material.critical_thinking_questions_json,
            "summary": material.summary,
            "revision_notes": material.revision_notes,
            "estimated_reading_time": material.estimated_reading_time,
            "difficulty_level": material.difficulty_level,
            "learning_outcomes": material.learning_outcomes
        },
        "flashcards": flashcards_list
    })


@student_bp.route("/study/api/topic/<int:topic_id>/generate-ai", methods=["POST"])
@login_required
def generate_ai_topic_material(topic_id):
    route_name = "/study/api/topic/<int:topic_id>/generate-ai"
    logger.info("[STUDY ROOM] Triggered AI generation request. Route: %s, Topic ID: %d, User ID: %d", route_name, topic_id, current_user.id)
    
    topic = Topic.query.get_or_404(topic_id)
    chapter_id = topic.chapter_id
    subject_id = topic.chapter.subject_id if topic.chapter else None
    
    material = LearningMaterial.query.filter_by(topic_id=topic.id).first()
    
    if not material:
        logger.info("[STUDY ROOM] No existing material found for Topic ID: %d. Calling AI generation pipeline.", topic_id)
        try:
            material = ai_service.generate_lesson_material(topic_id)
            logger.info("[STUDY ROOM] AI Generation and DB save successful. Material ID: %d, Topic ID: %d, Subject ID: %s, Chapter ID: %s", 
                        material.id, topic_id, subject_id, chapter_id)
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            logger.error("[STUDY ROOM] AI Generation failed. Topic ID: %d, Error: %s, Traceback: %s", topic_id, e, tb)
            return jsonify({"status": "error", "message": f"Failed to generate lesson: {str(e)}"}), 500
            
    if not material:
        logger.error("[STUDY ROOM] AI Generation returned null material without raising exception. Topic ID: %d", topic_id)
        return jsonify({"status": "error", "message": "Failed to create lesson material record."}), 500
        
    flashcards = Flashcard.query.filter_by(chapter_id=topic.chapter_id).all()
    flashcards_list = [{"front": f.front, "back": f.back} for f in flashcards]
    
    bookmark = BookmarkedChapter.query.filter_by(student_id=current_user.id, topic_id=topic_id).first()
    progress = ReviewedChapter.query.filter_by(student_id=current_user.id, topic_id=topic_id).first()
    note = ChapterNote.query.filter_by(student_id=current_user.id, topic_id=topic_id).first()
    p_questions = PastQuestion.query.filter_by(topic_id=topic_id).all()
    past_questions_list = [{"question_text": pq.question_text, "exam_year": pq.exam_year} for pq in p_questions]

    return jsonify({
        "bookmarked": bookmark is not None,
        "progress_status": progress.status if progress else "not started",
        "notes_content": note.content if note else "",
        "past_questions": past_questions_list,
        "status": "success",
        "material": {
            "title": material.title,
            "learning_objectives": material.learning_objectives,
            "introduction": material.introduction,
            "detailed_explanation": material.detailed_explanation,
            "important_definitions": material.important_definitions,
            "concepts": material.concepts,
            "examples": material.examples,
            "worked_examples": material.worked_examples,
            "real_life_applications": material.real_life_applications,
            "diagrams": material.diagrams,
            "key_points": material.key_points,
            "important_facts": material.important_facts,
            "formulae": material.formulae,
            "common_mistakes": material.common_mistakes,
            "mcqs_json": material.mcqs_json,
            "short_questions_json": material.short_questions_json,
            "long_questions_json": material.long_questions_json,
            "critical_thinking_questions_json": material.critical_thinking_questions_json,
            "summary": material.summary,
            "revision_notes": material.revision_notes,
            "estimated_reading_time": material.estimated_reading_time,
            "difficulty_level": material.difficulty_level,
            "learning_outcomes": material.learning_outcomes
        },
        "flashcards": flashcards_list
    })


@student_bp.route("/study/save-notes", methods=["POST"])
@login_required
def study_save_notes():
    subject_id = int(request.form.get("subject_id"))
    content = request.form.get("notes_content", "")
    
    note = StudentNote.query.filter_by(user_id=current_user.id, subject_id=subject_id).first()
    if not note:
        note = StudentNote(user_id=current_user.id, subject_id=subject_id, notes_content=content)
        db.session.add(note)
    else:
        note.notes_content = content
        note.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"status": "success", "message": "Notes saved successfully!"})


@student_bp.route("/study/toggle-topic", methods=["POST"])
@login_required
def study_toggle_topic():
    topic_id = int(request.form.get("topic_id"))
    completed = request.form.get("completed") == "true"

    # ── Context: toggle lesson completion — invalidates progress + achievement caches
    ctx = get_learning_context(current_user.id)
    progress = ctx.toggle_topic_completed(topic_id, completed)

    return jsonify({"status": "success", "completed": progress.is_completed})


@student_bp.route("/study/submit-quiz", methods=["POST"])
@login_required
def study_submit_quiz():
    topic_id = int(request.form.get("topic_id"))
    material = LearningMaterial.query.filter_by(topic_id=topic_id).first()
    if not material or not material.mcqs_json:
        return jsonify({"status": "error", "message": "No quiz found for this topic."}), 404

    mcqs = json.loads(material.mcqs_json)
    user_answers = request.form.getlist("answers[]")

    correct_count = 0
    total = len(mcqs)
    results = []

    for idx, q in enumerate(mcqs):
        user_ans = user_answers[idx] if idx < len(user_answers) else ""
        correct = (user_ans == q["ans"])
        if correct:
            correct_count += 1
        results.append({
            "question": q["q"],
            "options": {"A": q["a"], "B": q["b"], "C": q["c"], "D": q["d"]},
            "correct_ans": q["ans"],
            "user_ans": user_ans,
            "is_correct": correct,
            "explanation": q.get("exp", "No explanation available.")
        })

    topic = Topic.query.get(topic_id)
    chapter = Chapter.query.get(topic.chapter_id)
    score_pct = (correct_count / total) * 100.0 if total > 0 else 0

    # ── Context: save quiz score — invalidates quiz + strong/weak subject caches
    ctx = get_learning_context(current_user.id)
    ctx.save_quiz_score(chapter.subject_id, score_pct, total)

    return jsonify({
        "status": "success",
        "score_pct": score_pct,
        "correct_count": correct_count,
        "total": total,
        "results": results,
    })


@student_bp.route("/planner/adapt-regenerate", methods=["POST"])
@login_required
def planner_adapt_regenerate():
    from app.utils.log_analyzer import analyze_student_logs
    
    # 1. Run analysis
    analysis = analyze_student_logs(current_user.id)
    
    # Get last plan
    last_plan = StudyPlan.query.filter_by(student_id=current_user.id).order_by(StudyPlan.generated_at.desc()).first()
    
    if not last_plan or not last_plan.plan_data:
        flash("No active study plan found to adapt. Generate a plan first.", "warning")
        return redirect(url_for('student.dashboard'))
        
    try:
        plan_dict = json.loads(last_plan.plan_data)
        subjects = [sp["subject"] for sp in plan_dict.get("subject_priorities", [])]
        marks = [sp["mark"] for sp in plan_dict.get("subject_priorities", [])]
        
        # Adapt study hours
        original_daily_hours = plan_dict.get("recommended_daily_hours", 4.0)
        
        if analysis.diverges_significantly:
            adapted_daily_hours = max(2.0, round(original_daily_hours * 0.8, 1))
            msg = f"Logged hours diverged from original targets. Daily study hours adapted down from {original_daily_hours}h to {adapted_daily_hours}h to optimize study load and avoid fatigue."
        else:
            adapted_daily_hours = original_daily_hours
            msg = "Study plan updated to align with log performance."
            
        # ── DB fallback for prediction (mirrors the pattern at line 2834) ──────
        adapt_prediction = session.get('last_prediction')
        if not adapt_prediction:
            latest_pred = (
                Prediction.query
                .filter_by(student_id=current_user.id)
                .order_by(Prediction.created_at.desc())
                .first()
            )
            if latest_pred:
                adapt_prediction = ["Pass", "At Risk", "Fail"][{"low": 0, "medium": 1, "high": 2}.get(latest_pred.predicted_risk_level, 1)]
            else:
                adapt_prediction = 'At Risk'
        ctx_adapt = get_learning_context(current_user.id)
        user_weak_topics = ctx_adapt.weak_topics if hasattr(ctx_adapt, "weak_topics") else []
        peak_focus = ctx_adapt.profile.peak_focus_time if (ctx_adapt.profile and ctx_adapt.profile.peak_focus_time) else "Morning"

        subject_chapters = {}
        for s_name in subjects:
            s_obj = Subject.query.filter(Subject.name.ilike(s_name)).first()
            if s_obj:
                chs = Chapter.query.filter_by(subject_id=s_obj.id).order_by(Chapter.order_index).all()
                if chs:
                    subject_chapters[s_name] = [ch.title for ch in chs]

        planner_data = generate_study_planner(
            prediction_result=adapt_prediction,
            subjects=subjects,
            marks=marks,
            study_hours_per_day=adapted_daily_hours,
            session_length=plan_dict.get("session_length", 60),
            strategy=plan_dict.get("priority_strategy", "Weakest subjects first"),
            revision_day=plan_dict.get("revision_day", "Saturday"),
            free_slots_json=plan_dict.get("free_slots_json"),
            weak_topics=user_weak_topics,
            subject_chapters=subject_chapters,
            peak_focus_time=peak_focus
        )
        
        planner_data["planner_message"] = msg
        
        # Save adapted plan
        new_plan = StudyPlan(
            student_id=current_user.id,
            plan_data=json.dumps(planner_data),
            generated_at=datetime.utcnow()
        )
        db.session.add(new_plan)
        db.session.commit()
        
        # Build subject IDs map
        subject_ids = {}
        profile = StudentProfile.query.filter_by(user_id=current_user.id).first()
        if profile:
            lvl = profile.level_of_study
            db_lvl = lvl
            if lvl == "Class 10":
                db_lvl = "Class 10 (Secondary Education Examination - SEE)"
            elif lvl == "Class 12":
                db_lvl = "Class 12 (National Examination Board - NEB)"
            db_subjects = Subject.query.filter_by(
                level_of_study=db_lvl,
                program=profile.program
            ).all()
            for s in db_subjects:
                subject_ids[s.name] = s.id
                subject_ids[s.name.lower()] = s.id
                subject_ids[s.code] = s.id

        flash("Weekly planner adapted and regenerated successfully!", "success")
        log_analysis = StudyLogAnalysis.query.filter_by(user_id=current_user.id).first()
        return render_template('student/planner.html', planner=planner_data, subject_ids=subject_ids, log_analysis=log_analysis)
    except Exception as e:
        flash(f"Error adapting planner: {str(e)}", "danger")
        return redirect(url_for('student.dashboard'))


@student_bp.route("/api/availability", methods=["GET"])
@login_required
def get_availability():
    slots = AvailabilitySlot.query.filter_by(user_id=current_user.id).all()
    slots_list = [{
        "id": s.id,
        "day_of_week": s.day_of_week,
        "start_time": s.start_time,
        "end_time": s.end_time,
        "slot_type": s.slot_type,
        "category": s.category or s.slot_type,  # fallback to slot_type for old rows
        "custom_label": s.custom_label or "",
        "is_overnight": bool(s.is_overnight)
    } for s in slots]
    return jsonify({"status": "success", "slots": slots_list})


# Valid 7 categories the user can assign
VALID_CATEGORIES = {"Sleep", "Class/Academic", "Sports", "Social/Hangout",
                    "Entertainment", "Personal/Chores", "Other"}


DAY_NAME_TO_SCHEDULE_IDX = {
    'Monday': 0, 'Tuesday': 1, 'Wednesday': 2, 'Thursday': 3,
    'Friday': 4, 'Saturday': 5, 'Sunday': 6
}


def _slot_minutes(start_time, end_time):
    sh, sm = [int(part) for part in start_time.split(":")]
    eh, em = [int(part) for part in end_time.split(":")]
    return sh * 60 + sm, eh * 60 + em


def _minutes_to_time_str(total_minutes):
    total_minutes = total_minutes % 1440
    return f"{total_minutes // 60:02d}:{total_minutes % 60:02d}"


def _hour_range_for_slot(start_time, end_time):
    start_mins, end_mins = _slot_minutes(start_time, end_time)
    return _hour_range_for_minutes(start_mins, end_mins)


def _hour_range_for_minutes(start_mins, end_mins):
    start_day_offset = start_mins // 1440
    end_day_offset = end_mins // 1440
    start_mins = start_mins % 1440
    end_mins = end_mins % 1440
    start_hour = start_mins // 60
    end_hour = end_mins // 60
    end_minute = end_mins % 60
    if start_day_offset == end_day_offset and start_mins < end_mins:
        final_hour = end_hour if end_minute > 0 else end_hour - 1
        return [(start_day_offset, h) for h in range(start_hour, final_hour + 1) if 0 <= h < 24]
    final_hour = end_hour if end_minute > 0 else end_hour - 1
    ranges = [(start_day_offset, h) for h in range(start_hour, 24)]
    ranges.extend((end_day_offset, h) for h in range(0, final_hour + 1) if 0 <= h < 24)
    return ranges


def get_available_study_hours_by_day(user_id):
    """
    Single source of truth for schedulable study hours.
    Availability is every hour not covered by Sleep/Class/etc commitments.
    """
    blocked = {i: set() for i in range(7)}
    profile = StudentProfile.query.filter_by(user_id=user_id).first()
    commute_buffer = int(getattr(profile, "commute_buffer_minutes", 0) or 0)
    slots = AvailabilitySlot.query.filter_by(user_id=user_id).all()
    for slot in slots:
        day_idx = DAY_NAME_TO_SCHEDULE_IDX.get(slot.day_of_week)
        if day_idx is None:
            continue
        category = slot.category or slot.slot_type or "Other"
        if category == "Study":
            # Legacy rows mean explicit free time; ignore them because free time is now inverse-derived.
            continue
        try:
            start_time = slot.start_time
            end_time = slot.end_time
            custom_label = (slot.custom_label or "").lower()
            needs_commute = (
                commute_buffer > 0
                and (
                    category == "Class/Academic"
                    or (category == "Other" and any(term in custom_label for term in ("work", "college", "campus", "job")))
                )
            )
            if needs_commute:
                start_mins, end_mins = _slot_minutes(slot.start_time, slot.end_time)
                ranges = _hour_range_for_minutes(start_mins - commute_buffer, end_mins + commute_buffer)
            else:
                ranges = _hour_range_for_slot(start_time, end_time)
            for day_offset, hour in ranges:
                blocked[(day_idx + day_offset) % 7].add(hour)
        except Exception:
            logger.debug("Skipping malformed availability slot %s", getattr(slot, "id", None), exc_info=True)
    return {day: [h for h in range(24) if h not in blocked[day]] for day in range(7)}


def get_available_study_hours_total(user_id):
    return float(sum(len(hours) for hours in get_available_study_hours_by_day(user_id).values()))


@student_bp.route("/api/availability", methods=["POST"])
@login_required
def update_availability():
    data = request.json
    if not isinstance(data, list):
        return jsonify({"status": "error", "message": "Invalid request body: expected a list of slots."}), 400

    try:
        valid_slots = []
        for index, item in enumerate(data):
            day = item.get("day_of_week")
            start = item.get("start_time")
            end = item.get("end_time")
            category = item.get("category") or item.get("slot_type", "")
            custom_label = (item.get("custom_label") or "").strip()[:80]

            if not day or not start or not end or not category:
                return jsonify({"status": "error",
                                "message": f"Slot at index {index} is missing required fields."}), 400

            if not re.match(r"^\d{2}:\d{2}$", start) or not re.match(r"^\d{2}:\d{2}$", end):
                return jsonify({"status": "error",
                                "message": f"Invalid time format in slot at index {index}. Expected HH:MM."}), 400

            # Normalize legacy values from older clients into the seven-category model.
            if category in ("Busy", "Study"):
                category = "Other"
            if category not in VALID_CATEGORIES:
                category = "Other"

            # Map to slot_type for scheduling engine: Sleep stays Sleep, everything else is Busy
            slot_type_value = "Sleep" if category == "Sleep" else "Busy"

            is_over_n = start > end
            valid_slots.append(AvailabilitySlot(
                user_id=current_user.id,
                day_of_week=day,
                start_time=start,
                end_time=end,
                slot_type=slot_type_value,
                category=category,
                custom_label=custom_label if category == "Other" else None,
                is_overnight=is_over_n
            ))

        AvailabilitySlot.query.filter_by(user_id=current_user.id).delete()
        for new_slot in valid_slots:
            db.session.add(new_slot)
        db.session.commit()
        return jsonify({"status": "success",
                        "message": f"Successfully updated {len(valid_slots)} availability slots!"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": f"Failed to update availability: {str(e)}"}), 500


@student_bp.route("/api/availability/summary", methods=["GET"])
@login_required
def availability_summary():
    """Return total weekly hours per category for the dashboard widget."""
    slots = AvailabilitySlot.query.filter_by(user_id=current_user.id).all()
    totals = {}
    for s in slots:
        cat = s.category or s.slot_type or "Other"
        try:
            sh = int(s.start_time.split(":")[0]) * 60 + int(s.start_time.split(":")[1])
            eh = int(s.end_time.split(":")[0]) * 60 + int(s.end_time.split(":")[1])
            dur = ((1440 - sh) + eh) / 60.0 if sh > eh else (eh - sh) / 60.0
        except Exception:
            dur = 0.0
        totals[cat] = round(totals.get(cat, 0.0) + dur, 2)
    return jsonify({"status": "success", "summary": totals})


@student_bp.route("/api/curriculum-data", methods=["GET"])
def get_curriculum_data():
    from app.models import EducationLevel, Faculty, CurriculumProgram
    country = request.args.get("country")
    curriculum = request.args.get("curriculum")
    level = request.args.get("level")
    program = request.args.get("program")
    nepal_levels = ["Class 6", "Class 7", "Class 8", "Class 9", "Class 10", "Class 11", "Class 12", "Bachelors", "Masters"]
    
    if not country:
        countries = [r[0] for r in db.session.query(Subject.country).distinct().all() if r[0]]
        # also check active universities/levels countries
        for el_country in db.session.query(EducationLevel.country).filter_by(is_active=True).distinct().all():
            if el_country[0] and el_country[0] not in countries:
                countries.append(el_country[0])
        # Always include the standard fallback countries
        std_countries = ["Nepal", "United States", "United Kingdom", "Australia", "Canada", "India"]
        for c in std_countries:
            if c not in countries:
                countries.append(c)
        return jsonify({"countries": sorted(list(set(countries)))})
        
    if not curriculum:
        curricula = [r[0] for r in db.session.query(Subject.curriculum).filter_by(country=country).distinct().all() if r[0]]
        if country == "Nepal" and "NEB/CTEVT" not in curricula:
            curricula.append("NEB/CTEVT")
        return jsonify({"curricula": sorted(list(set(curricula)))})
        
    if not level:
        levels_db = EducationLevel.query.filter_by(country=country, is_active=True).order_by(EducationLevel.sort_order.asc()).all()
        if levels_db:
            return jsonify({"levels": [l.name for l in levels_db]})
        if country == "Nepal":
            return jsonify({"levels": nepal_levels})
        levels = [r[0] for r in db.session.query(Subject.level_of_study).filter(
            Subject.country == country,
            Subject.curriculum == curriculum
        ).distinct().all() if r[0]]
        return jsonify({"levels": sorted(levels)})
        
    if not program:
        if country == "Nepal":
            if level in ("Class 11", "Class 12"):
                facs_db = Faculty.query.filter_by(country="Nepal", is_active=True).filter((Faculty.level_name == level) | (Faculty.level_name == None)).order_by(Faculty.sort_order.asc()).all()
                if facs_db:
                    return jsonify({"programs": [f.name for f in facs_db]})
                programs = sorted(set(NEPAL_FACULTY_SUBJECT_MAP.keys()) | set(NEPAL_FACULTY_SUBJECT_MAP_C12.keys()))
                return jsonify({"programs": programs})
            if level == "Bachelors":
                progs_db = CurriculumProgram.query.filter_by(level_name="Bachelors", country="Nepal", is_active=True).order_by(CurriculumProgram.sort_order.asc()).all()
                if progs_db:
                    return jsonify({"programs": [p.name for p in progs_db]})
                return jsonify({"programs": ["BBA", "BCA", "BE Computer", "BE Civil", "BIT", "BSc CSIT", "BSc Nursing", "BTech", "MBBS"]})
            if level == "Masters":
                progs_db = CurriculumProgram.query.filter_by(level_name="Masters", country="Nepal", is_active=True).order_by(CurriculumProgram.sort_order.asc()).all()
                if progs_db:
                    return jsonify({"programs": [p.name for p in progs_db]})
                return jsonify({"programs": ["MBA", "MCA", "MIT", "MSc Computer Science"]})
            return jsonify({"programs": []})
        programs = [r[0] for r in db.session.query(Subject.program).filter(
            Subject.country == country,
            Subject.curriculum == curriculum,
            Subject.level_of_study == level
        ).distinct().all() if r[0]]
        return jsonify({"programs": sorted(programs)})
        
    semesters = [r[0] for r in db.session.query(Subject.semester).filter(
        Subject.country == country,
        Subject.curriculum == curriculum,
        Subject.level_of_study == level,
        Subject.program == program
    ).distinct().all() if r[0]]
    if country == "Nepal" and level == "Bachelors" and not semesters:
        semesters = [f"Semester {i}" for i in range(1, 9)]
    elif country == "Nepal" and level == "Masters" and not semesters:
        semesters = [f"Semester {i}" for i in range(1, 5)]
    return jsonify({"semesters": sorted(semesters)})


@student_bp.route("/api/taxonomy", methods=["GET"])
def get_taxonomy():
    from app.models import EducationLevel, University, Faculty, CurriculumProgram
    import json
    
    # 1. Fetch active education levels
    levels_db = EducationLevel.query.filter_by(is_active=True).order_by(EducationLevel.sort_order.asc()).all()
    education_levels = {}
    countries = set()
    for l in levels_db:
        countries.add(l.country)
        if l.country not in education_levels:
            education_levels[l.country] = []
        education_levels[l.country].append(l.name)
    
    # Fallback to standard countries if database is empty or missing countries
    std_countries = ["Nepal", "United States", "United Kingdom", "Australia", "Canada", "India"]
    for c in std_countries:
        countries.add(c)
        if c not in education_levels:
            education_levels[c] = ["Class 6", "Class 7", "Class 8", "Class 9", "Class 10", "Class 11", "Class 12", "Bachelors", "Masters"]
            
    if "__default__" not in education_levels:
        education_levels["__default__"] = ["Class 6", "Class 7", "Class 8", "Class 9", "Class 10", "Class 11", "Class 12", "Bachelors", "Masters"]
        
    # 2. Fetch active universities
    unis_db = University.query.filter_by(is_active=True).order_by(University.sort_order.asc()).all()
    universities = {}
    for u in unis_db:
        if u.country not in universities:
            universities[u.country] = []
        universities[u.country].append(u.name)
    # Default list for Nepal if empty
    if "Nepal" not in universities:
        universities["Nepal"] = [
            "Tribhuvan University (TU)", "Kathmandu University (KU)", "Purbanchal University (PU)",
            "Pokhara University (PokU)", "Mid-Western University", "Far-Western University",
            "Agriculture and Forestry University (AFU)", "Nepal Sanskrit University",
            "Foreign-Affiliated", "Other"
        ]
        
    # 3. Fetch active faculties — only those for Class 11 / Class 12 (or level-agnostic ones).
    #    Bachelors/Masters use CurriculumProgram, not Faculty, so do NOT include them here.
    from sqlalchemy import or_
    facs_db = Faculty.query.filter_by(country="Nepal", is_active=True).filter(
        or_(
            Faculty.level_name == "Class 11",
            Faculty.level_name == "Class 12",
            Faculty.level_name == None  # noqa: E711  — level-agnostic entries
        )
    ).order_by(Faculty.sort_order.asc()).all()
    neb_general = ["Science Faculty", "Management Faculty (Commerce)", "Humanities and Social Sciences Faculty (Arts)", "Law Faculty", "Education Faculty"]
    neb_technical = []
    for f in facs_db:
        if f.name not in neb_general:
            neb_technical.append(f.name)
            
    # 4. Fetch programs
    bachelors_db = CurriculumProgram.query.filter_by(level_name="Bachelors", is_active=True).order_by(CurriculumProgram.sort_order.asc()).all()
    masters_db = CurriculumProgram.query.filter_by(level_name="Masters", is_active=True).order_by(CurriculumProgram.sort_order.asc()).all()
    
    bachelors_programs = [p.name for p in bachelors_db]
    masters_programs = [p.name for p in masters_db]
    
    programs_with_duration = []
    duration_options = {}
    
    all_programs_db = CurriculumProgram.query.filter_by(is_active=True).all()
    for p in all_programs_db:
        if p.has_duration:
            programs_with_duration.append(p.name)
            if p.duration_options_json:
                try:
                    duration_options[p.name] = json.loads(p.duration_options_json)
                except Exception:
                    pass
                    
    from app.utils.foreign_universities import FOREIGN_UNIVERSITIES
    return jsonify({
        "countries": sorted(list(countries)),
        "education_levels": education_levels,
        "universities": universities,
        "foreign_universities": FOREIGN_UNIVERSITIES,
        "neb_general_faculties": neb_general,
        "neb_technical_streams": neb_technical if neb_technical else [
            "Computer Engineering", "Civil Engineering", "Electrical/Electronics Engineering",
            "Agriculture and Animal Science", "Forestry", "Nursing (PCL Nursing)", "Pharmacy",
            "Medical Lab Technology (CMLT)", "Hotel Management & Culinary Arts"
        ],
        "bachelors_programs": bachelors_programs if bachelors_programs else [
            "BBA", "BCA", "BE Computer", "BE Civil", "BIT", "BSc IT", "BSc CSIT", "BSc Nursing", "BTech", "MBBS"
        ],
        "masters_programs": masters_programs if masters_programs else [
            "MBA", "MCA", "MIT", "MSc Computer Science"
        ],
        "programs_with_duration": programs_with_duration if programs_with_duration else ["BSc IT"],
        "duration_options": duration_options if duration_options else {
            "BSc IT": [
                { "value": "3 Years", "label": "3 Years (International-affiliated, e.g. APU/LBEF)" },
                { "value": "4 Years", "label": "4 Years (TU-affiliated BSc CSIT)" }
            ]
        }
    })



def sync_student_subjects_from_program(profile, user_id):
    """
    Synchronizes StudentSubject rows for a user based on their selected CurriculumProgram and semester.
    
    1. Locates CurriculumProgram matching profile.program.
    2. Retrieves ProgramSubject mappings for that program and profile.semester (or all active if semester not set).
    3. Populates StudentSubject with mapped subjects while preventing duplicate entries.
    4. Handles missing or empty program/semester mappings gracefully.
    """
    if not profile or not user_id:
        return 0, "No profile or user_id provided"
    
    program_name = (getattr(profile, "program", None) or "").strip()
    semester_name = (getattr(profile, "semester", None) or "").strip()
    
    if not program_name:
        return 0, "No program selected in profile"
    
    from app.models import CurriculumProgram, ProgramSubject, StudentSubject, Subject
    
    prog = CurriculumProgram.query.filter_by(name=program_name, is_active=True).first()
    if not prog:
        prog = CurriculumProgram.query.filter(CurriculumProgram.name.ilike(program_name), CurriculumProgram.is_active == True).first()
    
    if not prog:
        return 0, f"No active curriculum program found matching '{program_name}'"
    
    query = ProgramSubject.query.filter_by(program_id=prog.id, is_active=True)
    if semester_name:
        ps_mappings = query.filter(db.or_(ProgramSubject.semester == semester_name, ProgramSubject.semester.ilike(semester_name))).all()
    else:
        ps_mappings = query.all()
    
    if not ps_mappings and semester_name:
        all_ps = ProgramSubject.query.filter_by(program_id=prog.id, is_active=True).all()
        ps_mappings = [m for m in all_ps if m.semester and (semester_name.lower() in m.semester.lower() or m.semester.lower() in semester_name.lower())]
        if not ps_mappings:
            ps_mappings = all_ps
    
    if not ps_mappings:
        return 0, f"No curriculum subjects are currently mapped to '{program_name}' ({semester_name})."
    
    existing_subjs = StudentSubject.query.filter_by(user_id=user_id).all()
    existing_ids = {s.subject_id for s in existing_subjs}
    
    added_count = 0
    for m in ps_mappings:
        if m.subject_id and m.subject_id not in existing_ids:
            sub_rec = Subject.query.get(m.subject_id)
            if sub_rec and getattr(sub_rec, 'is_active', True):
                new_st_sub = StudentSubject(user_id=user_id, subject_id=m.subject_id)
                db.session.add(new_st_sub)
                existing_ids.add(m.subject_id)
                added_count += 1
    
    if added_count > 0:
        db.session.commit()
    
    return added_count, f"Successfully synchronized {added_count} subjects for {program_name} ({semester_name})."


@student_bp.route("/api/sync-subjects", methods=["POST"])
@login_required
def sync_subjects_api():
    ctx = get_learning_context(current_user.id)
    profile = ctx.profile or StudentProfile.query.filter_by(user_id=current_user.id).first()
    if not profile or not profile.program:
        return jsonify({"success": False, "message": "No program selected in student profile. Please complete profile onboarding."}), 400
    
    count, msg = sync_student_subjects_from_program(profile, current_user.id)
    return jsonify({"success": True, "added_count": count, "message": msg}), 200


@student_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    import uuid
    from werkzeug.utils import secure_filename

    # ── Context: shared learning state for this request
    ctx = get_learning_context(current_user.id)

    # Auto-create profile if not present
    if not ctx.profile:
        new_profile = StudentProfile(
            user_id=current_user.id,
            student_number=f"STU-{uuid.uuid4().hex[:8].upper()}",
            cumulative_gpa=0.0,
        )
        db.session.add(new_profile)
        db.session.commit()
        ctx._profile = None  # reset cache so next access picks up new record

    # Determine if we are in Edit Mode
    edit_mode = (request.args.get("edit") == "1")

    if request.method == "POST":
        action = request.form.get("action", "save")
        if action == "cancel":
            return redirect(url_for("student.profile"))

        current_user.full_name = request.form.get("full_name")

        # Collect profile field updates
        raw_country   = (request.form.get("country") or "Nepal").strip()
        raw_study_lvl = (request.form.get("study_level") or "").strip()
        raw_timezone  = (request.form.get("timezone") or default_timezone_for_country(raw_country)).strip()
        allowed_timezones = set(MULTI_TIMEZONE_OPTIONS.get(raw_country, []))
        if allowed_timezones:
            raw_timezone = raw_timezone if raw_timezone in allowed_timezones else default_timezone_for_country(raw_country)
        else:
            raw_timezone = default_timezone_for_country(raw_country)
        
        derived_curriculum = COUNTRY_CURRICULUM_MAP.get(raw_country, "National")

        raw_university_type = ""
        raw_university_country = ""
        raw_university = ""
        raw_program = ""
        raw_program_duration = ""
        raw_semester = ""

        if raw_study_lvl in ("Class 11", "Class 12", "Bachelors", "Masters"):
            raw_program = (request.form.get("program") or "").strip()

        if raw_study_lvl in ("Bachelors", "Masters"):
            raw_semester = (request.form.get("semester") or "").strip()
            raw_university_type = (request.form.get("university_type") or "").strip()
            
            if raw_university_type == "Foreign":
                raw_university_country = (request.form.get("university_country") or "").strip()
                raw_university = (request.form.get("foreign_university") or "").strip()
            else: # National
                raw_university_type = "National"
                raw_university_country = ""
                sel_univ = request.form.get("university_select", "").strip()
                if sel_univ in ("Foreign-Affiliated", "Other"):
                    custom_univ = request.form.get("university_custom", "").strip()
                    if custom_univ:
                        raw_university = f"{sel_univ}: {custom_univ}"
                    else:
                        raw_university = sel_univ
                else:
                    raw_university = sel_univ
            
            from app.models import CurriculumProgram
            prog_rec = CurriculumProgram.query.filter_by(name=raw_program, is_active=True).first()
            has_duration = prog_rec.has_duration if prog_rec else (raw_program in {"BSc IT"})
            raw_program_duration = request.form.get("program_duration", "").strip() if has_duration else ""

        try:
            raw_att = float(request.form.get("attendance_pct") or 85.0)
            if not (0.0 <= raw_att <= 100.0):
                flash("Validation failed: Attendance % must be between 0 and 100.", "danger")
                return redirect(url_for("student.profile", edit="1"))
        except (TypeError, ValueError):
            raw_att = 85.0

        try:
            raw_gpa_val = float(request.form.get("cumulative_gpa") or 0.0)
            if not (0.0 <= raw_gpa_val <= 4.0):
                flash("Validation failed: Cumulative GPA must be between 0.00 and 4.00.", "danger")
                return redirect(url_for("student.profile", edit="1"))
        except (TypeError, ValueError):
            raw_gpa_val = 0.0

        try:
            raw_commute = int(request.form.get("commute_buffer_minutes") or 0)
            if not (0 <= raw_commute <= 180):
                flash("Validation failed: Commute buffer must be between 0 and 180 minutes.", "danger")
                return redirect(url_for("student.profile", edit="1"))
        except (TypeError, ValueError):
            raw_commute = 0

        profile_data = {
            "country":           raw_country,
            "timezone":          raw_timezone,
            "curriculum":        derived_curriculum,
            "level_of_study":    raw_study_lvl,
            "study_level":       raw_study_lvl,
            "program":           raw_program,
            "program_duration":  raw_program_duration,
            "semester":          raw_semester,
            "university":        raw_university,
            "university_type":   raw_university_type,
            "university_country": raw_university_country,
            "cumulative_gpa":    raw_gpa_val,
            "commute_buffer_minutes": raw_commute,
            "attendance_pct":    raw_att,
            "explanation_level": request.form.get("explanation_level", "Intermediate"),
            "study_goal":        request.form.get("study_goal", "Improve Grades"),
            "preferred_language":request.form.get("preferred_language", "English"),
            "peak_focus_time":   request.form.get("peak_focus_time") or "Morning",
        }

        # Handle profile picture
        if 'profile_pic' in request.files:
            file = request.files['profile_pic']
            if file and file.filename != '':
                filename = secure_filename(file.filename)
                ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
                if ext in ['jpg', 'jpeg', 'png']:
                    file.seek(0, os.SEEK_END)
                    file_length = file.tell()
                    file.seek(0)
                    if file_length <= 2 * 1024 * 1024:
                        upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'profile_pics')
                        os.makedirs(upload_dir, exist_ok=True)
                        unique_fn = f"user_{current_user.id}.{ext}"
                        file.save(os.path.join(upload_dir, unique_fn))
                        profile_data["profile_pic"] = f"uploads/profile_pics/{unique_fn}"
                    else:
                        flash("Profile picture exceeds 2MB limit.", "danger")

        try:
            ctx.update_profile(profile_data)
            db.session.commit()
            
            # Auto-synchronize StudentSubject records based on updated program/semester
            added_cnt, sync_msg = sync_student_subjects_from_program(ctx.profile, current_user.id)
            if added_cnt > 0:
                flash(f"Profile updated and {added_cnt} curriculum subjects synchronized!", "success")
            else:
                flash(f"Profile updated successfully! ({sync_msg})", "info")
        except Exception as e:
            db.session.rollback()
            logger.exception("Error saving student profile: %s", e)
            flash(f"An unexpected error occurred while saving profile: {str(e)}", "danger")
            
        return redirect(url_for("student.profile"))

    # GET — read all data from the shared analytics service (avoids duplicate queries)
    from app.services.analytics_service import StudentAnalyticsService
    analytics = StudentAnalyticsService(current_user.id)

    mastery = analytics.subject_mastery()
    summary = analytics.assessment_summary(limit=None)
    weak_topics = analytics.weak_topics(limit=3)
    academic = analytics.academic_summary()

    from app.models import University
    active_unis = University.query.filter_by(is_active=True).order_by(University.sort_order).all()
    return render_template(
        "student/profile.html",
        edit_mode=edit_mode,
        profile=ctx.profile,
        user=current_user,
        logged_hours=ctx.study_hours,
        streak=ctx.streak,
        risk_summary=ctx.risk_summary,
        completed_quizzes_count=ctx.completed_quizzes_count,
        completed_lessons_count=ctx.completed_lessons_count,
        
        # Analytics details
        subject_mastery=mastery,
        weak_topics=weak_topics,
        recent_assessments=summary["recent"],
        overall_stats={
            "total_attempted": summary["total_attempted"],
            "correct": summary["total_correct"],
            "incorrect": summary["total_incorrect"],
            "accuracy": summary["accuracy"]
        },
        strongest_subject=academic["strongest_subject"],
        weakest_subject=academic["weakest_subject"],
        improvement_trend=academic["improvement_trend"],
        overall_mastery=academic["overall_mastery"],
        subjects=ctx.subjects,
        active_universities=active_unis,
    )


@student_bp.route("/api/tutor-settings", methods=["POST"])
@login_required
def update_tutor_settings():
    # ── Context mutation: update_learning_preferences commits + invalidates profile cache
    # so next AI assistant request picks up the fresh preferences automatically
    ctx = get_learning_context(current_user.id)
    if not ctx.profile:
        return jsonify({"status": "error", "message": "Profile not found"}), 404

    data = request.json or {}
    ctx.update_learning_preferences(data)
    return jsonify({"status": "success", "message": "Tutor settings updated successfully!"})


# ─── AI ASSISTANT ────────────────────────────────────────────────────────────

@student_bp.route("/assistant", methods=["GET"])
@login_required
def assistant():
    """Render the AI chat assistant page."""
    # ── Context: read profile and history from shared state
    ctx = get_learning_context(current_user.id)

    # Get all active subjects for the subject context selector
    if ctx.profile and ctx.profile.study_level:
        from app.utils.subject_map import SUBJECT_MAP
        level_key = ctx.profile.study_level
        allowed_names = set(SUBJECT_MAP.get(level_key, []))
        subjects = Subject.query.filter(Subject.name.in_(allowed_names)).all() if allowed_names else Subject.query.all()
    else:
        subjects = Subject.query.all()

    # Load existing conversation history from context (session-backed)
    history = ctx.ai_conversation_history

    return render_template(
        "student/assistant.html",
        profile=ctx.profile,
        subjects=subjects,
        history=history,
    )


@student_bp.route("/api/chat", methods=["POST"])
@login_required
def api_chat():
    """
    JSON endpoint for the AI chat assistant.
    Reads/writes conversation history through StudentLearningContext.
    Passes enriched context (weak subjects, topics, streak) to the AI.
    """
    data = request.get_json(silent=True) or {}
    query = (data.get("query") or "").strip()
    subject_id = data.get("subject_id")
    if subject_id:
        try:
            subject_id = int(subject_id)
        except (ValueError, TypeError):
            subject_id = None

    if not query:
        return jsonify({"status": "error", "message": "Empty query"}), 400

    # ── Context: read history + enriched profile from shared state
    ctx = get_learning_context(current_user.id)

    # Retrieve history from context (session-backed), keep last 20 messages
    history = ctx.ai_conversation_history[-20:]

    # Build an enriched profile-like object for the AI service.
    # We pass ctx.profile as the profile argument; the enriched system
    # context string is built inside ctx.build_ai_system_context() and
    # injected by calling ai_service with a patched profile wrapper.
    profile = ctx.profile

    try:
        reply = ai_service.chat_with_history(
            history=history,
            user_query=query,
            subject_id=subject_id,
            profile=profile,
        )
    except Exception as e:
        logger.error(f"AI chat error: {e}")
        return jsonify({"status": "error", "message": "The AI tutor is temporarily unavailable. Please try again."}), 503

    # Append new turn to history
    history.append({"role": "user", "content": query})
    history.append({"role": "assistant", "content": reply})

    # ── Context mutation: write history back through context (keeps session in sync)
    ctx.update_ai_history(history)

    is_fallback = any(t in reply for t in ["Local Sync Mode Active", "Temporarily at Capacity"])
    status_str = "degraded" if is_fallback else "success"

    return jsonify({"status": status_str, "response": reply})



@student_bp.route("/api/chat/clear", methods=["POST"])
@login_required
def clear_chat_history():
    """Clear the AI conversation history through context."""
    ctx = get_learning_context(current_user.id)
    ctx.clear_ai_history()
    return jsonify({"status": "success", "message": "Conversation cleared."})


# ─── FUTURE LEARNING ─────────────────────────────────────────────────────────

@student_bp.route("/future-learning", methods=["GET"])
@student_bp.route("/future_learning", methods=["GET"])
@login_required
def future_learning():

    """Future Learning page: progression planner, recommended books, career pathways."""
    from app.models import StudentProfile
    from app.utils.subject_map import SUBJECT_MAP
    from app.utils.book_list import (
        BOOK_LIST, CAREER_PATHWAYS, NEXT_LEVEL_MAP, PROGRESSION_PLAN
    )

    profile = StudentProfile.query.filter_by(user_id=current_user.id).first()
    
    # Normalize custom study level to canonical key in SUBJECT_MAP / BOOK_LIST
    raw_lvl = (getattr(profile, "study_level", None) or "University Year 1").strip()
    prog = (getattr(profile, "program", None) or "").strip().lower()
    sem = (getattr(profile, "semester", None) or "").strip()

    if raw_lvl == "Class 8":
        current_lvl = "Class 8"
    elif raw_lvl == "Class 9":
        current_lvl = "Class 9"
    elif raw_lvl in ("Class 10", "Class 10 (SEE)"):
        current_lvl = "Class 10 (SEE)"
    elif raw_lvl == "Class 11":
        if "science" in prog:
            current_lvl = "Class 11 - Science Stream"
        elif "management" in prog or "commerce" in prog:
            current_lvl = "Class 11 - Management Stream"
        else:
            current_lvl = "Class 11 - Humanities Stream"
    elif raw_lvl == "Class 12":
        if "science" in prog:
            current_lvl = "Class 12 - Science Stream"
        elif "management" in prog or "commerce" in prog:
            current_lvl = "Class 12 - Management Stream"
        else:
            current_lvl = "Class 12 - Humanities Stream"
    elif raw_lvl == "Bachelors":
        if "Year 4" in sem or "Semester 7" in sem or "Semester 8" in sem:
            current_lvl = "University Year 4"
        elif "Year 3" in sem or "Semester 5" in sem or "Semester 6" in sem:
            current_lvl = "University Year 3"
        elif "Year 2" in sem or "Semester 3" in sem or "Semester 4" in sem:
            current_lvl = "University Year 2"
        else:
            current_lvl = "University Year 1"
    elif raw_lvl == "Masters":
        current_lvl = "Master's Level"
    else:
        current_lvl = raw_lvl

    # ── Next level ────────────────────────────────────────────────────────────
    next_lvl = NEXT_LEVEL_MAP.get(current_lvl)
    next_lvl_subjects = SUBJECT_MAP.get(next_lvl, []) if next_lvl else []

    # ── 4-Week progression plan ───────────────────────────────────────────────
    plan = PROGRESSION_PLAN.get(current_lvl, PROGRESSION_PLAN["default"])

    # ── Recommended books (current + next level combined) ─────────────────────
    # Build subject→books dict for all relevant subjects
    all_subjects = list(SUBJECT_MAP.get(current_lvl, [])) + list(next_lvl_subjects)
    # Deduplicate while preserving order
    seen = set()
    unique_subjects = [s for s in all_subjects if not (s in seen or seen.add(s))]

    books_by_subject = {}
    for subj in unique_subjects:
        b = BOOK_LIST.get(subj, [])
        if b:
            books_by_subject[subj] = b

    # ── Career pathways ───────────────────────────────────────────────────────
    # Try exact match first, then partial match on level prefix
    careers = CAREER_PATHWAYS.get(current_lvl, [])
    if not careers:
        for key in CAREER_PATHWAYS:
            if key.lower() in current_lvl.lower() or current_lvl.lower() in key.lower():
                careers = CAREER_PATHWAYS[key]
                break

    return render_template(
        "student/future_learning.html",
        profile=profile,
        current_lvl=current_lvl,
        next_lvl=next_lvl,
        next_lvl_subjects=next_lvl_subjects,
        plan=plan,
        books_by_subject=books_by_subject,
        careers=careers,
    )


def parse_json_safely(response_text):
    """
    Delegates to ai_service._parse_json — single, hardened JSON parsing
    implementation used across the entire application.
    """
    from app.services.ai_service import ai_service
    return ai_service._parse_json(response_text, context="mcq_generation")




def extract_text_from_file(file_path, file_type):
    extracted_text = ""
    if file_type == "pdf":
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(file_path)
            for page in doc:
                extracted_text += page.get_text()
            doc.close()
        except Exception:
            pass
            
        if not extracted_text.strip():
            try:
                import pdfplumber
                with pdfplumber.open(file_path) as pdf:
                    for page in pdf.pages:
                        text = page.extract_text()
                        if text:
                            extracted_text += text
            except Exception:
                pass
    elif file_type in ["png", "jpg", "jpeg"]:
        try:
            from PIL import Image
            import pytesseract
            img = Image.open(file_path)
            extracted_text = pytesseract.image_to_string(img)
        except Exception:
            pass
    elif file_type in ["txt"]:
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                extracted_text = f.read()
        except Exception:
            pass
            
    return extracted_text.strip()


@student_bp.route("/study-material", methods=["GET"])
@student_bp.route("/study_material", methods=["GET"])
@login_required
def study_material():

    from app.models import UploadedMaterial, Subject, LearningMaterial, Topic, Chapter
    profile = StudentProfile.query.filter_by(user_id=current_user.id).first()
    if not profile or not profile.study_level:
        flash("Please complete your profile configuration first (set your Class Level).", "warning")
        return redirect(url_for("student.profile"))

    active_subjects = get_profile_subjects(profile)
    if not active_subjects:
        flash("No subjects found. Please complete your profile to auto-assign your subjects.", "warning")
        return redirect(url_for("student.profile"))

    # Filters and sorting params
    q = request.args.get("q", "").strip()
    subject_id = request.args.get("subject_id", type=int)
    source = request.args.get("source", "all")
    sort_by = request.args.get("sort_by", "newest")

    active_subject_ids = [s.id for s in active_subjects]
    
    unified_list = []

    # 1. Fetch AI Generated LearningMaterials
    if source in ["all", "ai"]:
        lm_query = (
            db.session.query(LearningMaterial, Topic, Chapter, Subject)
            .join(Topic, LearningMaterial.topic_id == Topic.id)
            .join(Chapter, Topic.chapter_id == Chapter.id)
            .join(Subject, Chapter.subject_id == Subject.id)
        )
        if subject_id:
            lm_query = lm_query.filter(Subject.id == subject_id)
        else:
            lm_query = lm_query.filter(Subject.id.in_(active_subject_ids))

        if q:
            lm_query = lm_query.filter(
                db.or_(
                    LearningMaterial.title.ilike(f"%{q}%"),
                    Topic.name.ilike(f"%{q}%"),
                    Chapter.name.ilike(f"%{q}%")
                )
            )
        
        lm_results = lm_query.all()
        for lm, topic, chapter, subject in lm_results:
            unified_list.append({
                "type": "ai",
                "id": lm.id,
                "title": lm.title,
                "subject_name": subject.name,
                "chapter_name": chapter.name,
                "topic_name": topic.name,
                "topic_id": topic.id,
                "date": datetime.utcnow(),
                "details_url": url_for("student.study_subject", subject_id=subject.id) + f"?topic_id={topic.id}",
                "badge_class": "bg-primary bg-opacity-20 text-primary",
                "badge_text": "AI Notes"
            })

    # 2. Fetch User Uploaded Materials
    if source in ["all", "uploaded"]:
        um_query = (
            db.session.query(UploadedMaterial, Subject)
            .join(Subject, UploadedMaterial.subject_id == Subject.id)
            .filter(UploadedMaterial.user_id == current_user.id)
        )
        if subject_id:
            um_query = um_query.filter(UploadedMaterial.subject_id == subject_id)
        else:
            um_query = um_query.filter(UploadedMaterial.subject_id.in_(active_subject_ids))

        if q:
            um_query = um_query.filter(
                db.or_(
                    UploadedMaterial.filename.ilike(f"%{q}%"),
                    UploadedMaterial.extracted_text.ilike(f"%{q}%"),
                    UploadedMaterial.summary.ilike(f"%{q}%")
                )
            )

        um_results = um_query.all()
        for um, subject in um_results:
            unified_list.append({
                "type": "uploaded",
                "id": um.id,
                "title": um.filename,
                "subject_name": subject.name,
                "chapter_name": um.chapter.name if um.chapter else "N/A",
                "topic_name": um.topic.name if um.topic else "N/A",
                "topic_id": um.topic_id,
                "date": um.uploaded_at or datetime.utcnow(),
                "details_url": url_for("student.uploaded_material_detail", material_id=um.id),
                "badge_class": "bg-success bg-opacity-20 text-success",
                "badge_text": "Uploaded Document"
            })

    # Sort unified list
    is_reverse = (sort_by == "newest")
    unified_list.sort(key=lambda x: x["date"], reverse=is_reverse)

    # Build verbatim subfolder directory tree dictionary for Explorer
    from app.models import UploadedMaterial
    raw_uploaded = UploadedMaterial.query.filter_by(user_id=current_user.id).all()
    folder_tree = {}
    for um in raw_uploaded:
        rel_folder = um.relative_folder_path if um.relative_folder_path else "Root Directory"
        if rel_folder not in folder_tree:
            folder_tree[rel_folder] = []
        ext = (um.file_type or "").lower().lstrip('.')
        folder_tree[rel_folder].append({
            "id": um.id,
            "filename": um.filename,
            "relative_folder_path": rel_folder,
            "file_type": ext,
            "subject_name": um.subject.name if um.subject else "Unassigned",
            "file_size": um.file_size_bytes or 0,
            "uploaded_at": um.uploaded_at or datetime.utcnow(),
            "details_url": url_for("student.uploaded_material_detail", material_id=um.id),
            "download_url": url_for("student.download_raw_material", material_id=um.id)
        })

    from app.models import MaterialImportBatch, SubjectBook
    import_batches = MaterialImportBatch.query.filter_by(user_id=current_user.id).order_by(MaterialImportBatch.created_at.desc()).all()
    physical_books = SubjectBook.query.filter_by(user_id=current_user.id).all()

    # Determine Tier Mode (1: Files Uploaded, 2: Physical Books Configured, 3: Standard Curriculum)
    tier_mode = 3
    if raw_uploaded and len(raw_uploaded) > 0:
        tier_mode = 1
    elif physical_books and len(physical_books) > 0:
        tier_mode = 2

    # Standard Curriculum Fallback Tree for Tier 3
    curriculum_tree = []
    for subj in active_subjects:
        ch_list = Chapter.query.filter_by(subject_id=subj.id).order_by(Chapter.chapter_number).all()
        ch_data = []
        for ch in ch_list:
            top_list = Topic.query.filter_by(chapter_id=ch.id).order_by(Topic.topic_number).all()
            ch_data.append({
                "chapter": ch,
                "topics": top_list
            })
        curriculum_tree.append({
            "subject": subj,
            "chapters": ch_data
        })

    return render_template(
        "student/study_material.html",
        profile=profile,
        active_subjects=active_subjects,
        selected_subject_id=subject_id,
        selected_source=source,
        selected_sort=sort_by,
        search_query=q,
        materials=unified_list,
        import_batches=import_batches,
        folder_tree=folder_tree,
        physical_books=physical_books,
        tier_mode=tier_mode,
        curriculum_tree=curriculum_tree
    )


@student_bp.route("/study-materials/delete-batch/<int:batch_id>", methods=["POST", "DELETE"])
@login_required
def delete_import_batch(batch_id):
    from app.models import MaterialImportBatch, MaterialImportUnmatched, UploadedMaterial, MaterialChunk
    batch = MaterialImportBatch.query.get_or_404(batch_id)
    if batch.user_id != current_user.id:
        return jsonify({"status": "error", "message": "Unauthorized access."}), 403

    # 1. Purge physical files on disk & linked MaterialChunk vectors
    materials = UploadedMaterial.query.filter_by(import_batch_id=batch.id).all()
    for mat in materials:
        MaterialChunk.query.filter_by(material_id=mat.id).delete()
        if mat.file_path and os.path.exists(mat.file_path):
            try:
                os.remove(mat.file_path)
            except OSError:
                pass

    batch_dir = f"uploads/user_{current_user.id}/batch_{batch.id}"
    materials_dir = f"materials/user_{current_user.id}/batch_{batch.id}"

    for folder in [batch_dir, materials_dir]:
        if os.path.exists(folder):
            shutil.rmtree(folder, ignore_errors=True)

    # 2. Delete database rows
    UploadedMaterial.query.filter_by(import_batch_id=batch.id).delete()
    MaterialImportUnmatched.query.filter_by(batch_id=batch.id).delete()
    db.session.delete(batch)
    db.session.commit()

    return jsonify({"status": "success", "message": "Batch and all containing folders permanently deleted."}), 200


@student_bp.route("/study-materials/delete-material/<int:material_id>", methods=["DELETE", "POST"])
@login_required
def delete_uploaded_material(material_id):
    from app.models import UploadedMaterial, MaterialChunk
    mat = UploadedMaterial.query.get_or_404(material_id)
    if mat.user_id != current_user.id:
        return jsonify({"status": "error", "message": "Unauthorized access."}), 403

    MaterialChunk.query.filter_by(material_id=mat.id).delete()

    if mat.file_path and os.path.exists(mat.file_path):
        try:
            os.remove(mat.file_path)
        except OSError:
            pass
    db.session.delete(mat)
    db.session.commit()
    return jsonify({"status": "success", "message": "Material permanently deleted."}), 200


@student_bp.route("/study-materials/delete-subject/<int:subject_id>", methods=["DELETE", "POST"])
@login_required
def delete_student_subject(subject_id):
    from app.models import StudentSubject, UploadedMaterial
    StudentSubject.query.filter_by(user_id=current_user.id, subject_id=subject_id).delete()

    materials = UploadedMaterial.query.filter_by(user_id=current_user.id, subject_id=subject_id).all()
    for mat in materials:
        if mat.file_path and os.path.exists(mat.file_path):
            try:
                os.remove(mat.file_path)
            except OSError:
                pass
        db.session.delete(mat)

    subject_dir = f"uploads/user_{current_user.id}/subject_{subject_id}"
    if os.path.exists(subject_dir):
        shutil.rmtree(subject_dir, ignore_errors=True)

    db.session.commit()
    return jsonify({"status": "success", "message": "Subject folder and materials deleted."}), 200


@student_bp.route("/study/api/subject/<int:subject_id>/chapters", methods=["GET"])
@login_required
def get_subject_chapters(subject_id):
    from app.models import Chapter
    chapters = Chapter.query.filter_by(subject_id=subject_id).order_by(Chapter.chapter_number).all()
    chapters_list = [{"id": c.id, "name": f"Chapter {c.chapter_number}: {c.name}"} for c in chapters]
    return jsonify({"status": "success", "chapters": chapters_list})


@student_bp.route("/study-material/upload", methods=["POST"])
@login_required
def upload_study_material():
    subject_id = request.form.get("subject_id", type=int)
    chapter_id = request.form.get("chapter_id", type=int)
    topic_id = request.form.get("topic_id", type=int)
    
    if not subject_id:
        return jsonify({"status": "error", "message": "Subject is required."}), 400
        
    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "No file uploaded."}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({"status": "error", "message": "No selected file."}), 400
        
    filename = secure_filename(file.filename)
    file_ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    
    if file_ext not in ['pdf', 'txt', 'png', 'jpg', 'jpeg']:
        return jsonify({"status": "error", "message": "Unsupported file format. Please upload PDF, TXT, or Image."}), 400
        
    upload_dir = os.path.join(current_app.root_path, "static", "uploads", f"user_{current_user.id}")
    os.makedirs(upload_dir, exist_ok=True)
    
    file_path = os.path.join(upload_dir, filename)
    file.save(file_path)
    
    db_file_path = f"uploads/user_{current_user.id}/{filename}"
    extracted_text = extract_text_from_file(file_path, file_ext)
    
    if not extracted_text:
        return jsonify({"status": "error", "message": "Could not extract text from the document. Please ensure it contains readable text."}), 400
        
    prompt = (
        f"Analyze the following document text extracted from '{filename}'.\n"
        f"Generate a detailed, premium academic summary and key revision notes (bullet points) in HTML format.\n\n"
        f"Document Text:\n{extracted_text[:12000]}\n\n"
        "Return the output in valid JSON format. The format MUST be:\n"
        "{\n"
        '  "summary": "Detailed HTML summary here...",\n'
        '  "revision_notes": "<ul><li>Revision note 1</li><li>Revision note 2</li></ul>"\n'
        "}"
    )
    
    system_instruction = (
        "You are an expert academic research assistant. "
        "You must analyze the document and output a valid JSON containing 'summary' and 'revision_notes'. "
        "Do not include any preamble, explanations, or markdown outside the JSON."
    )
    
    try:
        response_text = ai_service.generate_content(
            prompt,
            feature=FEATURE_ASSISTANT,
            system_instruction=system_instruction
        )
        data = ai_service._parse_json(response_text)
    except Exception as e:
        data = {
            "summary": "<p>A summary could not be generated at this time.</p>",
            "revision_notes": "<p>Revision notes could not be generated at this time.</p>"
        }
        
    from app.models import UploadedMaterial
    material = UploadedMaterial(
        user_id=current_user.id,
        subject_id=subject_id,
        chapter_id=chapter_id if chapter_id else None,
        topic_id=topic_id if topic_id else None,
        filename=filename,
        file_path=db_file_path,
        file_type=file_ext,
        extracted_text=extracted_text,
        summary=data.get("summary"),
        revision_notes=data.get("revision_notes")
    )
    db.session.add(material)
    
    profile = StudentProfile.query.filter_by(user_id=current_user.id).first()
    if profile:
        profile.documents_uploaded = (profile.documents_uploaded or 0) + 1
        
    db.session.commit()
    
    return jsonify({
        "status": "success",
        "message": "Document uploaded and parsed successfully!",
        "material_id": material.id
    })


@student_bp.route("/study-material/uploaded/<int:material_id>", methods=["GET"])
@login_required
def uploaded_material_detail(material_id):
    from app.models import UploadedMaterial, Subject
    material = UploadedMaterial.query.get_or_404(material_id)
    
    if material.user_id != current_user.id:
        flash("You are not authorized to access this document.", "danger")
        return redirect(url_for("student.study_material"))
        
    subject = Subject.query.get(material.subject_id)
    material.last_opened = datetime.utcnow()
    db.session.commit()
    
    file_ext = (os.path.splitext(material.filename)[1] or material.file_type or "").lower().lstrip('.')

    docx_html = None
    if file_ext == 'docx' and material.file_path and os.path.exists(material.file_path):
        try:
            import mammoth
            with open(material.file_path, "rb") as docx_file:
                res_html = mammoth.convert_to_html(docx_file)
                docx_html = res_html.value
        except Exception as e:
            logger.error(f"[Mammoth Conversion Error]: {e}")
            docx_html = None

    return render_template(
        "student/uploaded_material_detail.html",
        material=material,
        subject=subject,
        docx_html=docx_html,
        file_ext=file_ext
    )


@student_bp.route("/study-material/<int:material_id>/generate-summary", methods=["POST"])
@login_required
def generate_material_summary_ajax(material_id):
    from app.models import UploadedMaterial
    from app.services.ai_service import AIService
    material = UploadedMaterial.query.get_or_404(material_id)
    if material.user_id != current_user.id:
        return jsonify({"status": "error", "message": "Unauthorized"}), 403

    text_to_summarize = material.extracted_text or ""
    if len(text_to_summarize.strip()) == 0:
        return jsonify({
            "status": "error",
            "message": "No text content available in this document to summarize."
        }), 400

    try:
        ai = AIService()
        prompt = (
            f"Generate a comprehensive executive summary and key bullet notes for the following study material:\n\n"
            f"Document Title: {material.filename}\n"
            f"Content:\n{text_to_summarize[:4000]}\n\n"
            f"Provide a structured response with:\n"
            f"1. Executive Summary (2-3 paragraphs)\n"
            f"2. Key Takeaways & Core Concepts (5-8 bullet points)\n"
        )
        summary_text = ai.call_gemini_reusable(
            prompt,
            feature="assistant",
            context=f"summary_gen_mat_{material.id}"
        )
        if summary_text:
            material.summary = summary_text.strip()
            db.session.commit()
            return jsonify({
                "status": "success",
                "summary": material.summary
            })
        else:
            return jsonify({"status": "error", "message": "AI returned empty summary."}), 500
    except Exception as e:
        logger.error(f"[Summary Gen Error]: {e}", exc_info=True)
        fallback_summary = (
            f"### Executive Summary (Offline Fallback)\n"
            f"This document '{material.filename}' has been processed and indexed into your RAG vector database.\n\n"
            f"### Key Concepts & Takeaways\n"
            f"• Core content extracted and ready for vector search.\n"
            f"• Full text content available under Extracted Text tab.\n"
            f"• Interactive document Q&A chat enabled.\n"
        )
        material.summary = fallback_summary
        db.session.commit()
        return jsonify({
            "status": "success",
            "summary": fallback_summary,
            "notice": "Generated using fallback offline indexing."
        }), 200


@student_bp.route("/physical-book/add", methods=["POST"])
@login_required
def add_physical_book():
    from app.models import SubjectBook
    subject_id = request.form.get("subject_id", type=int)
    title = request.form.get("title", "").strip()
    author = request.form.get("author", "").strip()
    publisher = request.form.get("publisher", "").strip()
    edition = request.form.get("edition", "").strip()
    isbn = request.form.get("isbn", "").strip()
    toc_raw = request.form.get("toc_text", "").strip()

    if not subject_id or not title:
        flash("Subject and Book Title are required.", "danger")
        return redirect(url_for("student.study_material"))

    # Convert TOC lines into structured JSON
    toc_structure = []
    if toc_raw:
        lines = [l.strip() for l in toc_raw.splitlines() if l.strip()]
        current_ch = None
        for line in lines:
            if line.lower().startswith("chapter") or line.lower().startswith("unit") or line.lower().startswith("module") or line[0].isdigit():
                current_ch = {"chapter_title": line, "topics": []}
                toc_structure.append(current_ch)
            else:
                if current_ch is None:
                    current_ch = {"chapter_title": "General Overview", "topics": []}
                    toc_structure.append(current_ch)
                current_ch["topics"].append(line)

    book = SubjectBook(
        user_id=current_user.id,
        subject_id=subject_id,
        title=title,
        author=author,
        publisher=publisher,
        edition=edition,
        isbn=isbn,
        toc_json=json.dumps(toc_structure) if toc_structure else "[]"
    )
    db.session.add(book)
    db.session.commit()
    flash(f"Physical textbook '{title}' registered successfully!", "success")
    return redirect(url_for("student.study_material"))


@student_bp.route("/study-material/download/<int:material_id>", methods=["GET"])
@login_required
def download_raw_material(material_id):
    from flask import send_from_directory
    from app.models import UploadedMaterial
    material = UploadedMaterial.query.get_or_404(material_id)
    if material.user_id != current_user.id:
        flash("You are not authorized to access this document.", "danger")
        return redirect(url_for("student.study_material"))

    if not material.file_path or not os.path.exists(material.file_path):
        flash("Original file not found on server.", "warning")
        return redirect(url_for("student.uploaded_material_detail", material_id=material.id))

    directory = os.path.dirname(os.path.abspath(material.file_path))
    filename = os.path.basename(material.file_path)
    return send_from_directory(directory, filename, as_attachment=True, download_name=material.filename)


@student_bp.route("/study-material/preview-file/<int:material_id>", methods=["GET"])
@login_required
def preview_raw_material(material_id):
    from flask import send_from_directory
    from app.models import UploadedMaterial
    material = UploadedMaterial.query.get_or_404(material_id)
    if material.user_id != current_user.id:
        return "Unauthorized", 403

    if not material.file_path or not os.path.exists(material.file_path):
        return "File not found", 404

    directory = os.path.dirname(os.path.abspath(material.file_path))
    filename = os.path.basename(material.file_path)
    return send_from_directory(directory, filename, as_attachment=False)


@student_bp.route("/study-material/uploaded/<int:material_id>/ai-action", methods=["POST"])
@login_required
def uploaded_material_ai_action(material_id):
    from app.models import UploadedMaterial
    material = UploadedMaterial.query.get_or_404(material_id)
    
    if material.user_id != current_user.id:
        return jsonify({"status": "error", "message": "Unauthorized"}), 403
        
    action = request.json.get("action")
    user_query = request.json.get("query", "").strip()
    
    if not action:
        return jsonify({"status": "error", "message": "Action is required."}), 400
        
    if action == "mcqs":
        if material.mcqs_json:
            return jsonify({"status": "success", "mcqs": json.loads(material.mcqs_json)})
            
        prompt = (
            f"Based on the following document text, generate 5 relevant multiple-choice questions (MCQs) for practice.\n\n"
            f"Document Text:\n{material.extracted_text[:12000]}\n\n"
            "Return the list strictly in valid JSON format matching the schema:\n"
            "[\n"
            "  {\n"
            '    "q": "Question text?",\n'
            '    "a": "Option A",\n'
            '    "b": "Option B",\n'
            '    "c": "Option C",\n'
            '    "d": "Option D",\n'
            '    "ans": "A",\n'
            '    "exp": "Detailed explanation."\n'
            "  },\n"
            "  ...\n"
            "]"
        )
        
        system_instruction = (
            "You are an elite academic examiner. Generate 5 high-quality MCQs based on the text. "
            "Output strictly valid JSON array of objects. Do not include markdown code block formatting."
        )
        
        try:
            response_text = ai_service.generate_content(
                prompt,
                feature=FEATURE_ASSISTANT,
                system_instruction=system_instruction
            )
            mcqs_data = ai_service._parse_json(response_text)
            material.mcqs_json = json.dumps(mcqs_data)
            db.session.commit()
            return jsonify({"status": "success", "mcqs": mcqs_data})
        except Exception as e:
            return jsonify({"status": "error", "message": f"Failed to generate MCQs: {str(e)}"}), 500
            
    elif action == "flashcards":
        if material.flashcards_json:
            return jsonify({"status": "success", "flashcards": json.loads(material.flashcards_json)})
            
        prompt = (
            f"Based on the following document text, generate 5 interactive flashcards for studying.\n\n"
            f"Document Text:\n{material.extracted_text[:12000]}\n\n"
            "Return the list strictly in valid JSON format matching the schema:\n"
            "[\n"
            "  {\n"
            '    "front": "Term / Question",\n'
            '    "back": "Definition / Answer"\n'
            "  },\n"
            "  ...\n"
            "]"
        )
        
        system_instruction = (
            "You are an academic advisor. Generate 5 active recall flashcards. "
            "Output strictly valid JSON array of objects. Do not include markdown code block formatting."
        )
        
        try:
            response_text = ai_service.generate_content(
                prompt,
                feature=FEATURE_ASSISTANT,
                system_instruction=system_instruction
            )
            fc_data = ai_service._parse_json(response_text)
            material.flashcards_json = json.dumps(fc_data)
            db.session.commit()
            return jsonify({"status": "success", "flashcards": fc_data})
        except Exception as e:
            return jsonify({"status": "error", "message": f"Failed to generate flashcards: {str(e)}"}), 500
            
    elif action == "chat":
        if not user_query:
            return jsonify({"status": "error", "message": "Query is required for chat."}), 400
            
        prompt = (
            f"You are tutoring a student based on a document they uploaded. Answer their question using only "
            f"the context provided from the document.\n\n"
            f"Document Title: {material.filename}\n"
            f"Document Context:\n{material.extracted_text[:12000]}\n\n"
            f"Student's Question: {user_query}\n\n"
            "Tutor Answer:"
        )
        
        try:
            response_text = ai_service.generate_content(
                prompt,
                feature=FEATURE_ASSISTANT,
            )
            return jsonify({"status": "success", "response": response_text})
        except Exception as e:
            return jsonify({"status": "error", "message": f"Failed to process chat query: {str(e)}"}), 500
            
    return jsonify({"status": "error", "message": "Invalid action."}), 400


@student_bp.route("/study-material/generate", methods=["POST"])
@login_required
def generate_study_material_route():
    profile = StudentProfile.query.filter_by(user_id=current_user.id).first()
    if not profile or not profile.study_level:
        return jsonify({"status": "error", "message": "Please set your class level in Profile first."}), 400

    subject_id = request.form.get("subject_id", type=int)
    if not subject_id:
        return jsonify({"status": "error", "message": "No subject specified."}), 400

    from app.models import StudentSubject, Subject
    is_active = StudentSubject.query.filter_by(user_id=current_user.id, subject_id=subject_id).first()
    if not is_active:
        return jsonify({"status": "error", "message": "Subject is not active for your profile."}), 403

    subject = Subject.query.get(subject_id)
    if not subject:
        return jsonify({"status": "error", "message": "Subject not found."}), 404

    force_regenerate = request.form.get("regenerate", type=int) == 1

    saved_material = AIStudyMaterial.query.filter_by(
        user_id=current_user.id,
        subject_id=subject.id,
        class_level=profile.study_level
    ).first()

    if saved_material and not force_regenerate:
        try:
            return jsonify({
                "status": "success",
                "message": "Loaded from cache.",
                "data": json.loads(saved_material.content_json)
            })
        except Exception:
            pass

    prompt = (
        f"Generate comprehensive and complete study material for Class Level: '{profile.study_level}' "
        f"and Subject Name: '{subject.name}'.\n"
        f"Curriculum context: {profile.curriculum or 'National Curriculum'}.\n"
        f"Language preference: {profile.preferred_language or 'English'}.\n\n"
        "Ensure you cover the syllabus standard for this level. Write the notes in simple, engaging language suitable "
        "for the student's class level. You must provide all 16 items of study material requested in the JSON schema."
    )

    system_instruction = (
        "You are an elite, expert Academic AI Tutor. Generate complete, high-quality study materials for students.\n"
        "You must output the result strictly in valid JSON format. Do not write any preamble, explanation, or markdown "
        "blocks outside the JSON content.\n\n"
        "JSON SCHEMA:\n"
        "{\n"
        '  "introduction": "Detailed introduction text.",\n'
        '  "learning_objectives": ["Objective 1", "Objective 2", "Objective 3", ...],\n'
        '  "detailed_notes": "Detailed notes with HTML formatting (use <p>, <h4>, <ul>, <li>, <strong>, etc.) explaining all major chapters/topics of this curriculum.",\n'
        '  "important_concepts": "Important concepts list or detailed text.",\n'
        '  "easy_explanation": "Simplified explanation using easy-to-understand real-world analogies.",\n'
        '  "real_life_examples": ["Example 1", "Example 2", ...],\n'
        '  "worked_examples": ["Worked Example 1 (e.g. math/science problem, grammar exercises, or historical case studies with step-by-step resolution)", ...],\n'
        '  "important_formulas": "Formulas listing, symbols, and mathematical relationships (or \"Not applicable for this subject\" if not math/science)",\n'
        '  "common_mistakes": ["Mistake 1: explanation", "Mistake 2: explanation", ...],\n'
        '  "key_points": ["Key Point 1", "Key Point 2", ...],\n'
        '  "chapter_summary": "Brief structured summary of the textbook contents.",\n'
        '  "revision_notes": "Handy notes for last-minute exam prep.",\n'
        '  "practice_questions": [\n'
        '     "1. practice question text", "2. practice question text", "3. ...", "4. ...", "5. ...",\n'
        '     "6. ...", "7. ...", "8. ...", "9. ...", "10. practice question text"\n'
        '  ],\n'
        '  "mcqs": [\n'
        "     {\n"
        '       "question": "1. Question text here?",\n'
        '       "options": ["A) Option A", "B) Option B", "C) Option C", "D) Option D"],\n'
        '       "correct_answer": "A",\n'
        '       "explanation": "Why A is correct."\n'
        "     },\n"
        "     ... (exactly 10 objects)\n"
        "  ],\n"
        '  "short_answer_questions": [\n'
        '     "1. Short question text", "2. ...", "3. ...", "4. ...", "5. Short question text"\n'
        '  ],\n'
        '  "flashcards": [\n'
        '     { "front": "Concept/Term/Question", "back": "Definition/Formula/Answer" },\n'
        "     ... (at least 8-10 cards)\n"
        "  ]\n"
        "}"
    )

    try:
        response_text = ai_service.generate_content(
            prompt,
            system_instruction=system_instruction,
            max_output_tokens=32768,   # study material JSON can be large; default 8192 causes truncation
        )
        material_data = parse_json_safely(response_text)

        if not saved_material:
            saved_material = AIStudyMaterial(
                user_id=current_user.id,
                subject_id=subject.id,
                class_level=profile.study_level,
                content_json=json.dumps(material_data)
            )
            db.session.add(saved_material)
        else:
            saved_material.class_level = profile.study_level
            saved_material.content_json = json.dumps(material_data)
            saved_material.updated_at = datetime.utcnow()

        db.session.commit()

        return jsonify({
            "status": "success",
            "message": "Generated and saved successfully.",
            "data": material_data
        })
    except Exception as e:
        db.session.rollback()
        import traceback
        tb = traceback.format_exc()
        try:
            with open("c:/smart_study/scratch/error_log.txt", "w") as f:
                f.write(f"Exception: {str(e)}\n\nTraceback:\n{tb}")
            if 'response_text' in locals() and response_text:
                with open("c:/smart_study/scratch/raw_response.txt", "w", encoding="utf-8") as f:
                    f.write(response_text)
        except Exception as log_err:
            print(f"Failed to write log file: {log_err}")
        traceback.print_exc()
        return jsonify({"status": "error", "message": f"AI generation failed: {str(e)}"}), 500


# ── NEW STUDY MATERIAL API IMPROVEMENTS ──────────────────────────────────────

@student_bp.route("/study/api/topic/<int:topic_id>/bookmark", methods=["POST"])
@login_required
def toggle_bookmark(topic_id):
    topic = Topic.query.get_or_404(topic_id)
    bookmark = BookmarkedChapter.query.filter_by(
        student_id=current_user.id, topic_id=topic.id
    ).first()
    if bookmark:
        db.session.delete(bookmark)
        db.session.commit()
        return jsonify({"status": "success", "bookmarked": False, "message": "Bookmark removed."})
    else:
        new_bookmark = BookmarkedChapter(student_id=current_user.id, topic_id=topic.id)
        db.session.add(new_bookmark)
        db.session.commit()
        return jsonify({"status": "success", "bookmarked": True, "message": "Chapter bookmarked."})


@student_bp.route("/study/api/topic/<int:topic_id>/bookmark-status", methods=["GET"])
@login_required
def bookmark_status(topic_id):
    topic = Topic.query.get_or_404(topic_id)
    bookmark = BookmarkedChapter.query.filter_by(
        student_id=current_user.id, topic_id=topic.id
    ).first()
    return jsonify({"status": "success", "bookmarked": bookmark is not None})


@student_bp.route("/study/api/topic/<int:topic_id>/mark-read", methods=["POST"])
@login_required
def mark_read(topic_id):
    topic = Topic.query.get_or_404(topic_id)
    status = request.form.get("status", "completed")
    progress = ReviewedChapter.query.filter_by(
        student_id=current_user.id, topic_id=topic.id
    ).first()
    if not progress:
        progress = ReviewedChapter(
            student_id=current_user.id, topic_id=topic.id, status=status
        )
        db.session.add(progress)
    else:
        progress.status = status
        progress.last_accessed_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"status": "success", "progress_status": progress.status})


@student_bp.route("/study/api/topic/<int:topic_id>/progress", methods=["GET"])
@login_required
def get_progress(topic_id):
    topic = Topic.query.get_or_404(topic_id)
    progress = ReviewedChapter.query.filter_by(
        student_id=current_user.id, topic_id=topic.id
    ).first()
    status = progress.status if progress else "not started"
    return jsonify({"status": "success", "progress_status": status})


@student_bp.route("/study/api/topic/<int:topic_id>/notes", methods=["GET", "POST"])
@login_required
def topic_notes(topic_id):
    topic = Topic.query.get_or_404(topic_id)
    if request.method == "POST":
        content = request.form.get("content", "")
        note = ChapterNote.query.filter_by(
            student_id=current_user.id, topic_id=topic.id
        ).first()
        if not note:
            note = ChapterNote(
                student_id=current_user.id, topic_id=topic.id, content=content
            )
            db.session.add(note)
        else:
            note.content = content
            note.updated_at = datetime.utcnow()
        db.session.commit()
        return jsonify({"status": "success", "message": "Notes saved."})
    else:
        note = ChapterNote.query.filter_by(
            student_id=current_user.id, topic_id=topic.id
        ).first()
        content = note.content if note else ""
        return jsonify({"status": "success", "content": content})


@student_bp.route("/study/api/topic/<int:topic_id>/generate-quiz", methods=["GET"])
@login_required
def generate_chapter_quiz(topic_id):
    import random
    topic = Topic.query.get_or_404(topic_id)
    material = LearningMaterial.query.filter_by(topic_id=topic.id).first()
    content_context = material.detailed_explanation if material else topic.name

    # ── GAP 1: Fetch ALL historically seen question texts for this student+topic ──
    seen_records = TopicSeenQuestion.query.filter_by(
        student_id=current_user.id, topic_id=topic_id
    ).order_by(TopicSeenQuestion.seen_at.desc()).all()
    seen_texts = [r.question_text for r in seen_records]

    exclusion_block = ""
    if seen_texts:
        # Cap at 80 to keep prompt size manageable
        exclusion_sample = seen_texts[:80]
        exclusion_block = (
            "\n\nDo not repeat any of these previously asked questions:\n"
            + "\n".join(f"- {q}" for q in exclusion_sample)
        )

    system_instruction = "You are an expert examiner for the National Examination Board (NEB) of Nepal."

    response_schema = {
        "type": "ARRAY",
        "items": {
            "type": "OBJECT",
            "properties": {
                "q":   {"type": "STRING", "description": "Question text"},
                "a":   {"type": "STRING"},
                "b":   {"type": "STRING"},
                "c":   {"type": "STRING"},
                "d":   {"type": "STRING"},
                "ans": {"type": "STRING", "description": "Correct option: A, B, C, or D"},
                "exp": {"type": "STRING", "description": "Explanation of why the answer is correct"}
            },
            "required": ["q", "a", "b", "c", "d", "ans", "exp"]
        }
    }

    def build_prompt(num_questions=5):
        return (
            f"Generate exactly {num_questions} unique, distinct multiple-choice questions "
            f"testing deep understanding of the topic '{topic.name}' "
            f"for a student at '{topic.chapter.subject.level_of_study}' level.\n"
            f"Use the following textbook content as context:\n{content_context[:3000]}\n"
            "Each question must have 4 options (A, B, C, D) and one correct answer with a clear explanation."
            f"{exclusion_block}"
        )

    quiz_data = None
    api_error = None

    # ── Attempt 1: Full prompt with structured output ──────────────────────────
    try:
        response_text = ai_service.generate_content(
            build_prompt(5),
            system_instruction=system_instruction,
            response_mime_type="application/json",
            response_schema=response_schema
        )
        quiz_data = parse_json_safely(response_text)
        if not isinstance(quiz_data, list) or len(quiz_data) < 1:
            raise ValueError("Empty or invalid response from AI")
    except Exception as e:
        api_error = str(e)
        logger.warning(f"[chapter_quiz] Primary AI attempt failed for topic {topic_id}: {e}")

    # ── Attempt 2: Retry with shorter, simpler prompt (no exclusion list) ─────
    if quiz_data is None:
        try:
            simple_prompt = (
                f"Generate exactly 5 multiple-choice questions on the topic '{topic.name}'. "
                "Each must have options A, B, C, D and one correct answer with explanation."
            )
            response_text = ai_service.generate_content(
                simple_prompt,
                system_instruction=system_instruction,
                response_mime_type="application/json",
                response_schema=response_schema
            )
            quiz_data = parse_json_safely(response_text)
            if not isinstance(quiz_data, list) or len(quiz_data) < 1:
                raise ValueError("Empty response on retry")
            logger.info(f"[chapter_quiz] Retry succeeded for topic {topic_id}")
        except Exception as e2:
            api_error = str(e2)
            logger.warning(f"[chapter_quiz] Retry AI attempt also failed for topic {topic_id}: {e2}")

    # ── GAP 2: Rotating fallback pool (4 sets, randomly selected) ─────────────
    if quiz_data is None:
        topic_name = topic.name
        FALLBACK_POOLS = [
            [
                {"q": f"What is the primary objective of studying '{topic_name}'?", "a": "Memorisation only", "b": "Conceptual understanding and application", "c": "Test preparation alone", "d": "None of the above", "ans": "B", "exp": "Education focuses on deep conceptual understanding so students can apply knowledge."},
                {"q": f"Which approach best helps mastery of '{topic_name}'?", "a": "Daily revision with active recall", "b": "Passive reading only", "c": "Skipping difficult sections", "d": "Memorising answers without understanding", "ans": "A", "exp": "Active recall and spaced repetition are proven learning strategies."},
                {"q": f"How does '{topic_name}' relate to other topics in the curriculum?", "a": "It is completely isolated", "b": "It builds foundational skills used across the subject", "c": "It is optional content", "d": "It has no practical relevance", "ans": "B", "exp": "Topics in a curriculum are interconnected; foundational topics support advanced learning."},
                {"q": "Which study technique is most effective for retaining new concepts?", "a": "Cramming one day before exams", "b": "Distributed practice over several days", "c": "Reading once and not revisiting", "d": "Avoiding practice problems", "ans": "B", "exp": "Research shows spaced/distributed practice leads to better long-term retention."},
                {"q": "What role does self-testing play in learning?", "a": "It wastes study time", "b": "It only helps with multiple-choice exams", "c": "It strengthens memory retrieval pathways", "d": "It is less effective than re-reading", "ans": "C", "exp": "Self-testing (retrieval practice) is one of the most effective learning strategies known to science."},
            ],
            [
                {"q": f"Why is conceptual clarity important when learning '{topic_name}'?", "a": "It allows rote memorisation to work faster", "b": "It enables problem-solving across varied question types", "c": "It is less important than memorising examples", "d": "It only matters in theoretical subjects", "ans": "B", "exp": "Conceptual clarity allows transfer of knowledge to new problems."},
                {"q": "What does 'active learning' mean in a study context?", "a": "Attending all classes without taking notes", "b": "Engaging with material through practice, questions and discussion", "c": "Listening passively to lectures", "d": "Highlighting textbook content only", "ans": "B", "exp": "Active learning involves engaging with the content, not passive consumption."},
                {"q": "Which is a sign of strong subject mastery?", "a": "Reciting definitions without error", "b": "Explaining concepts in your own words and solving novel problems", "c": "Scoring high on first attempts only", "d": "Avoiding topics you find difficult", "ans": "B", "exp": "True mastery means being able to explain and apply concepts flexibly."},
                {"q": "How should a student approach topics they find difficult?", "a": "Skip them and focus on easier content", "b": "Ask for help and practise more frequently", "c": "Read them quickly and move on", "d": "Only revisit them the night before exams", "ans": "B", "exp": "Consistent practice and seeking help when stuck are key strategies for improving weak areas."},
                {"q": "What is the benefit of reviewing past mistakes in quizzes?", "a": "It is discouraging and should be avoided", "b": "It confirms what you already know", "c": "It identifies specific knowledge gaps and corrects misconceptions", "d": "It only helps if you scored very poorly", "ans": "C", "exp": "Analysing errors directs future study effort to the areas that need it most."},
            ],
            [
                {"q": f"What makes a question on '{topic_name}' 'hard' difficulty?", "a": "It uses longer sentences", "b": "It requires integrating multiple concepts and deeper analysis", "c": "It has more answer options", "d": "Hard questions are the same as easy, just worded differently", "ans": "B", "exp": "Higher-order questions require synthesis of ideas, not just recall."},
                {"q": "How does feedback after a quiz improve learning?", "a": "It is only useful for the teacher", "b": "It provides no learning benefit", "c": "It helps the student identify and correct misunderstandings immediately", "d": "It only matters if the student fails", "ans": "C", "exp": "Immediate corrective feedback accelerates learning by catching errors early."},
                {"q": "What is the purpose of explanation fields in quiz answers?", "a": "To add extra text to the response", "b": "To help students understand why an answer is correct or incorrect", "c": "To make questions look more complex", "d": "To fill space", "ans": "B", "exp": "Explanations reinforce correct understanding and help learners avoid repeating mistakes."},
                {"q": "Which practice best prepares a student for NEB exams?", "a": "Completing only objective-type questions", "b": "Practising diverse question types including long-answer and application", "c": "Focusing only on model questions from one year", "d": "Memorising mark schemes without understanding", "ans": "B", "exp": "NEB exams include diverse question formats, so varied practice is essential."},
                {"q": "Why should a student track their quiz history?", "a": "For competitive comparison with classmates", "b": "To monitor improvement over time and target weak areas", "c": "It has no practical value", "d": "Only teachers benefit from tracking results", "ans": "B", "exp": "Tracking performance helps personalise study plans and measure genuine improvement."},
            ],
            [
                {"q": f"When you encounter an unfamiliar problem related to '{topic_name}', what should you do first?", "a": "Guess and move on", "b": "Identify which concept or formula applies, then work methodically", "c": "Look up the exact answer without trying", "d": "Skip it entirely", "ans": "B", "exp": "Methodical problem-solving begins with identifying the relevant principle."},
                {"q": "What does spaced repetition help with?", "a": "Learning multiple subjects simultaneously without breaks", "b": "Moving information from short-term to long-term memory", "c": "Avoiding the need to study difficult topics", "d": "Completing homework faster", "ans": "B", "exp": "Spaced repetition leverages the spacing effect to improve long-term retention."},
                {"q": "Why is interleaving different topics during study sessions effective?", "a": "It is not effective; blocked practice is always better", "b": "It forces the brain to distinguish between concepts, improving discrimination", "c": "It reduces the total study time needed", "d": "It only works for mathematics", "ans": "B", "exp": "Interleaving increases difficulty in a productive way, leading to better long-term learning."},
                {"q": "What is the role of prior knowledge when learning a new topic?", "a": "Prior knowledge is irrelevant to new learning", "b": "It can interfere with new concepts and should be ignored", "c": "It provides a framework to connect and organise new information", "d": "Only prior knowledge gained from textbooks counts", "ans": "C", "exp": "Prior knowledge provides cognitive scaffolding, making new information easier to integrate."},
                {"q": "What does it mean to study 'deeply' rather than 'broadly'?", "a": "Covering the maximum number of topics in minimum time", "b": "Focusing on understanding relationships, causes and implications within fewer topics", "c": "Reading every page of every textbook", "d": "Only studying topics likely to appear in exams", "ans": "B", "exp": "Deep study prioritises comprehension and long-term understanding over surface-level coverage."},
            ],
        ]
        quiz_data = random.choice(FALLBACK_POOLS)
        logger.warning(f"[chapter_quiz] Using rotating fallback pool for topic {topic_id}")
        return jsonify({
            "status": "success",
            "quiz": quiz_data,
            "degraded": True,
            "message": "Limited connectivity — showing a standard practice quiz. Personalisation will resume when the AI service is back."
        })

    return jsonify({"status": "success", "quiz": quiz_data, "degraded": False})



@student_bp.route("/study/api/topic/<int:topic_id>/submit-quiz", methods=["POST"])
@login_required
def submit_chapter_quiz(topic_id):
    topic = Topic.query.get_or_404(topic_id)
    score = request.form.get("score", type=float)
    total = request.form.get("total", type=int, default=5)
    if score is None:
        return jsonify({"status": "error", "message": "Missing score."}), 400

    # ── Persist overall score row (same as before) ─────────────────────────────
    quiz_score = ChapterQuizScore(
        student_id=current_user.id, topic_id=topic.id, score=score, total_questions=total
    )
    db.session.add(quiz_score)
    db.session.flush()  # Get quiz_score.id before commit

    # ── GAP 1 + Per-question tracking: parse individual results from client ─────
    # The client sends JSON: questions=[{q, ans, selected, correct: bool}]
    try:
        questions_json = request.form.get("questions", "[]")
        questions_data = json.loads(questions_json)
    except Exception:
        questions_data = []

    if questions_data:
        for item in questions_data:
            q_text = item.get("q", "")
            if not q_text:
                continue

            # Per-question result row
            result_row = ChapterQuizResult(
                quiz_score_id=quiz_score.id,
                student_id=current_user.id,
                topic_id=topic.id,
                question_text=q_text,
                selected_answer=item.get("selected", None),
                correct_answer=item.get("ans", ""),
                was_correct=bool(item.get("correct", False))
            )
            db.session.add(result_row)

            # Permanent seen-question record so future quizzes exclude it
            already_seen = TopicSeenQuestion.query.filter_by(
                student_id=current_user.id,
                topic_id=topic.id,
                question_text=q_text
            ).first()
            if not already_seen:
                seen_row = TopicSeenQuestion(
                    student_id=current_user.id,
                    topic_id=topic.id,
                    question_text=q_text
                )
                db.session.add(seen_row)

    db.session.commit()
    return jsonify({"status": "success", "score": score, "total": total})


@student_bp.route("/study/api/topic/<int:topic_id>/tts", methods=["POST"])
@login_required
def get_tts_audio(topic_id):
    api_key = current_app.config.get("ELEVENLABS_API_KEY")
    if not api_key:
        logger.warning("ELEVENLABS_API_KEY is not configured. Browser client-side SpeechSynthesis is used as fallback.")
        return jsonify({"status": "info", "message": "Local speech synth used. Configuration key missing in server env."})
    return jsonify({"status": "success", "message": "API config detected."})


@student_bp.route("/study/api/topic/<int:topic_id>/pdf", methods=["GET"])
@login_required
def get_chapter_pdf(topic_id):
    import html as html_module
    import traceback
    import fitz

    route_name = "/study/api/topic/<int:topic_id>/pdf"
    logger.info(
        "[PDF PIPELINE] Initiating download request. Route: %s, Topic ID: %d, User ID: %d",
        route_name, topic_id, current_user.id
    )

    topic = Topic.query.get(topic_id)
    if not topic:
        logger.error("[PDF PIPELINE] Topic ID %d not found in database.", topic_id)
        return jsonify({"status": "error", "message": "Topic not found."}), 404

    chapter = topic.chapter
    subject = chapter.subject if chapter else None
    subject_id = subject.id if subject else None
    chapter_id = chapter.id if chapter else None

    # Retrieve learning material
    try:
        material = LearningMaterial.query.filter_by(topic_id=topic.id).first()
        db_retrieved = "success" if material else "not_found"
        logger.info(
            "[PDF PIPELINE] Database retrieval of material. Status: %s, Topic ID: %d, Subject ID: %s, Chapter ID: %s",
            db_retrieved, topic.id, subject_id, chapter_id
        )
    except Exception as db_err:
        logger.error(
            "[PDF PIPELINE] Database query error for material. Topic ID: %d, Exception: %s",
            topic_id, db_err
        )
        return jsonify({"status": "error", "message": "Database query failed."}), 500

    if not material:
        logger.warning(
            "[PDF PIPELINE] Material not found in DB for Topic ID %d. Download rejected.",
            topic_id
        )
        return jsonify({"status": "error", "message": "Material not found. Generate lesson first."}), 404

    # content length logging
    content_len = len(material.detailed_explanation or "") + len(material.introduction or "")
    logger.info(
        "[PDF PIPELINE] Material verified. Material ID: %d, Total content length: %d characters.",
        material.id, content_len
    )

    cache_dir = os.path.join(current_app.root_path, "static", "cache", "pdfs")
    os.makedirs(cache_dir, exist_ok=True)
    pdf_filename = f"chapter_{topic_id}.pdf"
    pdf_path = os.path.join(cache_dir, pdf_filename)

    # If the PDF file exists, is not empty (0-bytes), and is not a corrupted blank page (< 5KB), we can serve it. 
    # Otherwise, generate/regenerate it robustly.
    pdf_valid = os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 5000

    if not pdf_valid:
        logger.info(
            "[PDF PIPELINE] PDF cache invalid, too small, or missing. Starting fitz PDF generation. Path: %s",
            pdf_path
        )
        try:
            import re
            
            # Create HTML content for the Story
            html_content = f"""
            <html>
            <head>
            <style>
                body {{
                    font-family: Helvetica, sans-serif;
                    font-size: 10pt;
                    line-height: 1.4;
                    color: #333333;
                }}
                h1 {{
                    font-size: 16pt;
                    color: #1a365d;
                    border-bottom: 1px solid #1a365d;
                    padding-bottom: 5px;
                    margin-top: 20px;
                }}
                h2 {{
                    font-size: 12pt;
                    color: #2b6cb0;
                    margin-top: 15px;
                    margin-bottom: 5px;
                }}
                p {{
                    margin-bottom: 10px;
                    text-align: justify;
                }}
                ul, ol {{
                    margin-bottom: 10px;
                    padding-left: 20px;
                }}
                li {{
                    margin-bottom: 5px;
                }}
                .header {{
                    font-size: 9pt;
                    color: #718096;
                    margin-bottom: 20px;
                    border-bottom: 1px solid #e2e8f0;
                    padding-bottom: 5px;
                }}
            </style>
            </head>
            <body>
                <div class="header">
                    SUBJECT: {html_module.escape(subject.name if subject else "Unknown")} | 
                    CHAPTER {chapter.chapter_number if chapter else 0}: {html_module.escape(chapter.name if chapter else "Unknown")}
                </div>
                <h1>{html_module.escape(topic.name)}</h1>
            """

            if material.learning_objectives:
                html_content += f"<h2>Learning Objectives</h2>{material.learning_objectives}"
            if material.introduction:
                html_content += f"<h2>Introduction</h2>{material.introduction}"
            if material.detailed_explanation:
                html_content += f"<h2>Detailed Explanation</h2>{material.detailed_explanation}"
            if material.concepts:
                html_content += f"<h2>Core Concepts</h2>{material.concepts}"
            if material.summary:
                html_content += f"<h2>Summary</h2>{material.summary}"
                
            html_content += """
            </body>
            </html>
            """
            
            writer = fitz.DocumentWriter(pdf_path)
            mediabox = fitz.paper_rect("a4")
            rect = mediabox + (50, 50, -50, -50)  # margins
            story = fitz.Story(html=html_content)
            
            more = 1
            while more:
                device = writer.begin_page(mediabox)
                more, _ = story.place(rect)
                story.draw(device)
                writer.end_page()
                
            writer.close()
            logger.info(
                "[PDF PIPELINE] fitz PDF generated and saved successfully. Material ID: %d, Topic ID: %d, Path: %s",
                material.id, topic_id, pdf_path
            )
        except Exception as pdf_err:
            logger.error(
                "[PDF PIPELINE] fitz PDF generation failed. Material ID: %d, Topic ID: %d, Error: %s, Traceback: %s",
                material.id, topic_id, pdf_err, traceback.format_exc()
            )
            # Remove partial/failed PDF file if it was created
            if os.path.exists(pdf_path):
                try:
                    os.remove(pdf_path)
                except Exception:
                    pass
            return jsonify({"status": "error", "message": "Failed to generate PDF document."}), 500
    else:
        logger.info(
            "[PDF PIPELINE] Serving PDF from cache. Material ID: %d, Topic ID: %d, Path: %s",
            material.id, topic_id, pdf_path
        )

    # Track reviewed chapter in user progress history
    try:
        progress = ReviewedChapter.query.filter_by(student_id=current_user.id, topic_id=topic.id).first()
        if not progress:
            progress = ReviewedChapter(student_id=current_user.id, topic_id=topic.id, status="in progress")
            db.session.add(progress)
        else:
            progress.last_accessed_at = datetime.utcnow()
        db.session.commit()
        db_save_status = "success"
    except Exception as db_err:
        db_save_status = "failed"
        logger.warning(
            "[PDF PIPELINE] Could not commit ReviewedChapter progress record to database: %s",
            db_err
        )

    logger.info(
        "[PDF PIPELINE] PDF dispatch complete. Material ID: %d, Topic ID: %d, DB Progress Log: %s",
        material.id, topic_id, db_save_status
    )

    from flask import send_from_directory
    return send_from_directory(cache_dir, pdf_filename, as_attachment=True)


@student_bp.route("/study-material/search", methods=["GET"])
@login_required
def search_study_materials():
    query = request.args.get("q", "").lower().strip()
    profile = StudentProfile.query.filter_by(user_id=current_user.id).first()
    active_subjects = get_profile_subjects(profile)
    active_subject_ids = [s.id for s in active_subjects]
    
    results = []
    if query:
        topics = Topic.query.join(Chapter).filter(
            Chapter.subject_id.in_(active_subject_ids),
            (Topic.name.like(f"%{query}%")) | (Chapter.name.like(f"%{query}%"))
        ).all()
        for t in topics:
            results.append({
                "topic_id": t.id,
                "topic_name": t.name,
                "chapter_name": t.chapter.name,
                "subject_name": t.chapter.subject.name,
                "subject_id": t.chapter.subject_id
            })
    return jsonify({"status": "success", "results": results})


@student_bp.route("/my-downloads", methods=["GET"])
@login_required
def my_downloads_page():
    downloads = ReviewedChapter.query.filter(
        ReviewedChapter.student_id == current_user.id,
        ReviewedChapter.status.in_(["completed", "in progress"])
    ).order_by(ReviewedChapter.last_accessed_at.desc()).all()
    
    profile = StudentProfile.query.filter_by(user_id=current_user.id).first()
    
    return render_template(
        "student/my_downloads.html",
        downloads=downloads,
        profile=profile
    )


# ── BULK ZIP UPLOAD & RAG ROUTES ──────────────────────────────────────────────

@student_bp.route("/study-materials/upload-zip", methods=["POST"])
@login_required
def upload_zip_batch():
    from threading import Thread
    from flask import current_app
    from app.models import MaterialImportBatch
    from app.services.zip_import import async_process_zip

    if 'zip_file' not in request.files:
        return jsonify({"status": "error", "message": "No zip file uploaded."}), 400

    zip_file = request.files['zip_file']
    if not zip_file or not zip_file.filename:
        return jsonify({"status": "error", "message": "No selected zip file."}), 400

    ext = zip_file.filename.rsplit('.', 1)[-1].lower()
    if ext != 'zip':
        return jsonify({"status": "error", "message": "File must be a .zip archive."}), 400

    profile = StudentProfile.query.filter_by(user_id=current_user.id).first()
    enrolled_subjects = get_profile_subjects(profile)
    if not enrolled_subjects:
        return jsonify({"status": "error", "message": "No active subjects found in profile."}), 400

    try:
        batch = MaterialImportBatch(
            user_id=current_user.id,
            source_filename=zip_file.filename,
            stored_zip_path='',
            status='processing',
            total_files_found=0,
            matched_files=0,
            unmatched_files=0
        )
        db.session.add(batch)
        db.session.flush()

        upload_root = f"uploads/user_{current_user.id}/batch_{batch.id}"
        os.makedirs(upload_root, exist_ok=True)
        zip_path = os.path.join(upload_root, 'source.zip')
        zip_file.save(zip_path)
        batch.stored_zip_path = zip_path
        db.session.commit()

        app = current_app._get_current_object()
        thread = Thread(target=async_process_zip, args=(app, batch.id, current_user.id), daemon=True)
        thread.start()

        return jsonify({
            "status": "accepted",
            "batch_id": batch.id,
            "message": "Zip upload processing started in background."
        }), 202
    except Exception as e:
        return jsonify({"status": "error", "message": f"Failed to start zip processing: {str(e)}"}), 500



@student_bp.route("/study-materials/import/<int:batch_id>/review", methods=["GET"])
@login_required
def review_import_batch(batch_id):
    from app.models import MaterialImportBatch
    batch = MaterialImportBatch.query.get_or_404(batch_id)
    if batch.user_id != current_user.id:
        flash("Unauthorized access to import batch.", "danger")
        return redirect(url_for("student.study_material"))

    profile = StudentProfile.query.filter_by(user_id=current_user.id).first()
    enrolled_subjects = get_profile_subjects(profile)

    return render_template("student/zip_review.html", batch=batch, enrolled_subjects=enrolled_subjects)


@student_bp.route("/study-materials/import/<int:batch_id>/resolve", methods=["POST"])
@login_required
def resolve_import_batch(batch_id):
    from app.models import MaterialImportBatch, MaterialImportUnmatched, UploadedMaterial
    batch = MaterialImportBatch.query.get_or_404(batch_id)
    if batch.user_id != current_user.id:
        flash("Unauthorized access.", "danger")
        return redirect(url_for("student.study_material"))

    upload_root = f"uploads/user_{current_user.id}/batch_{batch.id}/extracted"
    from app.services.zip_import import classify_category
    from app.services.text_extraction import extract_text_from_file
    from app.services.rag_embeddings import embed_and_store_material
    from app.services.module_descriptor_parser import parse_module_descriptor
    import shutil, uuid

    ALLOWED_EXT = {'.pdf', '.docx', '.pptx', '.txt', '.png', '.jpg', '.jpeg'}

    for item in batch.unmatched_items:
        choice = request.form.get(f"subject_map_{item.id}")
        if choice and choice != 'skip':
            try:
                subject_id = int(choice)
                item.resolved_subject_id = subject_id

                target_path = os.path.join(upload_root, item.folder_path_in_zip) if item.folder_path_in_zip else upload_root
                if os.path.exists(target_path):
                    final_dir = f"uploads/user_{current_user.id}/subject_{subject_id}"
                    os.makedirs(final_dir, exist_ok=True)

                    files_to_process = []
                    if os.path.isfile(target_path):
                        files_to_process.append((target_path, os.path.dirname(target_path), os.path.basename(target_path)))
                    else:
                        for dirpath, _, filenames in os.walk(target_path):
                            for fname in filenames:
                                files_to_process.append((os.path.join(dirpath, fname), dirpath, fname))

                    for src, dirpath, fname in files_to_process:
                        if fname.startswith('.'):
                            continue
                        ext = os.path.splitext(fname)[1].lower()
                        if ext not in ALLOWED_EXT:
                            continue
                        
                        rel_dir = os.path.relpath(dirpath, upload_root)
                        folder_segments = [] if rel_dir == '.' else rel_dir.split(os.sep)

                        dest = os.path.join(final_dir, f"{uuid.uuid4().hex}_{fname}")
                        shutil.move(src, dest)
                        category = classify_category(folder_segments, fname)

                        mat = UploadedMaterial(
                            user_id=current_user.id,
                            subject_id=subject_id,
                            filename=fname,
                            file_path=dest,
                            file_type=ext.lstrip('.'),
                            category=category,
                            import_batch_id=batch.id,
                            file_size_bytes=os.path.getsize(dest),
                            embedding_status='pending'
                        )
                        db.session.add(mat)
                        db.session.flush()

                        mat.extracted_text = extract_text_from_file(mat.file_path, mat.file_type)
                        db.session.commit()
                        if mat.extracted_text:
                            embed_and_store_material(mat.id)
                            if mat.category == 'Module Descriptor':
                                parse_module_descriptor(mat.user_id, mat.subject_id, mat.id, mat.extracted_text)
            except (ValueError, TypeError) as e:
                pass

    batch.status = "committed"
    batch.committed_at = datetime.utcnow()
    db.session.commit()

    flash("Zip study materials resolved and imported successfully!", "success")
    return redirect(url_for("student.study_material"))


@student_bp.route("/study-materials/import/<int:batch_id>/status", methods=["GET"])
@login_required
def import_batch_status(batch_id):
    from app.models import MaterialImportBatch, UploadedMaterial
    batch = MaterialImportBatch.query.get_or_404(batch_id)
    if batch.user_id != current_user.id:
        return jsonify({"status": "error", "message": "Unauthorized access."}), 403

    redirect_url = None
    if batch.status == 'reviewing':
        redirect_url = url_for("student.review_import_batch", batch_id=batch.id)
    elif batch.status in ('committed', 'extracted'):
        redirect_url = url_for("student.study_material")

    materials = UploadedMaterial.query.filter_by(import_batch_id=batch.id).all()
    total_materials = len(materials)
    ready_materials = sum(1 for m in materials if m.embedding_status == 'ready')

    return jsonify({
        "status": batch.status,
        "batch_status": batch.status,
        "batch_id": batch.id,
        "total_files": batch.total_files_found,
        "matched_files": batch.matched_files,
        "unmatched_files": batch.unmatched_files,
        "total_materials": total_materials,
        "ready_materials": ready_materials,
        "redirect_url": redirect_url,
        "error_log": batch.error_log
    })


@student_bp.route("/subjects/<int:subject_id>/coverage", methods=["GET"])
@login_required
def subject_coverage_api(subject_id):
    from app.services.coverage_analysis import compute_coverage
    results = compute_coverage(current_user.id, subject_id)
    return jsonify({"status": "success", "coverage": results})


@student_bp.route("/subjects/<int:subject_id>/module-info", methods=["GET"])
@login_required
def subject_module_info_api(subject_id):
    from app.models import ModuleDescriptor
    md = ModuleDescriptor.query.filter_by(user_id=current_user.id, subject_id=subject_id).first()
    if not md:
        return jsonify({"status": "success", "module_descriptor": None})

    data = {
        "has_final_exam": md.has_final_exam,
        "exam_weight_pct": md.exam_weight_pct,
        "coursework_weight_pct": md.coursework_weight_pct,
        "has_presentation": md.has_presentation,
        "topics": json.loads(md.topics_json) if md.topics_json else [],
        "assessment_dates": json.loads(md.assessment_dates_json) if md.assessment_dates_json else [],
        "extracted_at": md.extracted_at.strftime('%Y-%m-%d') if md.extracted_at else None
    }
    return jsonify({"status": "success", "module_descriptor": data})


@student_bp.route("/api/rag/chat", methods=["POST"])
@login_required
def api_rag_chat():
    """
    General Personal AI Tutor + RAG Hybrid Assistant Endpoint.
    Handles general educational questions via Gemini and grounds answers in
    the student's authorized study materials when matching RAG context is found.
    """
    data = request.get_json() or {}
    user_message = (data.get("message") or "").strip()

    if not user_message:
        return jsonify({"status": "error", "message": "Query message cannot be empty."}), 400

    if len(user_message) > 1000:
        return jsonify({"status": "error", "message": "Query message is too long (max 1000 characters)."}), 400

    # 1. Parse optional subject context
    subject_id = None
    subject_name = None
    raw_subj_id = data.get("subject_id")
    if raw_subj_id is not None:
        try:
            target_id = int(raw_subj_id)
            subj = Subject.query.get(target_id)
            if subj:
                profile = StudentProfile.query.filter_by(user_id=current_user.id).first()
                active_subs = get_profile_subjects(profile)
                if subj.id in [s.id for s in active_subs]:
                    subject_id = subj.id
                    subject_name = subj.name
        except (TypeError, ValueError):
            subject_id = None

    chapter_id = data.get("chapter_id")
    topic_id = data.get("topic_id")
    try:
        chapter_id = int(chapter_id) if chapter_id is not None else None
        topic_id = int(topic_id) if topic_id is not None else None
    except (TypeError, ValueError):
        chapter_id, topic_id = None, None

    # 2. Retrieve authorized RAG chunks (scoped to student's user_id)
    from app.services.rag_retrieval import retrieve_relevant_chunks_with_metadata, RAG_MIN_SIMILARITY_THRESHOLD
    chunks = retrieve_relevant_chunks_with_metadata(
        user_id=current_user.id,
        subject_id=subject_id,
        query=user_message,
        top_k=3,
        chapter_id=chapter_id,
        topic_id=topic_id,
    )

    max_sim = max([c["similarity_score"] for c in chunks], default=0.0)
    is_grounded = bool(chunks and max_sim >= RAG_MIN_SIMILARITY_THRESHOLD)

    # 3. Format Prompt based on Hybrid AI vs RAG Grounded Mode
    if is_grounded:
        context_str = "\n\n".join([f"--- SOURCE [{c['filename']}] ---\n{c['chunk_text']}" for c in chunks])
        subject_ctx_str = f" for the subject '{subject_name}'" if subject_name else ""
        prompt = f"""You are a helpful AI Study Assistant and Personal Tutor{subject_ctx_str}.
Use the following extracted study material context as reference to answer the student's question clearly.

STUDY MATERIAL CONTEXT:
{context_str}

STUDENT QUESTION:
{user_message}

Answer concisely, accurately, and clearly in student-friendly terms."""
    else:
        subject_ctx_str = f" Currently studying: {subject_name}." if subject_name else ""
        prompt = f"""You are a helpful, encouraging personal AI Study Assistant and Educational Tutor across all subjects.{subject_ctx_str}
Answer the student's question clearly, accurately, and concisely in student-friendly terms.

STUDENT QUESTION:
{user_message}"""

    # 4. Invoke existing AI service (Gemini) with quota management
    try:
        from app.services.ai_service import call_ai_model
        ai_response = call_ai_model(prompt)
    except Exception as e:
        return jsonify({"status": "error", "message": f"AI service error: {str(e)}"}), 500

    # 5. Format Deduplicated Sources (only if grounded)
    sources = []
    if is_grounded:
        seen_sources = set()
        for c in chunks:
            key = c["filename"]
            if key not in seen_sources:
                seen_sources.add(key)
                sources.append({
                    "filename": c["filename"],
                    "chapter_title": c["chapter_title"],
                    "topic_title": c["topic_title"],
                    "similarity_score": c["similarity_score"],
                })

    # 6. Maintain bounded chat history in session (max 6 items)
    session_key = f"rag_chat_history_{subject_id or 'global'}"
    history = session.get(session_key, [])
    history.append({"role": "user", "content": user_message})
    history.append({"role": "assistant", "content": ai_response})
    session[session_key] = history[-6:]

    return jsonify({
        "status": "success",
        "grounded": is_grounded,
        "answer": ai_response,
        "sources": sources
    }), 200

