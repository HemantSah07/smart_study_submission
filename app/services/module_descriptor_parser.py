# app/services/module_descriptor_parser.py
import json
from app.services.ai_service import ai_service, FEATURE_ASSISTANT

EXTRACTION_PROMPT = """You are extracting structured data from a university Module Descriptor document.
Return ONLY valid JSON, no preamble, no markdown fences, matching exactly this schema:

{{
  "has_final_exam": true or false,
  "exam_weight_pct": number or null,
  "coursework_weight_pct": number or null,
  "has_presentation": true or false,
  "topics": ["topic 1", "topic 2", ...],
  "assessment_dates": [{{"type": "Midterm", "date": "YYYY-MM-DD or null", "weight_pct": number}}]
}}

If a field cannot be determined from the text, use null (or false for booleans, or [] for lists).
Do not guess dates you cannot find in the text.

Module Descriptor text:
---
{text}
---
"""

def parse_module_descriptor(user_id: int, subject_id: int, material_id: int, extracted_text: str):
    from app.models import ModuleDescriptor
    from app import db

    truncated = extracted_text[:12000]
    prompt = EXTRACTION_PROMPT.format(text=truncated)

    try:
        response_text = ai_service.generate_content(prompt=prompt, feature=FEATURE_ASSISTANT)
        parsed = ai_service._parse_json(response_text, context="module_descriptor")
    except Exception:
        parsed = {}

    existing = ModuleDescriptor.query.filter_by(user_id=user_id, subject_id=subject_id).first()
    if not existing:
        existing = ModuleDescriptor(user_id=user_id, subject_id=subject_id)
        db.session.add(existing)

    existing.source_material_id = material_id
    existing.has_final_exam = parsed.get('has_final_exam')
    existing.exam_weight_pct = parsed.get('exam_weight_pct')
    existing.coursework_weight_pct = parsed.get('coursework_weight_pct')
    existing.has_presentation = parsed.get('has_presentation')
    existing.topics_json = json.dumps(parsed.get('topics', []))
    existing.assessment_dates_json = json.dumps(parsed.get('assessment_dates', []))
    existing.raw_extraction_json = json.dumps(parsed)
    existing.extraction_confidence = 'verified' if parsed else 'failed'
    db.session.commit()
    return existing
