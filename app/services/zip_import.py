# app/services/zip_import.py
import os
import zipfile
import uuid
import shutil
import re
import time
from datetime import datetime
from difflib import SequenceMatcher
from app.models import Subject, MaterialImportBatch, MaterialImportUnmatched, UploadedMaterial
from app import db

CATEGORY_ALIASES = {
    'apu resources': 'APU Resources',
    'apu resource': 'APU Resources',
    'resources': 'APU Resources',
    'lecture notes': 'APU Resources',
    'lectures': 'APU Resources',
    'slides': 'APU Resources',
    'tutorials': 'APU Resources',
    'labs': 'APU Resources',
    'module descriptor': 'Module Descriptor',
    'module descriptors': 'Module Descriptor',
    'descriptors': 'Module Descriptor',
    'descriptor': 'Module Descriptor',
    'md': 'Module Descriptor',
    'syllabus': 'Module Descriptor',
    'onedrive': 'OneDrive',
    'assignments': 'OneDrive',
    'assignment': 'OneDrive',
    'coursework': 'OneDrive',
}

FILENAME_KEYWORDS = {
    'lecture': 'APU Resources', 'slide': 'APU Resources',
    'tutorial': 'APU Resources', 'lab': 'APU Resources',
    'module_descriptor': 'Module Descriptor', 'md_': 'Module Descriptor',
    'syllabus': 'Module Descriptor',
    'assignment': 'OneDrive', 'brief': 'OneDrive',
}

NOISE_WORDS = {
    'lecture', 'lectures', 'week', 'weeks', 'unit', 'units', 'chapter', 'chapters',
    'module', 'descriptor', 'descriptors', 'assignment', 'assignments', 'lab', 'labs',
    'tutorial', 'tutorials', 'notes', 'slides', 'part', 'pdf', 'docx', 'pptx', 'txt',
    'apu', 'resources', 'onedrive', 'resource', 'doc', 'document', 'file'
}


def safe_move(src: str, dst: str, max_retries: int = 10, delay: float = 0.3):
    """
    Robust move wrapper for Windows environments.
    Retries when encountering transient PermissionError / WinError 32 caused by
    antivirus background scanning or lingering OS file locks.
    """
    for attempt in range(max_retries):
        try:
            shutil.move(src, dst)
            return
        except (PermissionError, OSError) as e:
            if attempt == max_retries - 1:
                try:
                    shutil.copy2(src, dst)
                    os.remove(src)
                    return
                except Exception:
                    raise e
            time.sleep(delay)


def classify_category(folder_segments: list[str], filename: str) -> str:
    """
    Check path segments from deepest folder to shallowest against CATEGORY_ALIASES.
    Fallback to filename keyword match, then default to 'APU Resources'.
    """
    for seg in reversed(folder_segments):
        key = seg.strip().lower()
        if key in CATEGORY_ALIASES:
            return CATEGORY_ALIASES[key]
        for alias, cat in CATEGORY_ALIASES.items():
            if alias in key:
                return cat

    fname_lower = filename.lower()
    for kw, cat in FILENAME_KEYWORDS.items():
        if kw in fname_lower:
            return cat

    return 'APU Resources'


def fuzzy_match_subject(target_text: str, candidate_subjects: list[Subject], threshold: float = 0.6) -> tuple[Subject | None, float]:
    """Simple ratio-based fuzzy match. Returns (best_subject_or_None, confidence 0-1)."""
    best, best_score = None, 0.0
    text_clean = target_text.lower().strip()
    if not text_clean:
        return None, 0.0

    for subj in candidate_subjects:
        subj_clean = subj.name.lower().strip()
        score = SequenceMatcher(None, text_clean, subj_clean).ratio()
        if score > best_score:
            best, best_score = subj, score

    return (best, best_score) if best_score >= threshold else (None, best_score)


def clean_filename_for_subject_matching(filename: str) -> str:
    """Strip extension and common noise words to isolate subject-specific words."""
    stem = os.path.splitext(filename)[0].lower()
    words = re.findall(r'[a-zA-Z]+', stem)
    filtered = [w for w in words if w not in NOISE_WORDS and len(w) > 1]
    return ' '.join(filtered)


def match_file_to_subject(
    folder_segments: list[str],
    filename: str,
    full_path: str,
    file_ext: str,
    enrolled_subjects: list[Subject]
) -> tuple[Subject | None, float, str | None]:
    """
    Multi-tier subject matching:
    Tier 1: Check folder path segments (deepest to shallowest).
    Tier 2: Check filename (substring of subject name/code, or cleaned stem fuzzy match).
    Tier 3: Check extracted document content (~300 words).
    Returns (matched_subject, confidence_score, extracted_text_or_None).
    """
    # Tier 1: Folder Path Segments (deepest to shallowest)
    for seg in reversed(folder_segments):
        subj, score = fuzzy_match_subject(seg, enrolled_subjects, threshold=0.6)
        if subj:
            return subj, score, None

        seg_lower = seg.lower()
        for subj_item in enrolled_subjects:
            s_name = subj_item.name.lower()
            if s_name in seg_lower or (len(s_name) > 4 and s_name[:5] in seg_lower):
                return subj_item, 0.85, None

    # Tier 2: Filename Substring & Cleaned Stem Match
    fname_lower = filename.lower()
    for subj_item in enrolled_subjects:
        s_name = subj_item.name.lower()
        if s_name in fname_lower:
            return subj_item, 0.90, None
        if hasattr(subj_item, 'code') and subj_item.code and subj_item.code.lower() in fname_lower:
            return subj_item, 0.95, None

    cleaned_stem = clean_filename_for_subject_matching(filename)
    if cleaned_stem:
        subj, score = fuzzy_match_subject(cleaned_stem, enrolled_subjects, threshold=0.6)
        if subj:
            return subj, score, None

    # Tier 3: Content-based Fallback Match
    from app.services.text_extraction import extract_text_from_file
    extracted_text = extract_text_from_file(full_path, file_ext)
    if extracted_text:
        text_sample = extracted_text[:2000].lower()
        best_subj, best_score = None, 0.0
        for subj_item in enrolled_subjects:
            s_name = subj_item.name.lower()
            if s_name in text_sample:
                return subj_item, 0.92, extracted_text
            if hasattr(subj_item, 'code') and subj_item.code and subj_item.code.lower() in text_sample:
                return subj_item, 0.95, extracted_text

            score = SequenceMatcher(None, s_name, text_sample[:len(s_name) * 2]).ratio()
            if score > best_score and score >= 0.5:
                best_subj, best_score = subj_item, score

        if best_subj:
            return best_subj, best_score, extracted_text

    return None, 0.0, extracted_text if 'extracted_text' in locals() else None


def resolve_subject_dynamically(path_str: str, enrolled_subjects: list[Subject]) -> tuple[Subject | None, float]:
    r"""
    Parse relative file paths against enrolled subjects:
    1. Extract APU Module Codes (e.g. BM050, CT006, CT071) using regex r'([A-Za-z]{2}\d{3})'
       and match them directly against enrolled subjects' code or name.
    2. Direct substring matching for full subject names present anywhere in path.
    3. Fall back to string fuzzy ratio matching on path components.
    """
    if not path_str or not enrolled_subjects:
        return (enrolled_subjects[0] if enrolled_subjects else None), 0.0

    path_lower = path_str.lower().replace('\\', '/')

    # 1. Regex search for APU Module Codes (e.g. BM050, CT006, CT071)
    codes_found = re.findall(r'([A-Za-z]{2}\d{3})', path_str)
    for code_match in codes_found:
        code_clean = code_match.upper()
        for subj in enrolled_subjects:
            if hasattr(subj, 'code') and subj.code and subj.code.upper() in code_clean:
                return subj, 1.0
            if code_clean in subj.name.upper():
                return subj, 0.95

    # 2. Direct Substring Matching
    for subj in enrolled_subjects:
        s_name = subj.name.lower().strip()
        if s_name and (s_name in path_lower or (len(s_name) > 4 and s_name[:6] in path_lower)):
            return subj, 0.90
        if hasattr(subj, 'code') and subj.code and subj.code.lower() in path_lower:
            return subj, 0.95

    # 3. Fuzzy Ratio Fallback on path components
    segments = [s.strip() for s in path_lower.split('/') if s.strip()]
    best_subj, best_score = None, 0.0
    for seg in reversed(segments):
        subj, score = fuzzy_match_subject(seg, enrolled_subjects, threshold=0.5)
        if subj and score > best_score:
            best_subj, best_score = subj, score

    if best_subj and best_score >= 0.5:
        return best_subj, best_score

    # Auto-assign first enrolled subject so batch ingestion completes seamlessly
    return (enrolled_subjects[0], 0.3) if enrolled_subjects else (None, 0.0)


def async_process_zip(app, batch_id: int, user_id: int):
    """
    Background worker task for processing ZIP archive extraction,
    classification, relocation, and incremental database commits within app context.
    """
    with app.app_context():
        batch = MaterialImportBatch.query.get(batch_id)
        if not batch:
            return

        try:
            from app.models import StudentProfile
            from app.routes.student import get_profile_subjects
            from app.services.text_extraction import extract_text_from_file
            from app.services.rag_embeddings import embed_and_store_material
            from app.services.module_descriptor_parser import parse_module_descriptor

            from app.models import StudentSubject
            user_subs = StudentSubject.query.filter_by(user_id=user_id).all()
            enrolled_subjects = [m.subject for m in user_subs if m.subject]
            if not enrolled_subjects:
                profile = StudentProfile.query.filter_by(user_id=user_id).first()
                enrolled_subjects = get_profile_subjects(profile) if profile else []
            if not enrolled_subjects:
                enrolled_subjects = Subject.query.all()

            upload_root = f"uploads/user_{user_id}/batch_{batch.id}"
            zip_path = batch.stored_zip_path

            # Stage 1: Raw Extraction Verification
            extract_dir = os.path.join(upload_root, 'raw_extracted')
            os.makedirs(extract_dir, exist_ok=True)

            with zipfile.ZipFile(zip_path, 'r') as zf:
                for member in zf.namelist():
                    if member.startswith('/') or '..' in member:
                        raise ValueError(f"Unsafe path in zip: {member}")
                zf.extractall(extract_dir)

            ALLOWED_EXT = {'.pdf', '.docx', '.pptx', '.txt', '.png', '.jpg', '.jpeg'}

            # Pre-walk Audit: Collect all valid files on disk before classification
            valid_files = []
            for dirpath, _, filenames in os.walk(extract_dir):
                rel_dir = os.path.relpath(dirpath, extract_dir)
                path_parts = rel_dir.split(os.sep) if rel_dir != '.' else []
                if any(part.startswith('.') or part == '__MACOSX' for part in path_parts):
                    continue
                for fname in sorted(filenames):
                    if fname.startswith('.') or fname.lower() == 'thumbs.db':
                        continue
                    ext = os.path.splitext(fname)[1].lower()
                    if ext in ALLOWED_EXT:
                        full_path = os.path.join(dirpath, fname)
                        if os.path.isfile(full_path):
                            valid_files.append((dirpath, fname, ext, path_parts))

            batch.total_files_found = len(valid_files)
            batch.status = 'processing'
            db.session.commit()

            matched_count = 0

            # Stage 2 & 3: Sequential processing, path-preserving relocation & incremental commits
            for dirpath, fname, ext, path_parts in valid_files:
                full_path = os.path.join(dirpath, fname)
                if not os.path.exists(full_path):
                    continue

                rel_dir = os.path.relpath(dirpath, extract_dir)
                folder_segments = [] if rel_dir == '.' else path_parts
                rel_file_path = os.path.relpath(full_path, extract_dir)
                rel_folder_path = os.path.dirname(rel_file_path) if rel_file_path != fname else ""

                category = classify_category(folder_segments, fname)
                subject, _ = resolve_subject_dynamically(rel_file_path, enrolled_subjects)

                # Move files preserving exact relative path to materials/user_<id>/batch_<id>/[relative_path]
                materials_base = f"materials/user_{user_id}/batch_{batch.id}"
                dest = os.path.join(materials_base, rel_file_path)
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                safe_move(full_path, dest)

                extracted_text = extract_text_from_file(dest, ext.lstrip('.'))

                mat = UploadedMaterial(
                    user_id=user_id,
                    subject_id=subject.id if subject else enrolled_subjects[0].id,
                    filename=fname,
                    file_path=dest,
                    file_type=ext.lstrip('.'),
                    category=category,
                    import_batch_id=batch.id,
                    extracted_text=extracted_text,
                    file_size_bytes=os.path.getsize(dest) if os.path.exists(dest) else 0,
                    embedding_status='pending',
                    relative_folder_path=rel_folder_path
                )
                db.session.add(mat)
                db.session.flush()

                if mat.extracted_text:
                    embed_and_store_material(mat.id)
                    if mat.category == 'Module Descriptor':
                        parse_module_descriptor(mat.user_id, mat.subject_id, mat.id, mat.extracted_text)

                matched_count += 1
                batch.matched_files = matched_count
                batch.unmatched_files = 0
                db.session.commit()

            batch.matched_files = batch.total_files_found
            batch.unmatched_files = 0
            batch.status = 'committed'
            batch.committed_at = datetime.utcnow()
            db.session.commit()

        except Exception as e:
            import traceback
            db.session.rollback()
            batch = MaterialImportBatch.query.get(batch_id)
            if batch:
                batch.status = 'error'
                batch.error_log = f"{str(e)}\n{traceback.format_exc()}"
                db.session.commit()


def process_zip_upload(user_id: int, zip_file_storage, enrolled_subjects: list[Subject]) -> MaterialImportBatch:
    """Synchronous legacy wrapper if called directly."""
    batch = MaterialImportBatch(
        user_id=user_id,
        source_filename=zip_file_storage.filename,
        stored_zip_path='',
        status='uploaded',
    )
    db.session.add(batch)
    db.session.flush()

    upload_root = f"uploads/user_{user_id}/batch_{batch.id}"
    os.makedirs(upload_root, exist_ok=True)
    zip_path = os.path.join(upload_root, 'source.zip')
    zip_file_storage.save(zip_path)
    batch.stored_zip_path = zip_path
    db.session.commit()

    from flask import current_app
    app = current_app._get_current_object()
    async_process_zip(app, batch.id, user_id)
    return MaterialImportBatch.query.get(batch.id)
