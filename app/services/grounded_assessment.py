# app/services/grounded_assessment.py
import json
from app.services.rag_retrieval import retrieve_relevant_chunks
from app.services.ai_service import ai_service, FEATURE_MCQ

GROUNDED_MCQ_PROMPT = """Generate {count} multiple-choice questions for a student studying "{subject_name}".
Base the questions ONLY on the material provided below — do not introduce facts, dates, or figures not present in this material.
If the material is too thin to generate {count} distinct questions, generate fewer rather than inventing content.

Return ONLY a valid JSON list of objects matching schema:
[
  {{
    "q": "Question text?",
    "a": "Option A",
    "b": "Option B",
    "c": "Option C",
    "d": "Option D",
    "ans": "A",
    "explanation": "Explanation based on source text",
    "diff": "medium"
  }}
]

Source material:
---
{context}
---
"""

def generate_grounded_mcqs(user_id: int, subject_id: int, subject_name: str, topic_hint: str = None, count: int = 10):
    query = topic_hint or subject_name
    chunks = retrieve_relevant_chunks(user_id, subject_id, query, top_k=8)

    if not chunks:
        return None, 'no_uploaded_material'

    context = '\n\n---\n\n'.join(chunks)
    prompt = GROUNDED_MCQ_PROMPT.format(count=count, subject_name=subject_name, context=context)

    try:
        response_text = ai_service.generate_content(prompt=prompt, feature=FEATURE_MCQ)
        questions = ai_service._parse_json(response_text, context="grounded_mcq")
        if isinstance(questions, list) and len(questions) > 0:
            return questions, 'ok'
        return None, 'parse_error'
    except Exception as e:
        return None, f'ai_error: {str(e)}'
