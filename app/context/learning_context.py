"""
app/context/learning_context.py
================================
Centralized Student Learning Context — Single Source of Truth.

Every existing module (Dashboard, Assessment, AI Assistant, Study Planner,
Progress, Student Profile) reads from and writes to this context instead of
issuing independent, isolated DB queries.

Design principles:
  - Request-scoped   : Instantiated once per request via get_learning_context().
                       Thread-safe, no shared global mutable state.
  - Lazy properties  : DB queries run at most once per request, cached on self.
  - No new DB tables : Pure aggregation layer over existing SQLAlchemy models.
  - Session bridge   : ai_conversation_history lives in Flask session but is
                       surfaced through this context so the AI module reads it
                       from one place.
  - Backward compatible: Routes pass ctx.X where they had local variables.
                         Template code is untouched.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional, Any

from flask import session
from flask_login import current_user

from app.utils.timezone_utils import local_now_for_user, local_today_for_user
from app import db
from app.models import (
    User, StudentProfile, Subject, StudentSubject,
    Chapter, Topic, LearningProgress, LearningMaterial,
    QuizScore, StudentNote, StudyLog, StudyPlan,
    Schedule, Assignment, Prediction, StudentAssessment,
    AssessmentResponse, AssessmentQuestion, Exam, Flashcard,
    Recommendation, Goal, AvailabilitySlot, StudyLogAnalysis,
)

logger = logging.getLogger(__name__)


def _subject_key(value: str) -> str:
    key = re.sub(r"[^a-z0-9]+", "", (value or "").lower())
    aliases = {
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
    return aliases.get(key, key)


# ---------------------------------------------------------------------------
# Factory helper — call this at the top of every route
# ---------------------------------------------------------------------------

def get_learning_context(user_id: int) -> "StudentLearningContext":
    """
    Return a fresh StudentLearningContext for the given user_id.

    Usage in routes::

        ctx = get_learning_context(current_user.id)
        ctx.study_hours       # reads total logged hours
        ctx.update_profile()  # writes to DB
    """
    return StudentLearningContext(user_id)


# ---------------------------------------------------------------------------
# Core context class
# ---------------------------------------------------------------------------

class StudentLearningContext:
    """
    Aggregates every piece of student learning state that is relevant across
    multiple modules.  Queries are lazy-loaded and cached for the lifetime of
    a single HTTP request.
    """

    # ── Construction ─────────────────────────────────────────────────────────

    def __init__(self, user_id: int):
        self.student_id: int = user_id

        # Private lazy-load caches — never access directly outside this class
        self._user: Optional[User] = None
        self._profile: Optional[StudentProfile] = None
        self._subjects: Optional[List[Subject]] = None
        self._study_logs: Optional[List[StudyLog]] = None
        self._quiz_scores: Optional[List[QuizScore]] = None
        self._completed_progress: Optional[List[LearningProgress]] = None
        self._all_progress: Optional[List[LearningProgress]] = None
        self._assignments: Optional[List[Assignment]] = None
        self._schedules: Optional[List[Schedule]] = None
        self._predictions: Optional[List[Prediction]] = None
        self._assessment_history: Optional[List[StudentAssessment]] = None
        self._notes: Optional[List[StudentNote]] = None
        self._goals: Optional[List[Goal]] = None
        self._latest_plan: Optional[StudyPlan] = None

        # Derived caches
        self._weak_subjects: Optional[List[str]] = None
        self._strong_subjects: Optional[List[str]] = None
        self._weak_chapters: Optional[List[Dict]] = None
        self._weak_topics: Optional[List[Dict]] = None
        self._strong_chapters: Optional[List[Dict]] = None
        self._strong_topics: Optional[List[Dict]] = None
        self._achievements: Optional[List[Dict]] = None
        self._recent_activity: Optional[List[Dict]] = None
        self._recommendations: Optional[List[str]] = None
        self._recommended_topics: Optional[List[Dict]] = None
        self._learning_progress: Optional[Dict] = None
        self._streak: Optional[int] = None

    # ── Identity & Profile ───────────────────────────────────────────────────

    @property
    def user(self) -> Optional[User]:
        if self._user is None:
            self._user = User.query.get(self.student_id)
        return self._user

    @property
    def profile(self) -> Optional[StudentProfile]:
        if self._profile is None:
            self._profile = StudentProfile.query.filter_by(
                user_id=self.student_id
            ).first()
        return self._profile

    @property
    def current_class(self) -> Optional[str]:
        return getattr(self.profile, "study_level", None)

    @property
    def current_subject(self) -> Optional[str]:
        """Returns the first subject the student is enrolled in (if any)."""
        subs = self.subjects
        return subs[0].name if subs else None

    @property
    def learning_preferences(self) -> Dict[str, str]:
        p = self.profile
        if not p:
            return {}
        return {
            "explanation_level": p.explanation_level or "Intermediate",
            "preferred_language": p.preferred_language or "English",
            "study_goal": p.study_goal or "Improve Grades",
        }

    @property
    def current_goal(self) -> Optional[str]:
        return getattr(self.profile, "study_goal", None)

    @property
    def exam_date(self) -> Optional[Any]:
        goals = self._get_goals()
        for g in goals:
            if g.target_date and not g.achieved:
                return g.target_date
        return None

    # ── Subjects ─────────────────────────────────────────────────────────────

    @property
    def subjects(self) -> List[Subject]:
        if self._subjects is None:
            self._subjects = self._resolve_subjects()
        return self._subjects

    def _resolve_subjects(self) -> List[Subject]:
        p = self.profile
        if not p:
            return []

        try:
            from app.routes.student import get_profile_subjects
            subjects = get_profile_subjects(p)
            if subjects:
                return subjects
        except Exception as exc:
            logger.warning("Falling back to local subject resolution: %s", exc)

        user_subs = StudentSubject.query.filter_by(
            user_id=self.student_id
        ).all()
        if user_subs:
            subjects = []
            seen = set()
            for mapping in user_subs:
                if not mapping.subject:
                    continue
                key = _subject_key(mapping.subject.name)
                if key in seen:
                    continue
                seen.add(key)
                subjects.append(mapping.subject)
            return subjects

        if not p.study_level:
            return []

        default_subs = Subject.query.filter_by(
            level_of_study=p.study_level
        ).all()

        for ds in default_subs:
            mapping = StudentSubject(
                user_id=self.student_id, subject_id=ds.id
            )
            db.session.add(mapping)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

        return default_subs

    # ── Study Logs ───────────────────────────────────────────────────────────

    @property
    def _logs(self) -> List[StudyLog]:
        if self._study_logs is None:
            self._study_logs = StudyLog.query.filter_by(
                user_id=self.student_id
            ).all()
        return self._study_logs

    @property
    def study_hours(self) -> float:
        return round(sum(log.duration_hours or 0 for log in self._logs), 2)

    @property
    def streak(self) -> int:
        if self._streak is not None:
            return self._streak

        all_log_dates = {log.date for log in self._logs}
        today_dt = local_today_for_user(self.student_id)
        count = 0
        check = today_dt
        if check not in all_log_dates:
            check -= timedelta(days=1)
        while check in all_log_dates:
            count += 1
            check -= timedelta(days=1)
        self._streak = count
        return self._streak

    # ── Quiz Scores ──────────────────────────────────────────────────────────

    @property
    def completed_quizzes(self) -> List[QuizScore]:
        if self._quiz_scores is None:
            self._quiz_scores = QuizScore.query.filter_by(
                user_id=self.student_id
            ).all()
        return self._quiz_scores

    @property
    def completed_quizzes_count(self) -> int:
        return len(self.completed_quizzes)

    # ── Learning Progress ────────────────────────────────────────────────────

    @property
    def completed_lessons(self) -> List[LearningProgress]:
        if self._completed_progress is None:
            self._completed_progress = LearningProgress.query.filter_by(
                user_id=self.student_id, is_completed=True
            ).all()
        return self._completed_progress

    @property
    def completed_lessons_count(self) -> int:
        return len(self._logs)   # matches previous behavior in profile route

    @property
    def completed_topic_ids(self) -> set:
        if self._all_progress is None:
            self._all_progress = LearningProgress.query.filter_by(
                user_id=self.student_id
            ).all()
        return {r.topic_id for r in self._all_progress if r.is_completed}

    @property
    def learning_progress(self) -> Dict[str, float]:
        """
        Returns a dict of {subject_name: pct_completed} across all subjects.
        A topic is 'completable' if it has an associated LearningMaterial.
        """
        if self._learning_progress is not None:
            return self._learning_progress

        result: Dict[str, float] = {}
        done_ids = self.completed_topic_ids

        for subj in self.subjects:
            chapters = Chapter.query.filter_by(subject_id=subj.id).all()
            total_topics = 0
            done_topics = 0
            for ch in chapters:
                topics = Topic.query.filter_by(chapter_id=ch.id).all()
                for t in topics:
                    total_topics += 1
                    if t.id in done_ids:
                        done_topics += 1
            pct = (done_topics / total_topics * 100) if total_topics > 0 else 0.0
            result[subj.name] = round(pct, 1)

        self._learning_progress = result
        return result

    # ── Notes ────────────────────────────────────────────────────────────────

    @property
    def completed_notes(self) -> List[StudentNote]:
        if self._notes is None:
            self._notes = StudentNote.query.filter_by(
                user_id=self.student_id
            ).all()
        return self._notes

    # ── Assignments ──────────────────────────────────────────────────────────

    @property
    def _assignment_list(self) -> List[Assignment]:
        if self._assignments is None:
            self._assignments = Assignment.query.filter_by(
                user_id=self.student_id
            ).all()
        return self._assignments

    @property
    def assignment_completion(self) -> float:
        assignments = self._assignment_list
        if not assignments:
            pred = self.latest_prediction
            return round(pred.assignment_completion_pct, 1) if pred else 0.0
        completed = sum(1 for a in assignments if a.status == "completed")
        return round((completed / len(assignments)) * 100, 1)

    # ── Schedule ─────────────────────────────────────────────────────────────

    @property
    def _schedule_list(self) -> List[Schedule]:
        if self._schedules is None:
            self._schedules = Schedule.query.filter_by(
                user_id=self.student_id
            ).all()
        return self._schedules

    @property
    def current_tasks(self) -> List[Schedule]:
        """Today's scheduled study slots, sorted by start time."""
        from datetime import time
        today_idx = local_now_for_user(self.student_id).weekday()
        today_slots = sorted(
            [s for s in self._schedule_list if s.day_of_week == today_idx],
            key=lambda x: x.start_time or time(0, 0),
        )
        for slot in today_slots:
            if slot.subject_id:
                subj = Subject.query.get(slot.subject_id)
                slot.subject_name = subj.name if subj else "Study Block"
            else:
                slot.subject_name = "Study Block"
        return today_slots

    @property
    def weekly_schedule(self) -> Dict[int, List[Schedule]]:
        result = {i: [] for i in range(7)}
        for s in self._schedule_list:
            subj_name = "Study Block"
            if s.subject_id:
                subj = Subject.query.get(s.subject_id)
                if subj:
                    subj_name = subj.name
            s.subject_name = subj_name
            result[s.day_of_week].append(s)
        return result

    @property
    def schedule_risk_counts(self) -> Dict[str, int]:
        high = medium = low = 0
        for s in self._schedule_list:
            if s.description and "High Risk" in s.description:
                high += 1
            elif s.description and "Medium Risk" in s.description:
                medium += 1
            elif s.description and "Low Risk" in s.description:
                low += 1
        return {"high": high, "medium": medium, "low": low}

    @property
    def total_week_hours(self) -> float:
        total = 0.0
        dummy = date(2026, 1, 1)
        for s in self._schedule_list:
            if s.start_time and s.end_time:
                dt_start = datetime.combine(dummy, s.start_time)
                dt_end = datetime.combine(dummy, s.end_time)
                if dt_end < dt_start:
                    dt_end += timedelta(days=1)
                total += (dt_end - dt_start).total_seconds() / 3600.0
        return round(total, 1)

    @property
    def subject_hours_chart(self):
        subject_hours: Dict[str, float] = {}
        dummy = date(2026, 1, 1)
        for s in self._schedule_list:
            name = "Other"
            if s.subject_id:
                subj = Subject.query.get(s.subject_id)
                if subj:
                    name = subj.name
            if s.start_time and s.end_time:
                dt_start = datetime.combine(dummy, s.start_time)
                dt_end = datetime.combine(dummy, s.end_time)
                if dt_end < dt_start:
                    dt_end += timedelta(days=1)
                duration = (dt_end - dt_start).total_seconds() / 3600.0
                subject_hours[name] = round(subject_hours.get(name, 0.0) + duration, 2)
        return subject_hours

    # ── Predictions ──────────────────────────────────────────────────────────

    @property
    def _prediction_list(self) -> List[Prediction]:
        if self._predictions is None:
            self._predictions = Prediction.query.filter_by(
                user_id=self.student_id
            ).order_by(Prediction.date.desc()).all()
        return self._predictions

    @property
    def latest_prediction(self) -> Optional[Prediction]:
        preds = self._prediction_list
        return preds[0] if preds else None

    @property
    def risk_summary(self) -> str:
        pred = self.latest_prediction
        return pred.predicted_risk_level if pred else "Unknown"

    # ── Assessment History ───────────────────────────────────────────────────

    @property
    def assessment_history(self) -> List[StudentAssessment]:
        if self._assessment_history is None:
            self._assessment_history = StudentAssessment.query.filter_by(
                student_id=self.student_id
            ).order_by(StudentAssessment.completed_at.desc()).all()
        return self._assessment_history

    @property
    def current_assessment(self) -> Dict:
        """
        The active (in-progress) assessment state from Flask session.
        Modules write to the session directly during assessment flow; this
        property gives a named view of that state.
        """
        return {
            "subjects": session.get("assessment_subjects", []),
            "current_idx": session.get("assessment_current_idx", 0),
            "scores": session.get("assessment_scores", {}),
            "history": session.get("assessment_history", {}),
            "question_history": session.get("assessment_question_history", {}),
        }

    # ── Weak / Strong Subjects ───────────────────────────────────────────────

    @property
    def weak_subjects(self) -> List[str]:
        if self._weak_subjects is None:
            self._compute_subject_strengths()
        return self._weak_subjects

    @property
    def strong_subjects(self) -> List[str]:
        if self._strong_subjects is None:
            self._compute_subject_strengths()
        return self._strong_subjects

    def _compute_subject_strengths(self):
        """
        Derive strong/weak subjects from QuizScore + Exam history.
        Mirrors the logic that previously lived inline in profile().
        """
        weak: List[str] = []
        strong: List[str] = []

        for s in self.subjects:
            scores = [
                qs.score  # QuizScore.score is the percentage field
                for qs in QuizScore.query.filter_by(
                    user_id=self.student_id, subject_id=s.id
                ).all()
                if qs.score is not None
            ]
            avg_score = sum(scores) / len(scores) if scores else None

            exams = [
                ex.score_pct
                for ex in Exam.query.filter_by(
                    user_id=self.student_id, subject_id=s.id
                ).all()
                if ex.score_pct is not None
            ]
            avg_exam = sum(exams) / len(exams) if exams else None

            if avg_score is not None and avg_exam is not None:
                final_score = (avg_score + avg_exam) / 2
            elif avg_score is not None:
                final_score = avg_score
            elif avg_exam is not None:
                final_score = avg_exam
            else:
                final_score = None

            if final_score is not None:
                if final_score >= 75:
                    strong.append(s.name)
                elif final_score < 50:
                    weak.append(s.name)

        self._weak_subjects = weak
        self._strong_subjects = strong

    # ── Weak / Strong Chapters & Topics (from Assessment session) ────────────

    @property
    def weak_chapters(self) -> List[Dict]:
        if self._weak_chapters is None:
            self._compute_chapter_topic_strengths()
        return self._weak_chapters

    @property
    def weak_topics(self) -> List[Dict]:
        if self._weak_topics is None:
            self._compute_chapter_topic_strengths()
        return self._weak_topics

    @property
    def strong_chapters(self) -> List[Dict]:
        if self._strong_chapters is None:
            self._compute_chapter_topic_strengths()
        return self._strong_chapters

    @property
    def strong_topics(self) -> List[Dict]:
        if self._strong_topics is None:
            self._compute_chapter_topic_strengths()
        return self._strong_topics

    def _compute_chapter_topic_strengths(self):
        """
        Derive weak/strong chapters and topics from the assessment question
        history stored in Flask session. Mirrors the logic that previously
        lived inline in dashboard() and assessment_results().
        """
        q_history: Dict[str, bool] = session.get(
            "assessment_question_history", {}
        )

        weak_ch_counts: Dict[int, int] = {}
        strong_ch_counts: Dict[int, int] = {}

        for q_id_str, is_correct in q_history.items():
            try:
                q = AssessmentQuestion.query.get(int(q_id_str))
            except (ValueError, TypeError):
                continue
            if not q or not q.chapter_id:
                continue
            if is_correct:
                strong_ch_counts[q.chapter_id] = (
                    strong_ch_counts.get(q.chapter_id, 0) + 1
                )
            else:
                weak_ch_counts[q.chapter_id] = (
                    weak_ch_counts.get(q.chapter_id, 0) + 1
                )

        def build_chapter_topic_lists(ch_counts: Dict[int, int]):
            chapters: List[Dict] = []
            topics: List[Dict] = []
            for ch_id, count in ch_counts.items():
                ch = Chapter.query.get(ch_id)
                if not ch:
                    continue
                subj = Subject.query.get(ch.subject_id)
                subj_name = subj.name if subj else "Unknown Subject"
                chapters.append({
                    "id": ch.id,
                    "name": ch.name,
                    "chapter_number": ch.chapter_number,
                    "subject_name": subj_name,
                    "count": count,
                    "wrong_count": count,
                })
                for t in Topic.query.filter_by(chapter_id=ch.id).all():
                    if not any(rt["id"] == t.id for rt in topics):
                        topics.append({
                            "id": t.id,
                            "name": t.name,
                            "chapter_name": ch.name if ch.name.startswith('Unit') else f"Unit {ch.chapter_number}: {ch.name}",
                            "subject_name": subj_name,
                            "subject_id": ch.subject_id,
                        })
            return chapters, topics

        self._weak_chapters, self._weak_topics = build_chapter_topic_lists(
            weak_ch_counts
        )
        self._strong_chapters, self._strong_topics = build_chapter_topic_lists(
            strong_ch_counts
        )

    # ── Recommended Topics (for Dashboard) ──────────────────────────────────

    @property
    def recommended_topics(self) -> List[Dict]:
        if self._recommended_topics is not None:
            return self._recommended_topics

        weak_chs = self.weak_chapters
        result: List[Dict] = []
        for ch_info in weak_chs[:3]:
            ch = Chapter.query.get(ch_info["id"])
            if ch:
                t = Topic.query.filter_by(chapter_id=ch.id).first()
                if t:
                    result.append({
                        "id": t.id,
                        "name": t.name,
                        "chapter_name": ch.name,
                        "subject_name": ch_info["subject_name"],
                        "subject_id": ch.subject_id,
                    })
        self._recommended_topics = result
        return self._recommended_topics

    # ── Achievements ─────────────────────────────────────────────────────────

    @property
    def achievements(self) -> List[Dict]:
        if self._achievements is not None:
            return self._achievements

        result: List[Dict] = []

        # Assessment completed
        if self.profile and self.profile.has_completed_assessment:
            result.append({
                "title": "Knowledge Profile Unlocked",
                "desc": "Successfully completed your diagnostic assessment evaluation.",
                "icon": "fa-brain text-gradient",
            })

        # High-scoring quizzes
        for q in self.completed_quizzes:
            if q.score and q.score >= 80:
                subj = Subject.query.get(q.subject_id)
                subj_name = subj.name if subj else "Subject"
                result.append({
                    "title": f"Mastered {subj_name} Quiz",
                    "desc": f"Scored an excellent {q.score:.0f}% in topic practice assessment.",
                    "icon": "fa-trophy text-warning",
                })

        # Completed lessons
        for cp in self.completed_lessons:
            topic = Topic.query.get(cp.topic_id)
            if topic:
                ch = Chapter.query.get(topic.chapter_id)
                subj = Subject.query.get(ch.subject_id) if ch else None
                subj_name = subj.name if subj else "Subject"
                result.append({
                    "title": f"Completed Lesson: {topic.name}",
                    "desc": f"Finished reading digital textbook study materials for {subj_name}.",
                    "icon": "fa-check-circle text-success",
                })

        if not result:
            result.append({
                "title": "Welcome to Smart Study",
                "desc": "Start your learning journey by running an ML prediction or completing assessments.",
                "icon": "fa-rocket text-primary",
            })

        self._achievements = result
        return self._achievements

    # ── Recent Activity ──────────────────────────────────────────────────────

    @property
    def recent_activity(self) -> List[Dict]:
        if self._recent_activity is not None:
            return self._recent_activity

        activities: List[Dict] = []

        # Study logs (last 10)
        for log in sorted(self._logs, key=lambda x: x.date, reverse=True)[:10]:
            subj_name = "General Study"
            if log.subject_id:
                s = Subject.query.get(log.subject_id)
                if s:
                    subj_name = s.name
            activities.append({
                "type": "study_log",
                "date": log.date,
                "description": f"Studied {subj_name} for {log.duration_hours:.1f} hours",
                "icon": "fa-book",
            })

        # Quiz scores (last 10)
        for qs in sorted(
            self.completed_quizzes,
            key=lambda x: x.completed_at or datetime.min,
            reverse=True,
        )[:10]:
            s = Subject.query.get(qs.subject_id)
            subj_name = s.name if s else "Subject"
            activities.append({
                "type": "quiz",
                "date": qs.completed_at,
                "description": f"Completed quiz in {subj_name} — Score: {qs.score:.1f}%",
                "icon": "fa-clipboard-check",
            })

        # Sort merged list by date descending, return top 15
        activities.sort(
            key=lambda x: x["date"] if x["date"] else date.min, reverse=True
        )
        self._recent_activity = activities[:15]
        return self._recent_activity

    # ── Recommendations (risk-based) ─────────────────────────────────────────

    @property
    def recommendations(self) -> List[str]:
        if self._recommendations is not None:
            return self._recommendations

        recs: List[str] = []
        risk = self.schedule_risk_counts

        if risk["high"] > 0:
            recs.append(
                "Critical: You have high risk subjects! Check your Adaptive Planner immediately."
            )
        if risk["medium"] > 0:
            recs.append(
                "Warning: Allocate extra focus to your moderate risk subjects."
            )
        if risk["low"] > 0:
            recs.append(
                "Great job on low risk subjects! Maintain your current habits."
            )

        # Add weak-subject recommendations
        for ws in self.weak_subjects[:2]:
            recs.append(
                f"Focus Area: '{ws}' is showing below-average performance. "
                "Consider extra revision sessions."
            )

        self._recommendations = recs
        return self._recommendations

    # ── Study Planner ────────────────────────────────────────────────────────

    @property
    def study_planner(self) -> Optional[StudyPlan]:
        if self._latest_plan is None:
            self._latest_plan = StudyPlan.query.filter_by(
                student_id=self.student_id
            ).order_by(StudyPlan.generated_at.desc()).first()
        return self._latest_plan

    # ── AI Conversation History ───────────────────────────────────────────────

    @property
    def ai_conversation_history(self) -> List[Dict]:
        """Read AI chat history from Flask session."""
        return session.get("chat_history", [])

    # ── Goals ─────────────────────────────────────────────────────────────────

    def _get_goals(self) -> List[Goal]:
        if self._goals is None:
            self._goals = Goal.query.filter_by(
                user_id=self.student_id
            ).all()
        return self._goals

    # =========================================================================
    # MUTATION METHODS — Write to DB / session
    # =========================================================================

    def update_assessment_results(
        self,
        scores: Dict[str, Dict],
        question_history: Dict[str, bool],
    ) -> float:
        """
        Persist assessment results (StudentAssessment records), mark profile
        as having completed assessment, and invalidate cached derived data so
        the next read reflects new state.

        :param scores: {str(subject_id): {'correct': int, 'total': int}}
        :param question_history: {str(question_id): bool}
        :returns: Average score percentage across all subjects.
        """
        results: List[Dict] = []
        total_pct = 0.0
        count = 0

        for sub_id, data in scores.items():
            total_q = data.get('total', 12)
            flat_pct = (data['correct'] / total_q) * 100 if total_q > 0 else 0
            
            w_pts = data.get('weighted_points', 0)
            m_pts = data.get('max_points', total_q)
            weighted_pct = (w_pts / m_pts) * 100 if m_pts > 0 else 0
            
            tier = "beginner"
            if weighted_pct >= 70: tier = "advanced"
            elif weighted_pct >= 40: tier = "intermediate"

            sa = StudentAssessment(
                student_id=self.student_id,
                subject_id=int(sub_id),
                total_score=flat_pct,
                max_score=100.0,
                weighted_score=weighted_pct,
                knowledge_tier=tier,
            )
            db.session.add(sa)

            subj = Subject.query.get(int(sub_id))
            results.append({
                "subject": subj.name if subj else "Unknown",
                "score": weighted_pct,
                "tier": tier,
                "correct": data["correct"],
            })
            total_pct += weighted_pct
            count += 1

        avg_score = total_pct / count if count > 0 else 0

        p = self.profile
        if p:
            p.has_completed_assessment = True
            if p.prior_academic_score == 0:
                p.prior_academic_score = avg_score

        db.session.commit()

        # Invalidate caches that depend on assessment data
        self._assessment_history = None
        self._weak_chapters = None
        self._weak_topics = None
        self._strong_chapters = None
        self._strong_topics = None
        self._recommended_topics = None
        self._achievements = None

        return avg_score

    def update_study_planner(self, plan_data: Dict) -> StudyPlan:
        """
        Persist a new StudyPlan and invalidate the cached plan reference.
        """
        plan = StudyPlan(
            student_id=self.student_id,
            plan_data=__import__("json").dumps(plan_data),
            generated_at=datetime.utcnow(),
        )
        db.session.add(plan)
        db.session.commit()
        self._latest_plan = plan
        return plan

    def log_study_hours(
        self, subject_name: str, hours: float
    ) -> StudyLog:
        """
        Log study time for a subject, invalidate study-hour caches.
        """
        subj = Subject.query.filter(Subject.name.ilike(subject_name)).first()
        subject_id = subj.id if subj else None

        log = StudyLog(
            user_id=self.student_id,
            date=local_today_for_user(self.student_id),
            duration_hours=hours,
            subject_id=subject_id,
            notes="Logged via Study Planner",
        )
        db.session.add(log)
        db.session.commit()

        # Invalidate caches
        self._study_logs = None
        self._streak = None
        self._recent_activity = None

        return log

    def toggle_topic_completed(
        self, topic_id: int, completed: bool
    ) -> LearningProgress:
        """
        Toggle a topic's completed state and invalidate progress caches.
        """
        progress = LearningProgress.query.filter_by(
            user_id=self.student_id, topic_id=topic_id
        ).first()

        if not progress:
            progress = LearningProgress(
                user_id=self.student_id,
                topic_id=topic_id,
                is_completed=completed,
                completed_at=datetime.utcnow(),
            )
            db.session.add(progress)
        else:
            progress.is_completed = completed
            progress.completed_at = datetime.utcnow()

        db.session.commit()

        # Invalidate caches
        self._completed_progress = None
        self._all_progress = None
        self._learning_progress = None
        self._achievements = None

        return progress

    def save_quiz_score(
        self, subject_id: int, score_pct: float, total_questions: int
    ) -> QuizScore:
        """
        Save a quiz score and invalidate quiz-related caches.
        """
        qs = QuizScore(
            user_id=self.student_id,
            subject_id=subject_id,
            score=score_pct,
            total_questions=total_questions,
        )
        db.session.add(qs)
        db.session.commit()

        # Invalidate caches
        self._quiz_scores = None
        self._weak_subjects = None
        self._strong_subjects = None
        self._achievements = None
        self._recent_activity = None

        return qs

    def update_ai_history(self, history: List[Dict]):
        """
        Persist the AI conversation history back to Flask session.
        Keeps only the last 20 messages (10 turns) to save tokens.
        """
        session["chat_history"] = history[-20:]
        session.modified = True

    def clear_ai_history(self):
        """Clear the AI conversation history from Flask session."""
        session.pop("chat_history", None)
        session.modified = True

    def update_learning_preferences(self, data: Dict):
        """
        Update student-controlled learning preference fields on StudentProfile.
        Only accepts the three fields the student can still set manually;
        learning_style, response_length, and quiz_difficulty are now
        system-calculated and are intentionally excluded here.
        """
        p = self.profile
        if not p:
            return

        # Only these 3 fields are student-controlled now
        preference_fields = [
            "explanation_level",
            "study_goal",
            "preferred_language",
        ]
        for field in preference_fields:
            if field in data:
                setattr(p, field, data[field])

        db.session.commit()
        # Invalidate profile cache so next read picks up new values
        self._profile = None

    def update_profile(self, data: Dict):
        """
        Update core profile fields. ``data`` is a dict keyed by field name.
        Handles type coercion and ignores unknown keys gracefully.
        """
        p = self.profile
        if not p:
            return

        str_fields = [
            "country", "curriculum", "level_of_study", "study_level",
            "program", "semester", "timezone", "explanation_level",
            "study_goal", "preferred_language", "profile_pic", "peak_focus_time",
            "university", "university_type", "university_country", "program_duration",
        ]
        float_fields = ["cumulative_gpa", "attendance_pct", "target_score_goal"]
        int_fields = ["commute_buffer_minutes"]

        for field in str_fields:
            if field in data:
                setattr(p, field, data[field])

        for field in float_fields:
            if field in data:
                try:
                    setattr(p, field, float(data[field]))
                except (ValueError, TypeError):
                    pass

        for field in int_fields:
            if field in data:
                try:
                    setattr(p, field, max(0, int(data[field])))
                except (ValueError, TypeError):
                    pass

        db.session.commit()
        self._profile = None
        self._subjects = None  # study_level change may affect subjects

    def build_ai_system_context(self) -> str:
        """
        Build an enriched system-prompt context string for the AI service,
        incorporating weak/strong subjects and recent activity — so the AI
        gives better, more personalised responses.
        """
        p = self.profile
        if not p:
            return ""

        lines = [
            f"Country: {getattr(p, 'country', 'Nepal')}",
            f"Education Level: {getattr(p, 'level_of_study', 'N/A')}",
            f"Curriculum: {getattr(p, 'curriculum', 'N/A')}",
            f"Explanation Level: {getattr(p, 'explanation_level', 'Intermediate')}",
            f"Study Goal: {getattr(p, 'study_goal', 'Improve Grades')}",
            f"Language Preference: {getattr(p, 'preferred_language', 'English')}",
        ]

        # Add university context if available
        if getattr(p, "university_type", None) and getattr(p, "study_level", "") in ("Bachelors", "Masters"):
            lines.append(f"University Type: {p.university_type}")
            if p.university_type == "Foreign" and getattr(p, "university_country", None):
                lines.append(f"University Country: {p.university_country}")
            if getattr(p, "university", None):
                lines.append(f"University: {p.university}")
            if getattr(p, "program_duration", None):
                lines.append(f"Program Duration: {p.program_duration}")

        # System-derived style hint based on risk level (replaces manual learning_style field)
        risk = getattr(self, 'risk_summary', 'low')
        if risk == 'high':
            lines.append("Adaptive Style: Use simple, step-by-step explanations and frequent comprehension checks (student is at high risk).")
        elif risk == 'medium':
            lines.append("Adaptive Style: Balanced explanations with worked examples (student is at moderate risk).")
        else:
            lines.append("Adaptive Style: Standard depth with concise responses (student is performing well).")

        if getattr(p, "program", None):
            lines.append(f"Program/Faculty: {p.program}")
        if getattr(p, "semester", None):
            lines.append(f"Semester/Year: {p.semester}")

        if self.weak_subjects:
            lines.append(f"Weak Subjects (needs focus): {', '.join(self.weak_subjects)}")
        if self.strong_subjects:
            lines.append(f"Strong Subjects: {', '.join(self.strong_subjects)}")

        if self.weak_topics:
            weak_topic_names = [t["name"] for t in self.weak_topics[:5]]
            lines.append(
                f"Recent Assessment Weak Topics: {', '.join(weak_topic_names)}"
            )

        lines.append(f"Study Streak: {self.streak} day(s)")
        lines.append(f"Total Study Hours Logged: {self.study_hours:.1f} hrs")

        return "\n".join(f"  - {l}" for l in lines)
