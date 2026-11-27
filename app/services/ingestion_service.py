"""
app/services/ingestion_service.py

Phase 4H, 4I, 4J — Transactional Document Ingestion Service

Handles:
  1. File Upload Processing & Temporary Storage
  2. Extraction & Staging (Session + Items creation)
  3. Transactional Commit (APPEND mode & REPLACE / SYNC mode)
  4. Reactivation of previously detached ProgramSubject mappings
  5. Full rollback on error
  6. Soft-delete safety (Never hard-deletes global Subjects)

Design rules:
  - Fully transactional: db.session.rollback() on any error.
  - Require explicit admin decision for unresolved NEEDS_REVIEW items.
  - Soft-deactivates replaced ProgramSubject mappings in REPLACE mode.
  - Protects global Subject records.
"""

import os
import uuid
from datetime import datetime
from werkzeug.utils import secure_filename
from app import db
from app.models import ImportSession, ImportItem, Subject, ProgramSubject, CurriculumProgram
from app.utils.doc_extractor import extract_document
from app.utils.curriculum_detector import detect_curriculum, match_subjects, match_program

UPLOAD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "uploads", "syllabus"))
ALLOWED_EXTENSIONS = {'docx', 'pdf', 'pptx'}
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB


def ensure_upload_dir():
    os.makedirs(UPLOAD_DIR, exist_ok=True)


def process_upload(file_obj, admin_id: int) -> ImportSession:
    """
    Validates, saves temporary file, extracts content, detects structure,
    runs matching, and creates staging ImportSession + ImportItems.

    Does NOT modify actual curriculum tables.
    """
    ensure_upload_dir()
    original_name = secure_filename(file_obj.filename)
    ext = os.path.splitext(original_name)[1].lstrip('.').lower()

    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported file type .{ext}. Allowed formats: docx, pdf, pptx")

    # Generate unique stored filename to prevent collision and path traversal
    stored_name = f"{uuid.uuid4().hex}_{original_name}"
    stored_path = os.path.join(UPLOAD_DIR, stored_name)
    file_obj.save(stored_path)

    file_size = os.path.getsize(stored_path)
    if file_size > MAX_FILE_SIZE:
        os.remove(stored_path)
        raise ValueError(f"File size ({file_size / (1024*1024):.1f}MB) exceeds 20MB limit.")

    # 1. Extract document text
    extraction = extract_document(stored_path)
    if not extraction.get("extraction_ok"):
        warnings = "; ".join(extraction.get("warnings", ["Extraction failed"]))
        raise ValueError(f"Failed to extract document: {warnings}")

    # 2. Detect curriculum structure
    detection = detect_curriculum(extraction)

    # 3. Match against existing DB records
    existing_programs = CurriculumProgram.query.filter_by(is_active=True).all()
    prog_match = match_program(detection.get("detected_program"), existing_programs)

    existing_subjects = Subject.query.filter_by(is_active=True).all()
    matched_subjects = match_subjects(detection.get("subjects", []), existing_subjects)

    # 4. Create staging session
    session = ImportSession(
        admin_id=admin_id,
        status="extracted",
        source_file=original_name,
        stored_file=stored_name,
        doc_type=ext,
        file_size=file_size,
        detected_program=detection.get("detected_program"),
        detected_program_id=prog_match.get("matched_program_id"),
        ingestion_mode="append",
        notes="; ".join(extraction.get("warnings", [])),
    )
    db.session.add(session)
    db.session.flush()

    # 5. Create staging items
    for idx, ds in enumerate(matched_subjects, start=1):
        item = ImportItem(
            session_id=session.id,
            extracted_program=detection.get("detected_program"),
            extracted_semester=ds.extracted_semester or detection.get("detected_semester"),
            extracted_term=ds.extracted_term if hasattr(ds, 'extracted_term') else None,
            extracted_code=ds.extracted_code,
            extracted_name=ds.extracted_name,
            extracted_credits=ds.extracted_credits,
            match_confidence=ds.match_confidence,
            matched_subject_id=ds.matched_subject_id,
            action=ds.action,
            final_subject_id=ds.matched_subject_id if ds.action == "LINK_EXISTING" else None,
            final_semester=ds.extracted_semester or detection.get("detected_semester"),
            final_term=None,
            final_code=ds.extracted_code,
            final_name=ds.extracted_name,
            final_credits=ds.extracted_credits or 3,
            sort_order=idx,
            status="pending",
        )
        db.session.add(item)

    db.session.commit()
    return session


def commit_ingestion(session_id: int, admin_id: int, target_program_id: int, mode: str = "append") -> dict:
    """
    Executes transactional database ingestion for a previewed session.

    Modes:
      'append': Keep existing mappings, add new mappings, reactivate detached mappings if applicable.
      'replace': Soft-detach old mappings for target_program, create/reactivate new mappings.

    All changes occur within a single database transaction. On error, rolls back completely.
    """
    session = ImportSession.query.get_or_404(session_id)
    if session.status == "committed":
        raise ValueError("This ingestion session has already been committed.")

    program = CurriculumProgram.query.get_or_404(target_program_id)
    session.detected_program_id = program.id
    session.ingestion_mode = mode

    items = ImportItem.query.filter_by(session_id=session.id).order_by(ImportItem.sort_order).all()

    # Verify no unresolved MANDATORY NEEDS_REVIEW items remain (unless action is explicitly set to SKIP/CREATE_NEW/LINK_EXISTING)
    unresolved = [item for item in items if item.action == "NEEDS_REVIEW"]
    if unresolved:
        raise ValueError(f"Cannot commit: {len(unresolved)} items still marked as NEEDS_REVIEW. Resolve or SKIP them first.")

    stats = {
        "created_subjects": 0,
        "reused_subjects": 0,
        "created_mappings": 0,
        "reactivated_mappings": 0,
        "skipped_items": 0,
        "replaced_mappings": 0,
    }

    try:
        # REPLACE mode: Soft-detach existing program_subjects for this program
        if mode == "replace":
            now = datetime.utcnow()
            active_mappings = ProgramSubject.query.filter_by(program_id=program.id, is_active=True).all()
            for m in active_mappings:
                m.is_active = False
                m.deleted_at = now
                m.deleted_by = admin_id
                stats["replaced_mappings"] += 1

        for item in items:
            if item.action == "SKIP":
                item.status = "skipped"
                stats["skipped_items"] += 1
                continue

            target_subject_id = None

            if item.action == "LINK_EXISTING":
                subject_id = item.final_subject_id or item.matched_subject_id
                if not subject_id:
                    raise ValueError(f"Item '{item.final_name}' set to LINK_EXISTING but no subject was selected.")
                subj = Subject.query.get(subject_id)
                if not subj:
                    raise ValueError(f"Selected subject ID {subject_id} not found.")
                target_subject_id = subj.id
                stats["reused_subjects"] += 1

            elif item.action == "CREATE_NEW":
                # Create a new global subject
                new_subj = Subject(
                    name=item.final_name,
                    code=item.final_code or None,
                    level_of_study=program.level_name,
                    program=program.name,
                    semester=item.final_semester,
                    credit_hours=item.final_credits or 3,
                    difficulty_level=3,
                    country="Nepal",
                    is_active=True,
                )
                db.session.add(new_subj)
                db.session.flush()  # get new_subj.id
                target_subject_id = new_subj.id
                item.final_subject_id = new_subj.id
                stats["created_subjects"] += 1

            if not target_subject_id:
                continue

            # Create or Reactivate ProgramSubject mapping
            existing_mapping = ProgramSubject.query.filter_by(
                program_id=program.id,
                subject_id=target_subject_id
            ).first()

            if existing_mapping:
                if not existing_mapping.is_active:
                    existing_mapping.is_active = True
                    existing_mapping.deleted_at = None
                    existing_mapping.deleted_by = None
                    existing_mapping.semester = item.final_semester or existing_mapping.semester
                    existing_mapping.term = item.final_term or existing_mapping.term
                    existing_mapping.sort_order = item.sort_order
                    item.program_subject_id = existing_mapping.id
                    stats["reactivated_mappings"] += 1
                else:
                    # Update order/semester if changed
                    existing_mapping.semester = item.final_semester or existing_mapping.semester
                    existing_mapping.term = item.final_term or existing_mapping.term
                    item.program_subject_id = existing_mapping.id
            else:
                new_mapping = ProgramSubject(
                    program_id=program.id,
                    subject_id=target_subject_id,
                    semester=item.final_semester,
                    term=item.final_term,
                    sort_order=item.sort_order,
                    is_active=True,
                )
                db.session.add(new_mapping)
                db.session.flush()
                item.program_subject_id = new_mapping.id
                stats["created_mappings"] += 1

            item.status = "committed"

        session.status = "committed"
        session.committed_at = datetime.utcnow()
        db.session.commit()
        return stats

    except Exception as e:
        db.session.rollback()
        session.status = "failed"
        db.session.commit()
        raise RuntimeError(f"Ingestion failed and transaction was rolled back cleanly: {str(e)}")
