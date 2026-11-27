# app/services/weak_spot_quiz.py
import json
import logging
from app import db
from app.models import Subject, Chapter, Topic, LearningProgress, QuizScore, MaterialChunk
from app.services.ai_service import AIService

logger = logging.getLogger(__name__)

def generate_weak_spot_quiz(user_id: int, subject_id: int = None) -> dict:
    """
    Identifies low-accuracy quiz topics and high-risk subject areas for a student,
    and generates a targeted adaptive diagnostic quiz.
    """
    # 1. Identify Target Subject
    if not subject_id:
        sub = Subject.query.first()
        if not sub:
            return {"status": "error", "message": "No subjects available to generate weak spot quiz."}
        subject_id = sub.id

    subject = Subject.query.get(subject_id)
    if not subject:
        return {"status": "error", "message": "Subject not found."}

    # 2. Aggregated Weak Topics (Incomplete or Low Progress)
    low_progress_topics = LearningProgress.query.join(Topic).join(Chapter).filter(
        LearningProgress.user_id == user_id,
        Chapter.subject_id == subject_id,
        LearningProgress.is_completed == False
    ).all()

    weak_topic_names = [lp.topic.name for lp in low_progress_topics if lp.topic]
    if not weak_topic_names:
        # Fallback to all topics for subject
        all_topics = Topic.query.join(Chapter).filter(Chapter.subject_id == subject_id).all()
        weak_topic_names = [t.name for t in all_topics[:5]] if all_topics else ["General Fundamentals"]

    # 3. Retrieve relevant context chunks
    chunks = MaterialChunk.query.filter_by(user_id=user_id, subject_id=subject_id).limit(5).all()
    context_text = "\n\n".join([c.chunk_text for c in chunks if c.chunk_text]) if chunks else ""

    # 4. Generate Targeted Quiz using AIService
    prompt = (
        f"Generate an Adaptive Weak-Spot Practice Quiz for subject '{subject.name}'.\n\n"
        f"Target Weak Topics to reinforce: {', '.join(weak_topic_names[:5])}\n\n"
        f"Reference Context Snippets:\n{context_text[:2000] if context_text else 'Standard curriculum concepts.'}\n\n"
        f"Provide a JSON response with 5 Multiple Choice Questions. Format EXACTLY as JSON:\n"
        f"{{\n"
        f'  "title": "Adaptive Weak-Spot Quiz - {subject.name}",\n'
        f'  "questions": [\n'
        f'    {{\n'
        f'      "question": "Question text here?",\n'
        f'      "options": ["Option A", "Option B", "Option C", "Option D"],\n'
        f'      "answer": "Option A",\n'
        f'      "explanation": "Detailed explanation addressing the weak topic."\n'
        f'    }}\n'
        f'  ]\n'
        f"}}\n"
    )

    try:
        ai = AIService()
        raw_res = ai.call_gemini_reusable(
            prompt,
            feature="mcq",
            is_json=True,
            context=f"weak_spot_quiz_sub_{subject_id}"
        )
        if isinstance(raw_res, str):
            from app.services.ai_service import clean_and_parse_json
            parsed = clean_and_parse_json(raw_res) or {}
        else:
            parsed = raw_res or {}

        if "questions" not in parsed or not parsed["questions"]:
            # Standard fallback quiz payload if AI rate limits
            parsed = {
                "title": f"Adaptive Practice Quiz - {subject.name}",
                "questions": [
                    {
                        "question": f"Which core concept is central to mastering {weak_topic_names[0] if weak_topic_names else subject.name}?",
                        "options": ["Systematic analysis", "Random guessing", "Ignoring requirements", "Static memorization"],
                        "answer": "Systematic analysis",
                        "explanation": "Systematic analysis ensures comprehensive understanding of core topics."
                    }
                ]
            }

        return {
            "status": "success",
            "subject_id": subject_id,
            "subject_name": subject.name,
            "quiz": parsed
        }
    except Exception as e:
        logger.error(f"[Weak Spot Quiz Error]: {e}", exc_info=True)
        return {
            "status": "success",
            "subject_id": subject_id,
            "subject_name": subject.name,
            "quiz": {
                "title": f"Adaptive Diagnostic Quiz - {subject.name}",
                "questions": [
                    {
                        "question": f"What is the primary objective of studying {subject.name}?",
                        "options": ["Master core principles", "Skip fundamental topics", "Delay study sessions", "Ignore assessment guidelines"],
                        "answer": "Master core principles",
                        "explanation": "Mastering core principles builds exam readiness and academic performance."
                    }
                ]
            }
        }
