"""
app/utils/curriculum_detector.py

Phase 4D — Curriculum Structure Detection
Phase 4E — Subject Matching and Deduplication
Phase 4F — Program Matching

Analyzes extracted text blocks to detect:
  - Program name
  - Semester / Term
  - Subject code and name
  - Level of study

Then matches detected subjects against existing Subject records.

Design rules:
  - Never invent values.
  - Never hallucinate program names or subject codes.
  - NEEDS_REVIEW when ambiguous.
  - Conservative fuzzy matching (similarity >= FUZZY_THRESHOLD required for auto-match).
  - Admin must confirm every match that is not exact.
"""

import re
import unicodedata
from typing import Optional

# Minimum similarity score to auto-link a subject (conservative)
FUZZY_THRESHOLD = 0.85
# Below this we still show the best candidate but require admin review
CANDIDATE_THRESHOLD = 0.65


# ── Text normalisation helpers ─────────────────────────────────────────────────

def _norm(text: str) -> str:
    """Lower-case, remove accents, collapse whitespace."""
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", text.lower())
    ascii_text = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", ascii_text).strip()


def _remove_stop(text: str) -> str:
    stops = {
        "in", "of", "and", "the", "for", "to", "a", "an",
        "introduction", "advanced", "fundamentals", "principles",
        "concepts", "basics",
    }
    return " ".join(w for w in text.split() if w not in stops)


# ── Simple token-based similarity ─────────────────────────────────────────────

def _token_similarity(a: str, b: str) -> float:
    """
    Jaccard similarity on word tokens (case-insensitive).
    Returns 0.0–1.0.
    """
    ta = set(_norm(a).split())
    tb = set(_norm(b).split())
    if not ta or not tb:
        return 0.0
    intersection = ta & tb
    union = ta | tb
    return len(intersection) / len(union)


def _seq_similarity(a: str, b: str) -> float:
    """
    Simple character-level similarity using difflib SequenceMatcher.
    Returns 0.0–1.0.
    """
    from difflib import SequenceMatcher
    return SequenceMatcher(None, _norm(a), _norm(b)).ratio()


def similarity(a: str, b: str) -> float:
    """Combined score: max of Jaccard and SequenceMatcher."""
    return max(_token_similarity(a, b), _seq_similarity(a, b))


# ── Extraction patterns ────────────────────────────────────────────────────────

# Patterns that label subject code + name on a line: "CODE SubjectName" or "CODE - SubjectName"
_CODE_NAME_RE = re.compile(
    r"^([A-Z]{2,8}[-_]?[A-Z0-9]{2,8})\s*[-–:]?\s*(.+)$", re.IGNORECASE
)

# Patterns for semester detection
_SEMESTER_RE = re.compile(
    r"(semester\s*[1-9IVX]+|year\s*[1-4]+|core\s*modules?|elective|foundation|year\s*one|year\s*two)",
    re.IGNORECASE,
)

# Patterns for program detection
_PROGRAM_KEYWORDS = [
    re.compile(r"programme?\s*:\s*(.+)", re.IGNORECASE),
    re.compile(r"program(?:me)?\s*[:—]\s*(.+)", re.IGNORECASE),
    re.compile(r"(B\.?Sc\.?\s+(?:Hons\.?\s+)?(?:in\s+)?[\w\s]+)", re.IGNORECASE),
    re.compile(r"(M\.?Sc\.?\s+[\w\s]+)", re.IGNORECASE),
    re.compile(r"(Bachelor\s+of\s+[\w\s]+)", re.IGNORECASE),
    re.compile(r"(Master\s+of\s+[\w\s]+)", re.IGNORECASE),
]

_CREDIT_RE = re.compile(r"(\d+)\s*credit", re.IGNORECASE)
_CODE_INLINE_RE = re.compile(r"\b([A-Z]{2,8}[0-9]{2,4})\b")


# ── Curriculum structure detector ─────────────────────────────────────────────

class DetectedSubject:
    """Raw detection from the document — NOT yet matched to the DB."""
    __slots__ = (
        "extracted_program", "extracted_semester", "extracted_term",
        "extracted_code", "extracted_name", "extracted_credits",
        "action", "match_confidence", "matched_subject_id",
        "candidates",   # list of (Subject, score) for NEEDS_REVIEW
    )

    def __init__(self, **kw):
        for s in self.__slots__:
            setattr(self, s, kw.get(s))
        if self.action is None:
            self.action = "NEEDS_REVIEW"
        if self.candidates is None:
            self.candidates = []


def detect_curriculum(extraction_result: dict) -> dict:
    """
    Analyse the extraction result and return:
    {
        "detected_program": str | None,
        "detected_semester": str | None,
        "subjects": [DetectedSubject, ...]
    }
    """
    blocks = extraction_result.get("text_blocks", [])
    tables = extraction_result.get("tables", [])

    detected_program: Optional[str] = None
    detected_semester: Optional[str] = None
    subjects: list = []

    # ── 1. Scan text blocks for program / semester / subjects ──────────────────
    current_semester: Optional[str] = None

    for block in blocks:
        text = block.get("text", "").strip()
        if not text:
            continue

        # Program detection
        if detected_program is None:
            for pat in _PROGRAM_KEYWORDS:
                m = pat.search(text)
                if m:
                    candidate = m.group(1).strip()
                    if 4 < len(candidate) < 120:
                        detected_program = candidate
                        break

        # Semester detection
        sem_m = _SEMESTER_RE.search(text)
        if sem_m:
            current_semester = _title_case(sem_m.group(1).strip())
            detected_semester = detected_semester or current_semester
            continue

        # Subject code + name pattern on a single line
        subj = _try_extract_subject(text, current_semester)
        if subj:
            subjects.append(subj)

    # ── 2. Scan tables for subjects ────────────────────────────────────────────
    for table in tables:
        table_subjects = _parse_table_subjects(table, current_semester)
        subjects.extend(table_subjects)

    # Deduplicate by (code or name)
    subjects = _deduplicate_subjects(subjects)

    return {
        "detected_program": detected_program,
        "detected_semester": detected_semester or current_semester,
        "subjects": subjects,
    }


def _title_case(s: str) -> str:
    return re.sub(r"\b(\w)", lambda m: m.group(1).upper(), s.lower())


def _try_extract_subject(text: str, semester: Optional[str]) -> Optional[DetectedSubject]:
    """Try to parse a single text line as a subject code + name."""
    # Skip lines that are clearly not subjects
    if len(text) < 4 or len(text) > 200:
        return None
    skip_words = {
        "semester", "year", "module", "programme", "program", "faculty",
        "university", "level", "credit", "total", "core", "elective",
        "course", "description", "outline", "syllabus", "introduction",
    }
    first_word = text.split()[0].lower() if text.split() else ""
    if first_word in skip_words:
        return None

    m = _CODE_NAME_RE.match(text)
    if m:
        code = m.group(1).strip().upper()
        name = m.group(2).strip()
        if len(name) > 5:
            credits_m = _CREDIT_RE.search(name)
            credits = int(credits_m.group(1)) if credits_m else None
            name_clean = _CREDIT_RE.sub("", name).strip().rstrip(",;:")
            return DetectedSubject(
                extracted_code=code,
                extracted_name=name_clean,
                extracted_semester=semester,
                extracted_credits=credits,
            )
    return None


def _parse_table_subjects(table: list, semester: Optional[str]) -> list:
    """Parse a table (list of list[str]) looking for subject rows."""
    results = []
    if not table or len(table) < 2:
        return results

    # Identify columns from header row
    header = [_norm(c) for c in table[0]]
    code_col = name_col = credit_col = sem_col = None
    for i, h in enumerate(header):
        if any(k in h for k in ("code", "module code", "subject code", "module no")):
            code_col = i
        elif any(k in h for k in ("name", "module name", "subject name", "title", "description")):
            name_col = i
        elif any(k in h for k in ("credit", "credits", "ch", "credit hour")):
            credit_col = i
        elif any(k in h for k in ("semester", "sem", "term")):
            sem_col = i

    if name_col is None and code_col is None:
        # Try heuristic: first 2 cols are code + name
        if len(header) >= 2:
            code_col, name_col = 0, 1

    for row in table[1:]:
        if not row or all(not c for c in row):
            continue

        code = row[code_col].strip().upper() if code_col is not None and code_col < len(row) else None
        name = row[name_col].strip() if name_col is not None and name_col < len(row) else None
        if not name and not code:
            continue

        credits_raw = row[credit_col].strip() if credit_col is not None and credit_col < len(row) else None
        credits = None
        if credits_raw:
            try:
                credits = int(float(credits_raw))
            except ValueError:
                pass

        row_semester = semester
        if sem_col is not None and sem_col < len(row):
            sem_text = row[sem_col].strip()
            if sem_text:
                row_semester = sem_text

        if name and len(name) > 3:
            results.append(DetectedSubject(
                extracted_code=code or None,
                extracted_name=name,
                extracted_semester=row_semester,
                extracted_credits=credits,
            ))

    return results


def _deduplicate_subjects(subjects: list) -> list:
    """Remove exact duplicate (code, name) pairs."""
    seen = set()
    unique = []
    for s in subjects:
        key = (_norm(s.extracted_code or ""), _norm(s.extracted_name or ""))
        if key in seen:
            continue
        seen.add(key)
        unique.append(s)
    return unique


# ── Subject matcher ────────────────────────────────────────────────────────────

def match_subjects(detected_subjects: list, existing_subjects: list) -> list:
    """
    For each DetectedSubject, find the best match in existing_subjects.
    Sets action, match_confidence, matched_subject_id, candidates on each item.

    existing_subjects: list of Subject ORM objects.
    Returns the same list with action/match fields populated.
    """
    for ds in detected_subjects:
        _match_one(ds, existing_subjects)
    return detected_subjects


def _match_one(ds: DetectedSubject, existing: list) -> None:
    """Sets action, match_confidence, matched_subject_id, candidates on ds."""
    candidates = []

    for subj in existing:
        score = 0.0

        # Exact code match → always wins
        if ds.extracted_code and subj.code:
            if _norm(ds.extracted_code) == _norm(subj.code):
                score = 1.0
                ds.action = "LINK_EXISTING"
                ds.match_confidence = 1.0
                ds.matched_subject_id = subj.id
                ds.candidates = [(subj.id, subj.name, 1.0)]
                return

        # Name similarity
        if ds.extracted_name and subj.name:
            name_score = similarity(ds.extracted_name, subj.name)
            reduced_score = similarity(
                _remove_stop(_norm(ds.extracted_name)),
                _remove_stop(_norm(subj.name))
            )
            score = max(name_score, reduced_score)

        if score >= CANDIDATE_THRESHOLD:
            candidates.append((score, subj))

    # Sort by score descending
    candidates.sort(key=lambda x: x[0], reverse=True)

    if candidates:
        best_score, best_subj = candidates[0]
        if best_score >= FUZZY_THRESHOLD:
            # Auto-link
            ds.action = "LINK_EXISTING"
            ds.match_confidence = best_score
            ds.matched_subject_id = best_subj.id
            ds.candidates = [(s, subj.id, subj.name) for s, subj in candidates[:5]]
        elif len(candidates) == 1:
            # One plausible match but below threshold → NEEDS_REVIEW
            ds.action = "NEEDS_REVIEW"
            ds.match_confidence = best_score
            ds.matched_subject_id = best_subj.id
            ds.candidates = [(best_score, best_subj.id, best_subj.name)]
        else:
            # Multiple ambiguous candidates
            ds.action = "NEEDS_REVIEW"
            ds.match_confidence = best_score
            ds.matched_subject_id = None
            ds.candidates = [(s, subj.id, subj.name) for s, subj in candidates[:5]]
    else:
        # No match found
        ds.action = "CREATE_NEW"
        ds.match_confidence = 0.0
        ds.matched_subject_id = None
        ds.candidates = []


# ── Program matcher ────────────────────────────────────────────────────────────

def match_program(detected_program_name: Optional[str], existing_programs: list) -> dict:
    """
    Match detected_program_name against existing CurriculumProgram objects.

    Returns:
    {
        "action": "LINK_EXISTING" | "NEEDS_REVIEW" | "NO_MATCH",
        "matched_program_id": int | None,
        "match_confidence": float,
        "candidates": [(program_id, program_name, score), ...]
    }
    """
    if not detected_program_name:
        return {
            "action": "NEEDS_REVIEW",
            "matched_program_id": None,
            "match_confidence": 0.0,
            "candidates": [],
        }

    candidates = []
    for prog in existing_programs:
        score = similarity(detected_program_name, prog.name)
        if score >= CANDIDATE_THRESHOLD:
            candidates.append((score, prog))

    candidates.sort(key=lambda x: x[0], reverse=True)

    if candidates:
        best_score, best_prog = candidates[0]
        if best_score >= FUZZY_THRESHOLD:
            return {
                "action": "LINK_EXISTING",
                "matched_program_id": best_prog.id,
                "match_confidence": best_score,
                "candidates": [(s, p.id, p.name) for s, p in candidates[:5]],
            }
        else:
            return {
                "action": "NEEDS_REVIEW",
                "matched_program_id": candidates[0][1].id,
                "match_confidence": best_score,
                "candidates": [(s, p.id, p.name) for s, p in candidates[:5]],
            }
    else:
        return {
            "action": "NO_MATCH",
            "matched_program_id": None,
            "match_confidence": 0.0,
            "candidates": [],
        }
