# app/services/spaced_repetition.py
from datetime import datetime, timedelta
import numpy as np
from app.models import FlashcardReview, Flashcard
from app import db


def grade_typed_flashcard_answer(user_answer: str, target_answer: str) -> dict:
    """
    Computes semantic similarity between typed user answer and target flashcard answer
    using all-MiniLM-L6-v2 embeddings and keyword overlap to map to SuperMemo quality rating q in [0, 5].
    """
    import re
    if not user_answer or not user_answer.strip():
        return {"quality_rating": 0, "similarity_score": 0.0}

    u_clean = user_answer.strip().lower()
    t_clean = target_answer.strip().lower()

    # Word overlap calculation
    u_words = set(re.findall(r'\w+', u_clean))
    t_words = set(re.findall(r'\w+', t_clean))
    word_overlap = len(u_words.intersection(t_words)) / max(1, len(t_words)) if t_words else 0.0

    embed_similarity = 0.0
    try:
        from app.services.rag_embeddings import get_embedder
        embedder = get_embedder()
        v_user = embedder.encode(u_clean)
        v_target = embedder.encode(t_clean)

        norm_u = np.linalg.norm(v_user)
        norm_t = np.linalg.norm(v_target)

        if norm_u > 0 and norm_t > 0:
            embed_similarity = float(np.dot(v_user, v_target) / (norm_u * norm_t))
    except Exception as e:
        print(f"[Semantic Flashcard Grading Warning]: {e}")

    # Composite similarity score
    final_similarity = max(embed_similarity, word_overlap)
    if embed_similarity > 0 and word_overlap > 0:
        final_similarity = 0.5 * embed_similarity + 0.5 * word_overlap

    final_similarity = max(0.0, min(1.0, final_similarity))

    if final_similarity >= 0.75:
        q = 5
    elif final_similarity >= 0.60:
        q = 4
    elif final_similarity >= 0.45:
        q = 3
    elif final_similarity >= 0.30:
        q = 2
    elif final_similarity >= 0.15:
        q = 1
    else:
        q = 0

    return {"quality_rating": q, "similarity_score": round(final_similarity, 4)}


def process_sm2_review(user_id: int, flashcard_id: int, quality_rating: int = None, user_answer: str = None) -> dict:
    """
    Executes SuperMemo SM-2 Spaced Repetition algorithm on a flashcard review.
    If user_answer is provided, quality_rating is automatically computed via semantic similarity!
    """
    flashcard = Flashcard.query.get(flashcard_id)
    if not flashcard:
        raise ValueError("Flashcard not found.")

    similarity_score = None
    if user_answer is not None:
        target_answer = flashcard.back or ""
        eval_res = grade_typed_flashcard_answer(user_answer, target_answer)
        quality_rating = eval_res["quality_rating"]
        similarity_score = eval_res["similarity_score"]

    if quality_rating is None:
        raise ValueError("Either quality_rating or user_answer must be provided.")

    if quality_rating < 0 or quality_rating > 5:
        raise ValueError("Quality rating must be between 0 and 5.")

    review = FlashcardReview.query.filter_by(user_id=user_id, flashcard_id=flashcard_id).first()
    if not review:
        review = FlashcardReview(
            user_id=user_id,
            flashcard_id=flashcard_id,
            easiness_factor=2.5,
            interval_days=0,
            repetitions=0
        )
        db.session.add(review)

    q = quality_rating
    ef = review.easiness_factor or 2.5
    n = review.repetitions or 0
    interval = review.interval_days or 0

    if q >= 3:
        if n == 0:
            interval = 1
        elif n == 1:
            interval = 6
        else:
            interval = max(1, int(round(interval * ef)))
        n += 1
    else:
        n = 0
        interval = 1

    new_ef = ef + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
    if new_ef < 1.3:
        new_ef = 1.3

    now = datetime.utcnow()
    review.easiness_factor = round(new_ef, 4)
    review.interval_days = interval
    review.repetitions = n
    review.last_reviewed_at = now
    review.next_review_date = now + timedelta(days=interval)
    review.last_quality_rating = q

    db.session.commit()

    res = {
        "status": "success",
        "flashcard_id": flashcard_id,
        "quality_rating": q,
        "easiness_factor": review.easiness_factor,
        "interval_days": review.interval_days,
        "repetitions": review.repetitions,
        "next_review_date": review.next_review_date.isoformat()
    }
    if similarity_score is not None:
        res["similarity_score"] = similarity_score
    return res
