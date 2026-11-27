"""
app/services/analytics_service.py
===================================
Shared analytics service — single source of truth for computed metrics
consumed by both Dashboard and Profile routes.

Design:
  - Wraps StudentLearningContext (never duplicates its logic)
  - All DB queries run at most once per request (lazy-loaded)
  - No new DB tables — pure aggregation over existing models
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class StudentAnalyticsService:
    """
    Computes and caches analytics for a single student within one request.

    Usage::

        svc = StudentAnalyticsService(current_user.id)
        mastery = svc.subject_mastery()
        summary = svc.assessment_summary(limit=3)
        weak    = svc.weak_topics(limit=3)
    """

    def __init__(self, user_id: int):
        self.user_id = user_id
        self._ctx: Optional[object] = None
        self._mastery: Optional[Dict[str, float]] = None
        self._assessment_summary: Optional[Dict] = None
        self._weak_topics_cache: Optional[List[Dict]] = None
        self._academic_summary_cache: Optional[Dict] = None

    # ── Internal helpers ──────────────────────────────────────────────────────

    @property
    def ctx(self):
        """Lazy-load StudentLearningContext."""
        if self._ctx is None:
            from app.context.learning_context import get_learning_context
            self._ctx = get_learning_context(self.user_id)
        return self._ctx

    # ── Public API ─────────────────────────────────────────────────────────────

    def subject_mastery(self) -> Dict[str, float]:
        """
        Returns {subject_name: weighted_percentage} for every active subject.
        Uses the existing get_subject_performance_snapshot() which blends
        assessment scores, chapter quiz scores, and marksheet data.
        Returns 0.0 for subjects with no data yet.
        """
        if self._mastery is not None:
            return self._mastery

        from app.routes.student import get_subject_performance_snapshot

        result: Dict[str, float] = {}
        for subj in self.ctx.subjects:
            snap = get_subject_performance_snapshot(self.user_id, subj.id)
            result[subj.name] = round(snap["score"] or 0.0, 1)

        self._mastery = result
        return self._mastery

    def assessment_summary(self, limit: Optional[int] = None) -> Dict:
        """
        Returns:
          total_attempted   -- total number of SA records
          total_correct     -- sum of correct answers across all assessments
          total_incorrect   -- derived from total_questions - total_correct
          accuracy          -- overall accuracy %
          recent            -- all or last `limit` StudentAssessment rows with detail
        """
        if self._assessment_summary is not None and self._assessment_summary.get("_limit") == limit:
            return self._assessment_summary

        from app.models import StudentAssessment, Subject, AssessmentResponse

        all_sa = (
            StudentAssessment.query
            .filter_by(student_id=self.user_id)
            .order_by(StudentAssessment.completed_at.desc())
            .all()
        )

        total_attempted = 0
        total_correct = 0
        total_questions = 0
        recent = []

        for sa in all_sa:
            resp_count = AssessmentResponse.query.filter_by(assessment_id=sa.id).count()
            if resp_count == 0:
                continue

            total_attempted += 1
            correct = round((sa.total_score or 0.0) / 100.0 * resp_count)
            total_correct += correct
            total_questions += resp_count

            if limit is None or len(recent) < limit:
                subj = Subject.query.get(sa.subject_id)
                recent.append({
                    "id": sa.id,
                    "subject": subj.name if subj else "Unknown",
                    "date": sa.completed_at,
                    "score_pct": round(sa.weighted_score or sa.total_score or 0.0, 1),
                    "correct": correct,
                    "total": resp_count,
                    "tier": sa.knowledge_tier or "beginner",
                })

        total_incorrect = max(0, total_questions - total_correct)
        accuracy = round((total_correct / total_questions * 100), 1) if total_questions > 0 else 0.0

        result = {
            "_limit": limit,
            "total_attempted": total_attempted,
            "total_correct": total_correct,
            "total_incorrect": total_incorrect,
            "accuracy": accuracy,
            "recent": recent,
        }
        self._assessment_summary = result
        return result

    def weak_topics(self, limit: int = 3) -> List[Dict]:
        """Returns ctx.weak_topics[:limit] (session-based assessment history)."""
        if self._weak_topics_cache is None:
            self._weak_topics_cache = self.ctx.weak_topics
        return self._weak_topics_cache[:limit]

    def improvement_trend(self) -> str:
        """
        Compares the last two StudentAssessment sessions' average score.
        Returns 'improving', 'declining', or 'stable'.
        """
        from app.models import StudentAssessment

        last_two = (
            StudentAssessment.query
            .filter_by(student_id=self.user_id)
            .order_by(StudentAssessment.completed_at.desc())
            .limit(2).all()
        )
        if len(last_two) < 2:
            return "stable"
        newer_score = last_two[0].weighted_score or last_two[0].total_score or 0.0
        older_score = last_two[1].weighted_score or last_two[1].total_score or 0.0
        diff = newer_score - older_score
        if diff >= 5:
            return "improving"
        elif diff <= -5:
            return "declining"
        return "stable"

    def academic_summary(self) -> Dict:
        """
        Returns:
          overall_performance  -- float avg weighted score
          strongest_subject    -- str
          weakest_subject      -- str
          risk_level           -- str from latest ML prediction
          overall_mastery      -- float avg mastery 0-100
          improvement_trend    -- 'improving' | 'declining' | 'stable'
        """
        if self._academic_summary_cache is not None:
            return self._academic_summary_cache

        from app.models import StudentAssessment

        mastery = self.subject_mastery()
        overall_mastery = round(sum(mastery.values()) / len(mastery), 1) if mastery else 0.0

        strongest = max(mastery, key=mastery.get) if mastery else "\u2014"
        weakest = min(mastery, key=mastery.get) if mastery else "\u2014"

        all_sa = StudentAssessment.query.filter_by(student_id=self.user_id).all()
        if all_sa:
            scores = [sa.weighted_score or sa.total_score or 0.0 for sa in all_sa]
            overall_performance = round(sum(scores) / len(scores), 1)
        else:
            overall_performance = 0.0

        result = {
            "overall_performance": overall_performance,
            "strongest_subject": strongest,
            "weakest_subject": weakest,
            "risk_level": self.ctx.risk_summary,
            "overall_mastery": overall_mastery,
            "improvement_trend": self.improvement_trend(),
        }
        self._academic_summary_cache = result
        return result
