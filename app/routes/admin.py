from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, session, abort, current_app
from flask_login import login_required, current_user
from app import db
from app.models import (
    User, Prediction, StudyLog, StudentProfile, StudentSubject,
    EducationLevel, University, Faculty, CurriculumProgram, Subject, AdminActivityLog,
    ProgramSubject, ImportSession, ImportItem, AdminRegistrationRequest, SUPER_ADMIN_EMAIL
)
from app.utils.auth_decorators import (
    super_admin_required, admin_required, is_protected_primary_super_admin,
    is_super_admin, is_admin
)
from datetime import datetime, timedelta
import json

admin_bp = Blueprint("admin", __name__)

@admin_bp.before_request
@login_required
def require_admin():
    if not current_user.is_authenticated or not current_user.is_admin:
        return redirect(url_for('student.dashboard'))


def log_admin_action(action, entity_type=None, entity_id=None, detail=None):
    try:
        log = AdminActivityLog(
            admin_user_id=current_user.id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            detail=detail
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Error logging admin action: {e}")

@admin_bp.route("/dashboard")
def dashboard():
    from app.models import (
        User, Prediction, StudyLog, EducationLevel, University, Faculty,
        CurriculumProgram, Subject, Chapter, Topic, AssessmentQuestion,
        ImportSession, AdminActivityLog
    )
    total_students = User.query.filter_by(role='student').count()
    active_students = User.query.filter_by(role='student', is_active=True).count()
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    recent_students = User.query.filter(User.role == 'student', User.date_registered >= seven_days_ago).count()
    
    total_predictions = Prediction.query.count()
    total_study_hours = round(db.session.query(db.func.sum(StudyLog.duration_hours)).scalar() or 0.0, 1)

    # Curriculum metrics
    levels_count = EducationLevel.query.filter_by(is_active=True).count()
    universities_count = University.query.filter_by(is_active=True).count()
    faculties_count = Faculty.query.filter_by(is_active=True).count()
    programs_count = CurriculumProgram.query.filter_by(is_active=True).count()
    subjects_count = Subject.query.filter_by(is_active=True).count()
    chapters_count = Chapter.query.count()
    topics_count = Topic.query.count()

    # Content & Ingestion
    mcq_count = AssessmentQuestion.query.count()
    import_sessions_count = ImportSession.query.count()

    # System Health Telemetry Summary
    db_status = "ok"
    gemini_status = "configured" if current_app.config.get("GEMINI_API_KEY") else "unconfigured"
    ml_status = _check_ml_model().get("status", "missing")

    # Recent Audit Activity
    recent_activities = AdminActivityLog.query.order_by(AdminActivityLog.timestamp.desc()).limit(8).all()

    # Weekly Predictions Chart Data
    chart_labels = []
    chart_data = []
    for i in range(3, -1, -1):
        week_start = datetime.utcnow() - timedelta(days=7 * (i + 1))
        week_end = datetime.utcnow() - timedelta(days=7 * i)
        count = Prediction.query.filter(
            Prediction.date >= week_start,
            Prediction.date < week_end,
        ).count()
        chart_labels.append(f"Week {4 - i}")
        chart_data.append(count)
    
    return render_template(
        "admin/dashboard.html", 
        total_students=total_students,
        active_students=active_students,
        recent_students=recent_students,
        total_predictions=total_predictions,
        total_study_hours=total_study_hours,
        levels_count=levels_count,
        universities_count=universities_count,
        faculties_count=faculties_count,
        programs_count=programs_count,
        subjects_count=subjects_count,
        chapters_count=chapters_count,
        topics_count=topics_count,
        mcq_count=mcq_count,
        import_sessions_count=import_sessions_count,
        db_status=db_status,
        gemini_status=gemini_status,
        ml_status=ml_status,
        recent_activities=recent_activities,
        chart_labels=chart_labels,
        chart_data=chart_data
    )



# ── SECTION 1: CURRICULUM LEVELS CRUD ─────────────────────────────────────────

@admin_bp.route("/curriculum/levels")
def curriculum_levels():
    levels = EducationLevel.query.order_by(EducationLevel.sort_order.asc()).all()
    # Calculate student usage counts
    usage_counts = {}
    for lvl in levels:
        usage_counts[lvl.name] = StudentProfile.query.filter_by(study_level=lvl.name).count()
    return render_template("admin/curriculum/levels.html", levels=levels, usage_counts=usage_counts)

@admin_bp.route("/curriculum/levels/add", methods=["POST"])
def curriculum_levels_add():
    name = request.form.get("name", "").strip()
    country = request.form.get("country", "").strip()
    sort_order = int(request.form.get("sort_order", 0))
    if name and country:
        level = EducationLevel(name=name, country=country, sort_order=sort_order, is_active=True)
        db.session.add(level)
        db.session.commit()
        log_admin_action("add_education_level", "EducationLevel", level.id, f"Added level '{name}' for country '{country}'")
        flash(f"Education level '{name}' added successfully!", "success")
    else:
        flash("Name and Country are required fields.", "danger")
    return redirect(url_for("admin.curriculum_levels"))

@admin_bp.route("/curriculum/levels/<int:level_id>/edit", methods=["POST"])
def curriculum_levels_edit(level_id):
    level = EducationLevel.query.get_or_404(level_id)
    old_name = level.name
    level.name = request.form.get("name", "").strip()
    level.country = request.form.get("country", "").strip()
    level.sort_order = int(request.form.get("sort_order", 0))
    db.session.commit()
    log_admin_action("edit_education_level", "EducationLevel", level.id, f"Edited level '{old_name}' -> '{level.name}'")
    flash(f"Education level '{level.name}' updated successfully!", "success")
    return redirect(url_for("admin.curriculum_levels"))

@admin_bp.route("/curriculum/levels/<int:level_id>/toggle", methods=["POST"])
def curriculum_levels_toggle(level_id):
    level = EducationLevel.query.get_or_404(level_id)
    level.is_active = not level.is_active
    if not level.is_active:
        level.deleted_at = datetime.utcnow()
        level.deleted_by = current_user.id
    else:
        level.deleted_at = None
        level.deleted_by = None
    db.session.commit()
    action_str = "reactivated" if level.is_active else "archived"
    log_admin_action(f"{action_str}_education_level", "EducationLevel", level.id, f"Set is_active={level.is_active} for '{level.name}'")
    flash(f"Education level '{level.name}' {action_str}.", "success")
    return redirect(url_for("admin.curriculum_levels"))


# ── SECTION 1: UNIVERSITIES CRUD ──────────────────────────────────────────────

@admin_bp.route("/curriculum/universities")
def curriculum_universities():
    universities = University.query.order_by(University.sort_order.asc()).all()
    usage_counts = {}
    for uni in universities:
        # Check profiles starting with uni name (e.g. "Tribhuvan University (TU)")
        usage_counts[uni.name] = StudentProfile.query.filter(StudentProfile.university.like(f"{uni.name}%")).count()
    return render_template("admin/curriculum/universities.html", universities=universities, usage_counts=usage_counts)

@admin_bp.route("/curriculum/universities/add", methods=["POST"])
def curriculum_universities_add():
    name = request.form.get("name", "").strip()
    abbr = request.form.get("abbreviation", "").strip() or None
    country = request.form.get("country", "").strip()
    sort_order = int(request.form.get("sort_order", 0))
    if name and country:
        uni = University(name=name, abbreviation=abbr, country=country, sort_order=sort_order, is_active=True)
        db.session.add(uni)
        db.session.commit()
        log_admin_action("add_university", "University", uni.id, f"Added university '{name}' ({abbr or 'no abbr'})")
        flash(f"University '{name}' added successfully!", "success")
    else:
        flash("Name and Country are required.", "danger")
    return redirect(url_for("admin.curriculum_universities"))

@admin_bp.route("/curriculum/universities/<int:uni_id>/edit", methods=["POST"])
def curriculum_universities_edit(uni_id):
    uni = University.query.get_or_404(uni_id)
    old_name = uni.name
    uni.name = request.form.get("name", "").strip()
    uni.abbreviation = request.form.get("abbreviation", "").strip() or None
    uni.country = request.form.get("country", "").strip()
    uni.sort_order = int(request.form.get("sort_order", 0))
    db.session.commit()
    log_admin_action("edit_university", "University", uni.id, f"Edited university '{old_name}' -> '{uni.name}'")
    flash(f"University '{uni.name}' updated successfully!", "success")
    return redirect(url_for("admin.curriculum_universities"))

@admin_bp.route("/curriculum/universities/<int:uni_id>/toggle", methods=["POST"])
def curriculum_universities_toggle(uni_id):
    uni = University.query.get_or_404(uni_id)
    uni.is_active = not uni.is_active
    if not uni.is_active:
        uni.deleted_at = datetime.utcnow()
        uni.deleted_by = current_user.id
    else:
        uni.deleted_at = None
        uni.deleted_by = None
    db.session.commit()
    action_str = "reactivated" if uni.is_active else "archived"
    log_admin_action(f"{action_str}_university", "University", uni.id, f"Set is_active={uni.is_active} for '{uni.name}'")
    flash(f"University '{uni.name}' {action_str}.", "success")
    return redirect(url_for("admin.curriculum_universities"))


# ── SECTION 1: FACULTIES CRUD ─────────────────────────────────────────────────

@admin_bp.route("/curriculum/faculties")
def curriculum_faculties():
    faculties = Faculty.query.order_by(Faculty.sort_order.asc()).all()
    usage_counts = {}
    for fac in faculties:
        usage_counts[fac.name] = StudentProfile.query.filter_by(program=fac.name).count()
    return render_template("admin/curriculum/faculties.html", faculties=faculties, usage_counts=usage_counts)

@admin_bp.route("/curriculum/faculties/add", methods=["POST"])
def curriculum_faculties_add():
    name = request.form.get("name", "").strip()
    lvl = request.form.get("level_name", "").strip() or None
    sort_order = int(request.form.get("sort_order", 0))
    if name:
        fac = Faculty(name=name, level_name=lvl, country="Nepal", sort_order=sort_order, is_active=True)
        db.session.add(fac)
        db.session.commit()
        log_admin_action("add_faculty", "Faculty", fac.id, f"Added faculty '{name}' for level '{lvl or 'All'}'")
        flash(f"Faculty '{name}' added successfully!", "success")
    else:
        flash("Name is required.", "danger")
    return redirect(url_for("admin.curriculum_faculties"))

@admin_bp.route("/curriculum/faculties/<int:fac_id>/edit", methods=["POST"])
def curriculum_faculties_edit(fac_id):
    fac = Faculty.query.get_or_404(fac_id)
    old_name = fac.name
    fac.name = request.form.get("name", "").strip()
    fac.level_name = request.form.get("level_name", "").strip() or None
    fac.sort_order = int(request.form.get("sort_order", 0))
    db.session.commit()
    log_admin_action("edit_faculty", "Faculty", fac.id, f"Edited faculty '{old_name}' -> '{fac.name}'")
    flash(f"Faculty '{fac.name}' updated successfully!", "success")
    return redirect(url_for("admin.curriculum_faculties"))

@admin_bp.route("/curriculum/faculties/<int:fac_id>/toggle", methods=["POST"])
def curriculum_faculties_toggle(fac_id):
    fac = Faculty.query.get_or_404(fac_id)
    fac.is_active = not fac.is_active
    if not fac.is_active:
        fac.deleted_at = datetime.utcnow()
        fac.deleted_by = current_user.id
    else:
        fac.deleted_at = None
        fac.deleted_by = None
    db.session.commit()
    action_str = "reactivated" if fac.is_active else "archived"
    log_admin_action(f"{action_str}_faculty", "Faculty", fac.id, f"Set is_active={fac.is_active} for '{fac.name}'")
    flash(f"Faculty '{fac.name}' {action_str}.", "success")
    return redirect(url_for("admin.curriculum_faculties"))


# ── SECTION 1: PROGRAMS CRUD ──────────────────────────────────────────────────

@admin_bp.route("/curriculum/programs")
def curriculum_programs():
    import json
    programs = CurriculumProgram.query.order_by(CurriculumProgram.sort_order.asc()).all()
    for p in programs:
        p.parsed_duration_options = []
        if p.duration_options_json:
            try:
                p.parsed_duration_options = json.loads(p.duration_options_json)
            except Exception:
                p.parsed_duration_options = []
    usage_counts = {}
    for prog in programs:
        usage_counts[prog.name] = StudentProfile.query.filter_by(program=prog.name).count()
    return render_template("admin/curriculum/programs.html", programs=programs, usage_counts=usage_counts)

@admin_bp.route("/curriculum/programs/add", methods=["POST"])
def curriculum_programs_add():
    name = request.form.get("name", "").strip()
    lvl = request.form.get("level_name", "").strip()
    has_duration = bool(request.form.get("has_duration"))
    sort_order = int(request.form.get("sort_order", 0))
    if name and lvl:
        dur_json = None
        if has_duration:
            dur_vals = request.form.getlist("duration_values[]")
            dur_lbls = request.form.getlist("duration_labels[]")
            options = []
            for val, lbl in zip(dur_vals, dur_lbls):
                if val.strip():
                    options.append({"value": val.strip(), "label": lbl.strip() or val.strip()})
            if options:
                dur_json = json.dumps(options)
            else:
                # Seed default duration choices for Bachelors duration-variable programs
                dur_json = json.dumps([
                    {"value": "3 Years", "label": "3 Years (International-affiliated, e.g. APU/LBEF)"},
                    {"value": "4 Years", "label": "4 Years (TU-affiliated BSc CSIT)"}
                ])
        prog = CurriculumProgram(
            name=name, level_name=lvl, country="Nepal",
            has_duration=has_duration, duration_options_json=dur_json,
            sort_order=sort_order, is_active=True
        )
        db.session.add(prog)
        db.session.commit()
        log_admin_action("add_program", "CurriculumProgram", prog.id, f"Added program '{name}' under '{lvl}'")
        flash(f"Program '{name}' added successfully!", "success")
    else:
        flash("Name and Level Name are required.", "danger")
    return redirect(url_for("admin.curriculum_programs"))

@admin_bp.route("/curriculum/programs/<int:prog_id>/edit", methods=["POST"])
def curriculum_programs_edit(prog_id):
    prog = CurriculumProgram.query.get_or_404(prog_id)
    old_name = prog.name
    prog.name = request.form.get("name", "").strip()
    prog.level_name = request.form.get("level_name", "").strip()
    prog.has_duration = bool(request.form.get("has_duration"))
    prog.sort_order = int(request.form.get("sort_order", 0))
    if prog.has_duration:
        dur_vals = request.form.getlist("duration_values[]")
        dur_lbls = request.form.getlist("duration_labels[]")
        options = []
        for val, lbl in zip(dur_vals, dur_lbls):
            if val.strip():
                options.append({"value": val.strip(), "label": lbl.strip() or val.strip()})
        if options:
            prog.duration_options_json = json.dumps(options)
        elif not prog.duration_options_json:
            prog.duration_options_json = json.dumps([
                {"value": "3 Years", "label": "3 Years (International-affiliated, e.g. APU/LBEF)"},
                {"value": "4 Years", "label": "4 Years (TU-affiliated BSc CSIT)"}
            ])
    else:
        prog.duration_options_json = None
    db.session.commit()
    log_admin_action("edit_program", "CurriculumProgram", prog.id, f"Edited program '{old_name}' -> '{prog.name}'")
    flash(f"Program '{prog.name}' updated successfully!", "success")
    return redirect(url_for("admin.curriculum_programs"))

@admin_bp.route("/curriculum/programs/<int:prog_id>/toggle", methods=["POST"])
def curriculum_programs_toggle(prog_id):
    prog = CurriculumProgram.query.get_or_404(prog_id)
    prog.is_active = not prog.is_active
    if not prog.is_active:
        prog.deleted_at = datetime.utcnow()
        prog.deleted_by = current_user.id
        # Soft-deactivate this program's ProgramSubject mappings ONLY
        # Global Subject records are NOT touched
        ProgramSubject.query.filter_by(program_id=prog.id, is_active=True).update(
            {"is_active": False, "deleted_at": datetime.utcnow(), "deleted_by": current_user.id}
        )
    else:
        prog.deleted_at = None
        prog.deleted_by = None
        # Reactivate this program's ProgramSubject mappings
        ProgramSubject.query.filter_by(program_id=prog.id, is_active=False).update(
            {"is_active": True, "deleted_at": None, "deleted_by": None}
        )
    db.session.commit()
    action_str = "reactivated" if prog.is_active else "archived"
    log_admin_action(f"{action_str}_program", "CurriculumProgram", prog.id, f"Set is_active={prog.is_active} for '{prog.name}'")
    flash(f"Program '{prog.name}' {action_str}. Shared global subjects were NOT affected.", "success")
    return redirect(url_for("admin.curriculum_programs"))


# ── PROGRAM DETAIL — Subject Management ────────────────────────────────────────

@admin_bp.route("/curriculum/programs/<int:prog_id>")
def curriculum_program_detail(prog_id):
    """Program detail page showing all mapped subjects grouped by semester."""
    prog = CurriculumProgram.query.get_or_404(prog_id)
    # Load active mappings, ordered by semester then sort_order
    mappings = (
        ProgramSubject.query
        .filter_by(program_id=prog.id, is_active=True)
        .join(Subject, ProgramSubject.subject_id == Subject.id)
        .order_by(ProgramSubject.semester, ProgramSubject.sort_order, Subject.name)
        .all()
    )
    # Group by semester
    from collections import defaultdict
    by_semester = defaultdict(list)
    for m in mappings:
        key = m.semester or "Unassigned"
        by_semester[key].append(m)
    # Sorted semester keys (Semester 1 < Semester 2 < ... < Core < Unassigned)
    def sem_sort_key(s):
        if s.startswith("Semester "):
            try: return (0, int(s.split()[1]))
            except: pass
        return (1, s)
    semesters_ordered = sorted(by_semester.keys(), key=sem_sort_key)

    # All active global subjects for the Attach modal
    all_subjects = Subject.query.filter_by(is_active=True).order_by(Subject.name).all()
    # Exclude already-attached subject IDs
    attached_ids = {m.subject_id for m in mappings}
    available_subjects = [s for s in all_subjects if s.id not in attached_ids]

    # All programs for Copy-from dropdown
    other_programs = CurriculumProgram.query.filter(
        CurriculumProgram.id != prog.id, CurriculumProgram.is_active == True
    ).order_by(CurriculumProgram.name).all()

    usage_count = StudentProfile.query.filter_by(program=prog.name).count()

    return render_template(
        "admin/curriculum/program_detail.html",
        prog=prog,
        by_semester=by_semester,
        semesters_ordered=semesters_ordered,
        available_subjects=available_subjects,
        other_programs=other_programs,
        usage_count=usage_count,
        total_subjects=len(mappings),
    )


@admin_bp.route("/curriculum/programs/<int:prog_id>/subjects/attach", methods=["POST"])
def curriculum_program_attach_subject(prog_id):
    """Attach an existing global Subject to this program."""
    prog = CurriculumProgram.query.get_or_404(prog_id)
    subject_id = request.form.get("subject_id", type=int)
    semester = request.form.get("semester", "").strip() or None
    term = request.form.get("term", "").strip() or None

    if not subject_id:
        flash("Please select a subject to attach.", "warning")
        return redirect(url_for("admin.curriculum_program_detail", prog_id=prog_id))

    subject = Subject.query.get_or_404(subject_id)

    # Check for existing active mapping
    existing = ProgramSubject.query.filter_by(program_id=prog.id, subject_id=subject_id).first()
    if existing:
        if existing.is_active:
            flash(f"'{subject.name}' is already attached to this program.", "warning")
        else:
            # Reactivate it
            existing.is_active = True
            existing.deleted_at = None
            existing.deleted_by = None
            existing.semester = semester or existing.semester
            db.session.commit()
            log_admin_action("reattach_subject", "ProgramSubject", existing.id,
                             f"Reattached '{subject.name}' to program '{prog.name}'")
            flash(f"'{subject.name}' reattached to program '{prog.name}'.", "success")
        return redirect(url_for("admin.curriculum_program_detail", prog_id=prog_id))

    # Get max sort_order for this semester in this program
    max_order = db.session.query(db.func.max(ProgramSubject.sort_order)).filter_by(
        program_id=prog.id, semester=semester
    ).scalar() or 0

    mapping = ProgramSubject(
        program_id=prog.id,
        subject_id=subject_id,
        semester=semester,
        term=term,
        sort_order=max_order + 1,
        is_active=True
    )
    db.session.add(mapping)
    db.session.commit()
    log_admin_action("attach_subject", "ProgramSubject", mapping.id,
                     f"Attached '{subject.name}' to program '{prog.name}' (semester={semester})")
    flash(f"'{subject.name}' attached to program '{prog.name}'.", "success")
    return redirect(url_for("admin.curriculum_program_detail", prog_id=prog_id))


@admin_bp.route("/curriculum/programs/<int:prog_id>/subjects/create", methods=["POST"])
def curriculum_program_create_subject(prog_id):
    """Create a new global Subject and immediately attach it to this program."""
    prog = CurriculumProgram.query.get_or_404(prog_id)
    name = request.form.get("name", "").strip()
    code = request.form.get("code", "").strip() or None
    credit_hours = int(request.form.get("credit_hours", 3))
    difficulty = int(request.form.get("difficulty_level", 3))
    semester = request.form.get("semester", "").strip() or None
    term = request.form.get("term", "").strip() or None

    if not name:
        flash("Subject name is required.", "danger")
        return redirect(url_for("admin.curriculum_program_detail", prog_id=prog_id))

    # Check for duplicate code
    if code and Subject.query.filter_by(code=code).first():
        flash(f"Subject code '{code}' already exists. Use a different code.", "danger")
        return redirect(url_for("admin.curriculum_program_detail", prog_id=prog_id))

    subj = Subject(
        name=name, code=code,
        level_of_study=prog.level_name,
        program=prog.name,
        semester=semester,
        credit_hours=credit_hours,
        difficulty_level=difficulty,
        country="Nepal",
        curriculum="LBEF (APU)" if "APU" in prog.name or "LBEF" in prog.name else "National",
        is_active=True
    )
    db.session.add(subj)
    db.session.flush()  # get subj.id

    max_order = db.session.query(db.func.max(ProgramSubject.sort_order)).filter_by(
        program_id=prog.id, semester=semester
    ).scalar() or 0

    mapping = ProgramSubject(
        program_id=prog.id, subject_id=subj.id,
        semester=semester, term=term,
        sort_order=max_order + 1, is_active=True
    )
    db.session.add(mapping)
    db.session.commit()
    log_admin_action("create_attach_subject", "Subject", subj.id,
                     f"Created and attached '{name}' ({code}) to program '{prog.name}'")
    flash(f"Subject '{name}' created and attached to '{prog.name}'.", "success")
    return redirect(url_for("admin.curriculum_program_detail", prog_id=prog_id))


@admin_bp.route("/curriculum/programs/<int:prog_id>/subjects/<int:ps_id>/detach", methods=["POST"])
def curriculum_program_detach_subject(prog_id, ps_id):
    """
    Detach a subject from this program.

    IMPORTANT: Only the ProgramSubject mapping is soft-deleted.
    The global Subject record is NEVER deleted here.
    Other programs that use the same Subject are completely unaffected.
    """
    prog = CurriculumProgram.query.get_or_404(prog_id)
    mapping = ProgramSubject.query.filter_by(id=ps_id, program_id=prog.id).first_or_404()
    subj_name = mapping.subject.name if mapping.subject else f"ID={mapping.subject_id}"

    mapping.is_active = False
    mapping.deleted_at = datetime.utcnow()
    mapping.deleted_by = current_user.id
    db.session.commit()
    log_admin_action("detach_subject", "ProgramSubject", ps_id,
                     f"Detached '{subj_name}' from program '{prog.name}' (global Subject preserved)")
    flash(f"'{subj_name}' detached from '{prog.name}'. The global subject record is preserved.", "success")
    return redirect(url_for("admin.curriculum_program_detail", prog_id=prog_id))


@admin_bp.route("/curriculum/programs/<int:prog_id>/subjects/<int:ps_id>/edit", methods=["POST"])
def curriculum_program_edit_mapping(prog_id, ps_id):
    """Edit the semester/term/sort_order of a ProgramSubject mapping."""
    prog = CurriculumProgram.query.get_or_404(prog_id)
    mapping = ProgramSubject.query.filter_by(id=ps_id, program_id=prog.id).first_or_404()
    mapping.semester = request.form.get("semester", "").strip() or mapping.semester
    mapping.term = request.form.get("term", "").strip() or mapping.term
    sort_val = request.form.get("sort_order", type=int)
    if sort_val is not None:
        mapping.sort_order = sort_val
    db.session.commit()
    log_admin_action("edit_mapping", "ProgramSubject", ps_id,
                     f"Updated mapping for subject_id={mapping.subject_id} in program '{prog.name}'")
    flash("Subject mapping updated.", "success")
    return redirect(url_for("admin.curriculum_program_detail", prog_id=prog_id))


@admin_bp.route("/curriculum/programs/<int:prog_id>/subjects/reorder", methods=["POST"])
def curriculum_program_reorder(prog_id):
    """AJAX endpoint: receive ordered list of ProgramSubject IDs and update sort_order."""
    prog = CurriculumProgram.query.get_or_404(prog_id)
    data = request.get_json(silent=True) or {}
    ordered_ids = data.get("ordered_ids", [])  # list of ps_id in display order
    for i, ps_id in enumerate(ordered_ids, start=1):
        ProgramSubject.query.filter_by(id=int(ps_id), program_id=prog.id).update({"sort_order": i})
    db.session.commit()
    return jsonify({"status": "ok", "updated": len(ordered_ids)})


@admin_bp.route("/curriculum/programs/<int:prog_id>/subjects/bulk-attach", methods=["POST"])
def curriculum_program_bulk_attach(prog_id):
    """Attach multiple existing subjects to this program at once."""
    prog = CurriculumProgram.query.get_or_404(prog_id)
    subject_ids = request.form.getlist("subject_ids", type=int)
    semester = request.form.get("semester", "").strip() or None
    attached = 0
    skipped = 0
    for sid in subject_ids:
        existing = ProgramSubject.query.filter_by(program_id=prog.id, subject_id=sid).first()
        if existing:
            if not existing.is_active:
                existing.is_active = True
                existing.deleted_at = None
                existing.deleted_by = None
                attached += 1
            else:
                skipped += 1
            continue
        max_order = db.session.query(db.func.max(ProgramSubject.sort_order)).filter_by(
            program_id=prog.id, semester=semester
        ).scalar() or 0
        db.session.add(ProgramSubject(
            program_id=prog.id, subject_id=sid,
            semester=semester, sort_order=max_order + 1, is_active=True
        ))
        attached += 1
    db.session.commit()
    log_admin_action("bulk_attach_subjects", "CurriculumProgram", prog.id,
                     f"Bulk attached {attached} subjects, skipped {skipped} duplicates")
    flash(f"Attached {attached} subjects. {skipped} already present.", "success")
    return redirect(url_for("admin.curriculum_program_detail", prog_id=prog_id))


@admin_bp.route("/curriculum/programs/<int:prog_id>/subjects/bulk-detach", methods=["POST"])
def curriculum_program_bulk_detach(prog_id):
    """Soft-detach multiple ProgramSubject mappings at once."""
    prog = CurriculumProgram.query.get_or_404(prog_id)
    ps_ids = request.form.getlist("ps_ids", type=int)
    now = datetime.utcnow()
    detached = 0
    for ps_id in ps_ids:
        mapping = ProgramSubject.query.filter_by(id=ps_id, program_id=prog.id, is_active=True).first()
        if mapping:
            mapping.is_active = False
            mapping.deleted_at = now
            mapping.deleted_by = current_user.id
            detached += 1
    db.session.commit()
    log_admin_action("bulk_detach_subjects", "CurriculumProgram", prog.id,
                     f"Bulk detached {detached} subject mappings (global subjects preserved)")
    flash(f"{detached} subjects detached. Global subject records are preserved.", "success")
    return redirect(url_for("admin.curriculum_program_detail", prog_id=prog_id))


@admin_bp.route("/curriculum/programs/<int:prog_id>/subjects/copy-preview", methods=["POST"])
def curriculum_program_copy_preview(prog_id):
    """Show a preview of subjects to copy from a source program."""
    prog = CurriculumProgram.query.get_or_404(prog_id)
    source_id = request.form.get("source_program_id", type=int)
    if not source_id:
        flash("Please select a source program.", "warning")
        return redirect(url_for("admin.curriculum_program_detail", prog_id=prog_id))

    source_prog = CurriculumProgram.query.get_or_404(source_id)
    source_mappings = ProgramSubject.query.filter_by(program_id=source_id, is_active=True).all()
    existing_subject_ids = {
        m.subject_id for m in ProgramSubject.query.filter_by(program_id=prog.id, is_active=True).all()
    }

    new_mappings = [m for m in source_mappings if m.subject_id not in existing_subject_ids]
    existing_mappings = [m for m in source_mappings if m.subject_id in existing_subject_ids]

    return render_template(
        "admin/curriculum/copy_preview.html",
        prog=prog,
        source_prog=source_prog,
        new_mappings=new_mappings,
        existing_mappings=existing_mappings,
    )


@admin_bp.route("/curriculum/programs/<int:prog_id>/subjects/copy-confirm", methods=["POST"])
def curriculum_program_copy_confirm(prog_id):
    """Commit copying selected subject mappings from source program."""
    prog = CurriculumProgram.query.get_or_404(prog_id)
    source_id = request.form.get("source_program_id", type=int)
    conflict_mode = request.form.get("conflict_mode", "skip")  # skip | replace

    if not source_id:
        flash("Invalid source program.", "danger")
        return redirect(url_for("admin.curriculum_program_detail", prog_id=prog_id))

    source_mappings = ProgramSubject.query.filter_by(program_id=source_id, is_active=True).all()
    created = 0
    skipped = 0
    replaced = 0

    for sm in source_mappings:
        existing = ProgramSubject.query.filter_by(
            program_id=prog.id, subject_id=sm.subject_id
        ).first()
        if existing:
            if conflict_mode == "replace":
                existing.semester = sm.semester
                existing.term = sm.term
                existing.sort_order = sm.sort_order
                existing.is_active = True
                existing.deleted_at = None
                existing.deleted_by = None
                replaced += 1
            else:
                skipped += 1
            continue

        db.session.add(ProgramSubject(
            program_id=prog.id,
            subject_id=sm.subject_id,
            semester=sm.semester,
            term=sm.term,
            sort_order=sm.sort_order,
            is_active=True
        ))
        created += 1

    db.session.commit()
    source_prog = CurriculumProgram.query.get(source_id)
    log_admin_action("copy_subjects", "CurriculumProgram", prog.id,
                     f"Copied {created} new mappings from '{source_prog.name}'; skipped={skipped}, replaced={replaced}")
    flash(f"Copied {created} subjects from '{source_prog.name}'. {skipped} skipped, {replaced} replaced.", "success")
    return redirect(url_for("admin.curriculum_program_detail", prog_id=prog_id))


# ── HARD-DELETE SAFETY HELPER ──────────────────────────────────────────────────

def _count_subject_references(subject_id):
    """Returns total number of references to a subject across all dependent tables."""
    from app.models import (
        StudentSubject, StudentAssessment, AssessmentQuestion,
        Chapter, ChapterQuizScore, ChapterQuizResult, TopicSeenQuestion, StudentSeenQuestion
    )
    ref_checks = [
        StudentSubject.query.filter_by(subject_id=subject_id).count(),
        AssessmentQuestion.query.filter_by(subject_id=subject_id).count(),
        Chapter.query.filter_by(subject_id=subject_id).count(),
        ProgramSubject.query.filter_by(subject_id=subject_id).count(),
    ]
    return sum(ref_checks)


@admin_bp.route("/curriculum/subjects/<int:subject_id>/hard-delete", methods=["POST"])
def curriculum_subjects_hard_delete(subject_id):
    """Permanently delete a subject — only allowed if zero historical references exist."""
    subj = Subject.query.get_or_404(subject_id)
    confirmed = request.form.get("confirm") == "PERMANENTLY DELETE"
    if not confirmed:
        flash("Hard delete requires typing 'PERMANENTLY DELETE' to confirm.", "danger")
        return redirect(url_for("admin.curriculum_subjects"))

    ref_count = _count_subject_references(subj.id)
    if ref_count > 0:
        flash(
            f"Cannot permanently delete '{subj.name}': {ref_count} dependent records exist "
            f"(student subjects, questions, chapters, or program mappings). "
            f"Deactivate or archive it instead.",
            "danger"
        )
        return redirect(url_for("admin.curriculum_subjects"))

    subj_name = subj.name
    db.session.delete(subj)
    db.session.commit()
    log_admin_action("hard_delete_subject", "Subject", subject_id,
                     f"Permanently deleted subject '{subj_name}' (no references found)")
    flash(f"Subject '{subj_name}' permanently deleted.", "success")
    return redirect(url_for("admin.curriculum_subjects"))


# ── PHASE 4: DOCUMENT INGESTION ROUTES ──────────────────────────────────────────

@admin_bp.route("/curriculum/import")
def curriculum_import():
    """Import Syllabus main upload page & session history."""
    sessions = ImportSession.query.order_by(ImportSession.created_at.desc()).all()
    return render_template("admin/curriculum/import.html", sessions=sessions)


@admin_bp.route("/curriculum/import/upload", methods=["POST"])
def curriculum_import_upload():
    """Handles syllabus file upload, extraction, and staging session creation."""
    if "syllabus_file" not in request.files:
        flash("No file was uploaded.", "danger")
        return redirect(url_for("admin.curriculum_import"))

    file_obj = request.files["syllabus_file"]
    if not file_obj or file_obj.filename == "":
        flash("Please select a file to upload.", "warning")
        return redirect(url_for("admin.curriculum_import"))

    from app.services.ingestion_service import process_upload
    try:
        session_obj = process_upload(file_obj, current_user.id)
        log_admin_action("upload_syllabus", "ImportSession", session_obj.id, f"Uploaded '{session_obj.source_file}' ({session_obj.file_size} bytes)")
        flash(f"Document '{session_obj.source_file}' extracted successfully! Review and confirm mappings below.", "success")
        return redirect(url_for("admin.curriculum_import_preview", session_id=session_obj.id))
    except Exception as e:
        flash(f"Upload failed: {str(e)}", "danger")
        return redirect(url_for("admin.curriculum_import"))


@admin_bp.route("/curriculum/import/<int:session_id>")
def curriculum_import_preview(session_id):
    """Preview extracted syllabus items and match settings."""
    import_session = ImportSession.query.get_or_404(session_id)
    items = ImportItem.query.filter_by(session_id=import_session.id).order_by(ImportItem.sort_order).all()
    all_programs = CurriculumProgram.query.filter_by(is_active=True).order_by(CurriculumProgram.name).all()
    all_subjects = Subject.query.filter_by(is_active=True).order_by(Subject.name).all()

    return render_template(
        "admin/curriculum/import_preview.html",
        import_session=import_session,
        items=items,
        all_programs=all_programs,
        all_subjects=all_subjects
    )


@admin_bp.route("/curriculum/import/<int:session_id>/commit", methods=["POST"])
def curriculum_import_commit(session_id):
    """Applies admin choices from preview and executes transactional ingestion."""
    import_session = ImportSession.query.get_or_404(session_id)
    target_program_id = request.form.get("target_program_id", type=int)
    ingestion_mode = request.form.get("ingestion_mode", "append")

    if not target_program_id:
        flash("Please select a target Curriculum Program.", "danger")
        return redirect(url_for("admin.curriculum_import_preview", session_id=session_id))

    items = ImportItem.query.filter_by(session_id=import_session.id).all()

    # Update item user decisions from form
    for item in items:
        action_val = request.form.get(f"action_{item.id}", item.action)
        sem_val = request.form.get(f"semester_{item.id}", item.final_semester)
        code_val = request.form.get(f"code_{item.id}", item.final_code)
        name_val = request.form.get(f"name_{item.id}", item.final_name)
        credits_val = request.form.get(f"credits_{item.id}", type=int) or item.final_credits
        subj_id_val = request.form.get(f"matched_subject_id_{item.id}", type=int)

        item.action = action_val
        item.final_semester = sem_val or None
        item.final_code = code_val or None
        item.final_name = name_val
        item.final_credits = credits_val
        if subj_id_val:
            item.final_subject_id = subj_id_val

    db.session.commit()

    from app.services.ingestion_service import commit_ingestion
    try:
        stats = commit_ingestion(session_id, current_user.id, target_program_id, mode=ingestion_mode)
        log_admin_action("commit_ingestion", "ImportSession", session_id, f"Committed session in mode '{ingestion_mode}' for program_id={target_program_id}: {stats}")
        flash(
            f"Ingestion committed successfully! Mode: {ingestion_mode.upper()} &bull; "
            f"Created Subjects: {stats['created_subjects']}, Reused Subjects: {stats['reused_subjects']}, "
            f"Created Mappings: {stats['created_mappings']}, Reactivated: {stats['reactivated_mappings']}, "
            f"Skipped: {stats['skipped_items']}.",
            "success"
        )
        return redirect(url_for("admin.curriculum_program_detail", prog_id=target_program_id))
    except Exception as e:
        flash(str(e), "danger")
        return redirect(url_for("admin.curriculum_import_preview", session_id=session_id))


@admin_bp.route("/curriculum/import/<int:session_id>/cancel", methods=["POST"])
def curriculum_import_cancel(session_id):
    """Cancels an uncommitted import session."""
    import_session = ImportSession.query.get_or_404(session_id)
    if import_session.status != "committed":
        import_session.status = "cancelled"
        db.session.commit()
        log_admin_action("cancel_ingestion", "ImportSession", session_id, "Cancelled import session.")
        flash("Import session cancelled.", "info")
    return redirect(url_for("admin.curriculum_import"))


# ── PHASE 4K: UNMAPPED SUBJECTS FILTER & ATTACH ────────────────────────────────

@admin_bp.route("/curriculum/unmapped-subjects")
def unmapped_subjects():
    """Lists global subjects that have no active ProgramSubject mapping."""
    mapped_subject_ids = db.session.query(ProgramSubject.subject_id).filter_by(is_active=True)
    unmapped = Subject.query.filter(Subject.is_active == True, ~Subject.id.in_(mapped_subject_ids)).order_by(Subject.name).all()
    all_programs = CurriculumProgram.query.filter_by(is_active=True).order_by(CurriculumProgram.name).all()

    return render_template(
        "admin/curriculum/unmapped_subjects.html",
        unmapped_subjects=unmapped,
        all_programs=all_programs
    )



@admin_bp.route("/curriculum/unmapped-subjects/<int:subject_id>/attach", methods=["POST"])
def unmapped_subjects_attach(subject_id):
    """Attaches an unmapped global subject to a selected program."""
    subj = Subject.query.get_or_404(subject_id)
    program_id = request.form.get("program_id", type=int)
    semester = request.form.get("semester", "").strip() or None

    if not program_id:
        flash("Please select a target program.", "warning")
        return redirect(url_for("admin.unmapped_subjects"))

    prog = CurriculumProgram.query.get_or_404(program_id)

    max_order = db.session.query(db.func.max(ProgramSubject.sort_order)).filter_by(
        program_id=prog.id, semester=semester
    ).scalar() or 0

    mapping = ProgramSubject(
        program_id=prog.id,
        subject_id=subj.id,
        semester=semester,
        sort_order=max_order + 1,
        is_active=True
    )
    db.session.add(mapping)
    db.session.commit()
    log_admin_action("attach_unmapped_subject", "ProgramSubject", mapping.id, f"Attached unmapped subject '{subj.name}' to program '{prog.name}'")
    flash(f"Attached '{subj.name}' to program '{prog.name}'.", "success")
    return redirect(url_for("admin.unmapped_subjects"))




# ── SECTION 1: SUBJECTS CRUD ──────────────────────────────────────────────────

@admin_bp.route("/curriculum/subjects")
def curriculum_subjects():
    selected_level = request.args.get("level", "").strip()
    levels = EducationLevel.query.filter_by(is_active=True).order_by(EducationLevel.sort_order.asc()).all()
    
    query = Subject.query
    if selected_level:
        query = query.filter_by(level_of_study=selected_level)
    subjects = query.order_by(Subject.level_of_study.asc(), Subject.name.asc()).all()
    
    usage_counts = {}
    for s in subjects:
        usage_counts[s.id] = StudentSubject.query.filter_by(subject_id=s.id).count()
        
    return render_template(
        "admin/curriculum/subjects.html",
        subjects=subjects,
        levels=levels,
        selected_level=selected_level,
        usage_counts=usage_counts
    )

@admin_bp.route("/curriculum/subjects/add", methods=["POST"])
def curriculum_subjects_add():
    lvl_filter = request.form.get("level_filter", "").strip()
    name = request.form.get("name", "").strip()
    code = request.form.get("code", "").strip() or None
    lvl = request.form.get("level_of_study", "").strip()
    program = request.form.get("program", "").strip() or None
    semester = request.form.get("semester", "").strip() or None
    credit_hours = int(request.form.get("credit_hours", 3))
    difficulty = int(request.form.get("difficulty_level", 3))
    
    if name and lvl:
        subj = Subject(
            name=name, code=code, level_of_study=lvl,
            program=program, semester=semester,
            credit_hours=credit_hours, difficulty_level=difficulty,
            country="Nepal", curriculum="NEB/CTEVT" if lvl in ("Class 11", "Class 12") else "National",
            is_active=True
        )
        db.session.add(subj)
        db.session.commit()
        log_admin_action("add_subject", "Subject", subj.id, f"Added subject '{name}' ({code or 'no code'}) under '{lvl}'")
        flash(f"Subject '{name}' added successfully!", "success")
    else:
        flash("Subject Name and Level are required.", "danger")
        
    return redirect(url_for("admin.curriculum_subjects", level=lvl_filter))

@admin_bp.route("/curriculum/subjects/<int:subject_id>/edit", methods=["POST"])
def curriculum_subjects_edit(subject_id):
    subj = Subject.query.get_or_404(subject_id)
    lvl_filter = request.form.get("level_filter", "").strip()
    old_name = subj.name
    
    subj.name = request.form.get("name", "").strip()
    subj.code = request.form.get("code", "").strip() or None
    subj.level_of_study = request.form.get("level_of_study", "").strip()
    subj.program = request.form.get("program", "").strip() or None
    subj.semester = request.form.get("semester", "").strip() or None
    subj.credit_hours = int(request.form.get("credit_hours", 3))
    subj.difficulty_level = int(request.form.get("difficulty_level", 3))
    
    db.session.commit()
    log_admin_action("edit_subject", "Subject", subj.id, f"Edited subject '{old_name}' -> '{subj.name}'")
    flash(f"Subject '{subj.name}' updated successfully!", "success")
    return redirect(url_for("admin.curriculum_subjects", level=lvl_filter))

@admin_bp.route("/curriculum/subjects/<int:subject_id>/toggle", methods=["POST"])
def curriculum_subjects_toggle(subject_id):
    subj = Subject.query.get_or_404(subject_id)
    lvl_filter = request.form.get("level_filter", "").strip()
    subj.is_active = not subj.is_active
    db.session.commit()
    action_str = "activated" if subj.is_active else "deactivated"
    log_admin_action(f"{action_str}_subject", "Subject", subj.id, f"Set is_active={subj.is_active} for '{subj.name}'")
    flash(f"Subject '{subj.name}' {action_str} successfully!", "success")
    return redirect(url_for("admin.curriculum_subjects", level=lvl_filter))



# ── SECTION 3: STUDENT MANAGEMENT ─────────────────────────────────────────────

from math import ceil

@admin_bp.route("/students")
def students():
    from app.models import StudyPlan, StudentAssessment, EducationLevel, University, CurriculumProgram
    page = request.args.get("page", 1, type=int)
    per_page = 20
    search_q = request.args.get("q", "").strip()
    selected_level = request.args.get("level", "").strip()
    selected_university = request.args.get("university", "").strip()
    selected_program = request.args.get("program", "").strip()
    selected_status = request.args.get("status", "").strip()

    levels = EducationLevel.query.filter_by(is_active=True).order_by(EducationLevel.sort_order).all()
    universities = University.query.filter_by(is_active=True).order_by(University.sort_order).all()
    programs = CurriculumProgram.query.filter_by(is_active=True).order_by(CurriculumProgram.sort_order).all()

    query = User.query.filter_by(role="student")
    if search_q:
        from sqlalchemy import or_
        query = query.filter(or_(
            User.full_name.ilike(f"%{search_q}%"),
            User.email.ilike(f"%{search_q}%")
        ))
    if selected_status == "active":
        query = query.filter_by(is_active=True)
    elif selected_status == "inactive" or selected_status == "suspended":
        query = query.filter_by(is_active=False)

    if selected_level or selected_university or selected_program:
        query = query.join(StudentProfile, User.id == StudentProfile.user_id)
        if selected_level:
            query = query.filter(StudentProfile.study_level == selected_level)
        if selected_university:
            query = query.filter(StudentProfile.university == selected_university)
        if selected_program:
            query = query.filter(StudentProfile.program == selected_program)

    total = query.count()
    pages = ceil(total / per_page) if total else 1
    users = query.order_by(User.date_registered.desc()).offset((page - 1) * per_page).limit(per_page).all()

    rows = []
    for u in users:
        prof = u.profile
        profile_complete = bool(prof and prof.country and prof.study_level)
        assessed = bool(prof and prof.has_completed_assessment)
        subjects_count = StudentSubject.query.filter_by(user_id=u.id).count()
        has_planner = StudyPlan.query.filter_by(student_id=u.id).count() > 0
        rows.append({
            "user": u, 
            "profile": prof,
            "profile_complete": profile_complete,
            "assessed": assessed, 
            "subjects_count": subjects_count, 
            "has_planner": has_planner,
        })

    stats = {
        "total": User.query.filter_by(role="student").count(),
        "complete_profile": StudentProfile.query.filter(StudentProfile.country != None, StudentProfile.study_level != None).count(),
        "assessed": StudentProfile.query.filter_by(has_completed_assessment=True).count(),
        "active": User.query.filter_by(role="student", is_active=True).count(),
    }

    return render_template(
        "admin/students/list.html",
        students=rows, page=page, pages=pages,
        stats=stats, levels=levels, universities=universities, programs=programs,
        search_q=search_q, selected_level=selected_level, 
        selected_university=selected_university, selected_program=selected_program,
        selected_status=selected_status,
    )


@admin_bp.route("/students/<int:student_id>")
def student_detail(student_id):
    from app.models import (
        Prediction, StudentAssessment, Subject as SubjectModel, StudyPlan,
        AcademicDocument, UploadedMaterial, StudyLog, AdminActivityLog
    )
    student = User.query.get_or_404(student_id)
    profile = student.profile
    subjects = StudentSubject.query.filter_by(user_id=student_id).all()
    latest_prediction = Prediction.query.filter_by(user_id=student_id).order_by(Prediction.date.desc()).first()
    assessments = StudentAssessment.query.filter_by(student_id=student_id).order_by(StudentAssessment.completed_at.desc()).limit(10).all()
    
    for a in assessments:
        a.subject = SubjectModel.query.get(a.subject_id) if a.subject_id else None
        
    study_plan = StudyPlan.query.filter_by(student_id=student_id).order_by(StudyPlan.generated_at.desc()).first()
    
    # Uploads & Docs
    academic_docs = AcademicDocument.query.filter_by(student_id=student_id).all()
    uploaded_materials = UploadedMaterial.query.filter_by(user_id=student_id).all()

    # Study Logs summary
    total_study_logs = StudyLog.query.filter_by(user_id=student_id).count()
    total_study_hours = round(db.session.query(db.func.sum(StudyLog.duration_hours)).filter_by(user_id=student_id).scalar() or 0.0, 1)

    # Activity history
    student_logs = AdminActivityLog.query.filter(
        AdminActivityLog.entity_type == 'User',
        AdminActivityLog.entity_id == student_id
    ).order_by(AdminActivityLog.timestamp.desc()).all()

    return render_template(
        "admin/students/detail.html",
        student=student, profile=profile, subjects=subjects,
        latest_prediction=latest_prediction,
        assessments=assessments,
        study_plan=study_plan,
        academic_docs=academic_docs,
        uploaded_materials=uploaded_materials,
        total_study_logs=total_study_logs,
        total_study_hours=total_study_hours,
        student_logs=student_logs
    )



@admin_bp.route("/students/<int:student_id>/impersonate", methods=["POST"])
def impersonate(student_id):
    student = User.query.get_or_404(student_id)
    if student.role != "student":
        flash("You can only impersonate student accounts.", "warning")
        return redirect(url_for("admin.student_detail", student_id=student_id))
    from flask import session as flask_session
    flask_session["impersonating_student_id"] = student_id
    log_admin_action("impersonate_student", "User", student_id, f"Started impersonating student '{student.email}'")
    flash(f"Now viewing as student: {student.full_name or student.email}", "info")
    from flask import redirect, url_for
    return redirect("/student/dashboard")


@admin_bp.route("/impersonate/exit")
def exit_impersonate():
    from flask import session as flask_session
    impersonate_id = flask_session.pop("impersonating_student_id", None)
    if impersonate_id:
        student = User.query.get(impersonate_id)
        log_admin_action("exit_impersonation", "User", impersonate_id, f"Exited impersonation of student ID {impersonate_id}")
        flash(f"Exited impersonation mode.", "success")
        return redirect(url_for("admin.student_detail", student_id=impersonate_id))
    return redirect(url_for("admin.students"))


@admin_bp.route("/students/<int:student_id>/run-ml", methods=["POST"])
def student_run_ml(student_id):
    student = User.query.get_or_404(student_id)
    try:
        from app.routes.student import (
            get_profile_subjects, get_subject_performance_snapshot,
            get_subject_features, load_ml_model,
        )
        import numpy as np
        profile = StudentProfile.query.filter_by(user_id=student_id).first()
        student_subjects = get_profile_subjects(profile)
        if not student_subjects:
            flash("Student has no subjects configured. Cannot run ML.", "warning")
            return redirect(url_for("admin.student_detail", student_id=student_id))

        raw_gpa = float(profile.cumulative_gpa or profile.prior_academic_score or 0.0)
        profile_grade = raw_gpa * 25 if raw_gpa <= 4.0 else raw_gpa
        attendance = float(profile.attendance_pct or 85.0)
        target_weekly_hours = float(profile.target_weekly_hours or 14.0)
        per_subject_weekly_hours = max(1.0, target_weekly_hours / max(1, len(student_subjects)))
        model = load_ml_model("random_forest")
        scaler = load_ml_model("scaler")

        prediction_rank = {"low": 0, "medium": 1, "high": 2}
        overall_risk = "low"

        for subject in student_subjects:
            snapshot = get_subject_performance_snapshot(student_id, subject.id)
            if snapshot["source"] == "missing" or snapshot["score"] is None:
                continue
            performance_score = snapshot["score"]
            difficulty = float(subject.difficulty_level or 3.0)
            features = get_subject_features(
                student_id, subject.name, performance_score,
                attendance, per_subject_weekly_hours, difficulty, 30, None,
            )
            if model and scaler:
                f_scaled = scaler.transform(np.array([features]))
                if hasattr(model, "predict_proba"):
                    probs = model.predict_proba(f_scaled)[0]
                    risk_pred = int(np.argmax(probs))
                else:
                    risk_pred = min(2, max(0, int(model.predict(f_scaled)[0])))
            else:
                risk_pred = 1
            risk_lvl = ["low", "medium", "high"][risk_pred]
            if prediction_rank.get(risk_lvl, 0) > prediction_rank.get(overall_risk, 0):
                overall_risk = risk_lvl

        # Store/update the overall prediction
        existing = Prediction.query.filter_by(user_id=student_id).order_by(Prediction.date.desc()).first()
        if existing:
            existing.predicted_risk_level = overall_risk
            existing.date = datetime.utcnow()
        else:
            new_pred = Prediction(user_id=student_id, predicted_risk_level=overall_risk, date=datetime.utcnow())
            db.session.add(new_pred)
        db.session.commit()

        log_admin_action("run_ml_prediction", "User", student_id, f"ML re-run: risk={overall_risk} for {student.email}")
        flash(f"ML prediction updated for {student.full_name or student.email} — Risk: {overall_risk.upper()}", "success")
    except Exception as e:
        flash(f"Could not run ML prediction: {e}", "danger")
    return redirect(url_for("admin.student_detail", student_id=student_id))


@admin_bp.route("/students/<int:student_id>/reset-assessment", methods=["POST"])
def student_reset_assessment(student_id):
    from app.models import StudentProfile
    profile = StudentProfile.query.filter_by(user_id=student_id).first()
    if profile:
        profile.has_completed_assessment = False
        db.session.commit()
    # Clear any session state for that student
    log_admin_action("reset_assessment", "User", student_id, f"Reset assessment session for student ID {student_id}")
    flash("Assessment session reset. Student can now start fresh.", "success")
    return redirect(url_for("admin.student_detail", student_id=student_id))


@admin_bp.route("/students/<int:student_id>/toggle-active", methods=["POST"])
def student_toggle_active(student_id):
    student = User.query.get_or_404(student_id)
    student.is_active = not student.is_active
    db.session.commit()
    action_str = "activated" if student.is_active else "suspended"
    log_admin_action(f"{action_str}_student_account", "User", student_id, f"Account {action_str} for student {student.email}")
    flash(f"Account {action_str} for {student.full_name or student.email}.", "success")
    return redirect(url_for("admin.student_detail", student_id=student_id))


# ── SECTION 4 STUB: HEALTH ────────────────────────────────────────────────────
@admin_bp.route("/health")
def health():
    """AI & ML Management + System Health Dashboard."""
    import os, sys, time, datetime
    from flask import current_app
    from app.models import (
        User, Prediction, StudentProfile, LearningMaterial, 
        AssessmentQuestion, Subject as SubjectModel
    )

    # 1. Audit all 14 ML model and scaler files from filesystem
    models_dir = os.path.join(current_app.root_path, "..", "models")
    if not os.path.exists(models_dir):
        models_dir = os.path.join(current_app.root_path, "models")
        if not os.path.exists(models_dir):
            models_dir = "models"

    ml_inventory = [
        {"filename": "random_forest.pkl", "name": "Global Random Forest Classifier", "type": "Model", "cohort": "Global / All Levels"},
        {"filename": "rf_bachelors.pkl", "name": "Bachelors Cohort Classifier", "type": "Model", "cohort": "Bachelors Degree"},
        {"filename": "rf_class11.pkl", "name": "Class 11 NEB Classifier", "type": "Model", "cohort": "Class 11"},
        {"filename": "rf_class12.pkl", "name": "Class 12 NEB Classifier", "type": "Model", "cohort": "Class 12"},
        {"filename": "rf_class8.pkl", "name": "Class 8 Classifier", "type": "Model", "cohort": "Class 8"},
        {"filename": "rf_masters.pkl", "name": "Masters Cohort Classifier", "type": "Model", "cohort": "Masters Degree"},
        {"filename": "rf_see.pkl", "name": "SEE Class 10 Classifier", "type": "Model", "cohort": "SEE / Class 10"},
        {"filename": "scaler.pkl", "name": "Global Standard Scaler", "type": "Scaler", "cohort": "Global / All Levels"},
        {"filename": "scaler_bachelors.pkl", "name": "Bachelors Standard Scaler", "type": "Scaler", "cohort": "Bachelors Degree"},
        {"filename": "scaler_class11.pkl", "name": "Class 11 Standard Scaler", "type": "Scaler", "cohort": "Class 11"},
        {"filename": "scaler_class12.pkl", "name": "Class 12 Standard Scaler", "type": "Scaler", "cohort": "Class 12"},
        {"filename": "scaler_class8.pkl", "name": "Class 8 Standard Scaler", "type": "Scaler", "cohort": "Class 8"},
        {"filename": "scaler_masters.pkl", "name": "Masters Standard Scaler", "type": "Scaler", "cohort": "Masters Degree"},
        {"filename": "scaler_see.pkl", "name": "SEE Class 10 Standard Scaler", "type": "Scaler", "cohort": "SEE / Class 10"},
    ]

    total_ml_size = 0
    active_ml_count = 0
    missing_ml_count = 0
    largest_file = None
    smallest_file = None
    last_modified_file = None

    for m in ml_inventory:
        file_path = os.path.join(models_dir, m["filename"])
        if os.path.exists(file_path):
            m["exists"] = True
            size = os.path.getsize(file_path)
            m["size"] = size
            m["size_formatted"] = f"{size / 1024:.1f} KB" if size < 1024*1024 else f"{size / (1024*1024):.2f} MB"
            mtime = os.path.getmtime(file_path)
            m["mtime"] = mtime
            m["mtime_formatted"] = datetime.datetime.fromtimestamp(mtime).strftime("%b %d, %Y %H:%M")
            
            if size == 0:
                m["status"] = "ERROR"
                missing_ml_count += 1
            elif size < 100:
                m["status"] = "WARNING"
                active_ml_count += 1
            else:
                m["status"] = "ACTIVE"
                active_ml_count += 1
                
            total_ml_size += size
            
            if largest_file is None or size > largest_file["size"]:
                largest_file = m
            if smallest_file is None or size < smallest_file["size"]:
                smallest_file = m
            if last_modified_file is None or mtime > last_modified_file["mtime"]:
                last_modified_file = m
        else:
            m["exists"] = False
            m["size"] = 0
            m["size_formatted"] = "0 B"
            m["mtime"] = 0
            m["mtime_formatted"] = "N/A"
            m["status"] = "MISSING"
            missing_ml_count += 1

    # 2. Real Prediction & Risk Distribution Stats
    total_predictions = Prediction.query.count()
    low_risk_count = Prediction.query.filter_by(predicted_risk_level="Low Risk").count()
    med_risk_count = Prediction.query.filter_by(predicted_risk_level="Medium Risk").count()
    high_risk_count = Prediction.query.filter_by(predicted_risk_level="High Risk").count()

    # 3. Gemini API Health Configuration Check
    from app.services.ai_service import ai_service
    gemini_health = ai_service.get_ai_health_status()
    gemini_configured = (gemini_health["api_config"] == "Configured")
    
    mode = gemini_health["mode"].lower()
    if mode == "paid":
        raw_api_key = current_app.config.get("GEMINI_API_KEY_PAID") or current_app.config.get("GEMINI_API_KEY") or ""
    else:
        raw_api_key = current_app.config.get("GEMINI_API_KEY_FREE") or current_app.config.get("GEMINI_API_KEY") or ""
    masked_key = f"••••••••••••{raw_api_key[-4:]}" if len(raw_api_key) >= 4 else ("••••••••••••" if gemini_configured else "Not set")
    
    gemini_model_version = gemini_health["mcq_model"]

    # 4. Content & Material Telemetry
    total_ai_materials = LearningMaterial.query.count()

    # 5. Diagnostic scanner checks
    subjects_zero_q = 0
    try:
        all_subjects = SubjectModel.query.filter_by(is_active=True).all()
        for s in all_subjects:
            if AssessmentQuestion.query.filter_by(subject_id=s.id).count() == 0:
                subjects_zero_q += 1
    except Exception:
        subjects_zero_q = 0

    broken_pdfs_count = 0
    try:
        cache_dir = os.path.join(current_app.root_path, "static", "cache", "pdfs")
        if os.path.exists(cache_dir):
            for f in os.listdir(cache_dir):
                if f.startswith("chapter_") and f.endswith(".pdf"):
                    if os.path.getsize(os.path.join(cache_dir, f)) < 5000:
                        broken_pdfs_count += 1
    except Exception:
        broken_pdfs_count = 0

    # System services live checks
    checks = {
        "db": _check_db(),
        "gemini": _check_gemini_api(),
        "ml": _check_ml_model(),
    }
    disk = _get_disk_info()
    python_info = _get_python_info()

    return render_template(
        "admin/health.html",
        ml_inventory=ml_inventory,
        active_ml_count=active_ml_count,
        missing_ml_count=missing_ml_count,
        total_ml_size_formatted=f"{total_ml_size / (1024*1024):.2f} MB",
        largest_file=largest_file,
        smallest_file=smallest_file,
        last_modified_file=last_modified_file,
        total_predictions=total_predictions,
        low_risk_count=low_risk_count,
        med_risk_count=med_risk_count,
        high_risk_count=high_risk_count,
        gemini_configured=gemini_configured,
        masked_key=masked_key,
        gemini_model_version=gemini_model_version,
        gemini_health=gemini_health,
        total_ai_materials=total_ai_materials,
        subjects_zero_q=subjects_zero_q,
        broken_pdfs_count=broken_pdfs_count,
        checks=checks,
        disk=disk,
        python_info=python_info
    )




# ── SECTION 2 STUB: CONTENT ──────────────────────────────────────────────────
@admin_bp.route("/curriculum/integrity")
def curriculum_integrity():
    """Read-only Admin Curriculum Integrity Checker & Health Scanner."""
    from app.models import (
        Subject, ProgramSubject, CurriculumProgram, EducationLevel, University, Faculty,
        Chapter, Topic, LearningMaterial, AssessmentQuestion, User, StudentProfile, StudentSubject
    )
    
    total_subjects = Subject.query.count()
    mapped_subject_ids = set(r[0] for r in db.session.query(ProgramSubject.subject_id).filter(ProgramSubject.is_active==True).all())
    mapped_count = len(mapped_subject_ids)
    unmapped_count = total_subjects - mapped_count
    pct_mapped = round((mapped_count / total_subjects * 100), 1) if total_subjects > 0 else 0.0

    unmapped_subjects = db.session.query(Subject).filter(~Subject.id.in_(mapped_subject_ids)).all() if mapped_subject_ids else Subject.query.all()
    
    all_programs = CurriculumProgram.query.all()
    program_audit = []
    
    for p in all_programs:
        level = EducationLevel.query.get(p.education_level_id) if getattr(p, 'education_level_id', None) else None
        uni = University.query.get(p.university_id) if getattr(p, 'university_id', None) else None
        
        mappings = ProgramSubject.query.filter_by(program_id=p.id, is_active=True).all()
        total_p_mapped = len(mappings)
        
        sem_counts = {f"Semester {s}": 0 for s in range(1, 7)}
        for m in mappings:
            sem_key = (m.semester or "").strip()
            if sem_key in sem_counts:
                sem_counts[sem_key] += 1
        
        status = "HEALTHY" if total_p_mapped > 0 else "CRITICAL"
        if total_p_mapped > 0 and any(cnt == 0 for cnt in sem_counts.values()):
            status = "WARNING"
            
        program_audit.append({
            "program": p,
            "level_name": level.name if level else "N/A",
            "uni_name": uni.name if uni else "N/A",
            "total_mapped": total_p_mapped,
            "sem_counts": sem_counts,
            "status": status
        })
    
    subjects_no_chaps = db.session.query(Subject).outerjoin(Chapter).filter(Chapter.id == None).count()
    chaps_no_topics = db.session.query(Chapter).outerjoin(Topic).filter(Topic.id == None).count()
    topics_no_mat = db.session.query(Topic).outerjoin(LearningMaterial).filter(LearningMaterial.id == None).count()
    subjects_no_mcq = db.session.query(Subject).outerjoin(AssessmentQuestion).filter(AssessmentQuestion.id == None).count()
    
    students_with_prog = db.session.query(User).join(StudentProfile).filter(User.role == 'student', StudentProfile.program != None, StudentProfile.program != '').all()
    students_zero_subjs = []
    for st in students_with_prog:
        st_sub_cnt = StudentSubject.query.filter_by(user_id=st.id).count()
        if st_sub_cnt == 0:
            sp = StudentProfile.query.filter_by(user_id=st.id).first()
            students_zero_subjs.append({
                "user": st,
                "profile": sp
            })
            
    return render_template(
        "admin/curriculum/integrity.html",
        total_subjects=total_subjects,
        mapped_count=mapped_count,
        unmapped_count=unmapped_count,
        pct_mapped=pct_mapped,
        unmapped_subjects=unmapped_subjects[:30],
        program_audit=program_audit,
        subjects_no_chaps=subjects_no_chaps,
        chaps_no_topics=chaps_no_topics,
        topics_no_mat=topics_no_mat,
        subjects_no_mcq=subjects_no_mcq,
        students_zero_subjs=students_zero_subjs
    )


@admin_bp.route("/content")
def content_subjects():
    """Redirect main /content to the stats overview."""
    return redirect(url_for("admin.content_stats"))


# ── SECTION 6: COHORT ANALYTICS & AUDIT LOGS ───────────────────────────────────

@admin_bp.route("/analytics")
def analytics():

    """Cohort Analytics & Risk Reporting Dashboard."""
    from app.models import (
        User, StudentProfile, Prediction, StudyLog, StudentAssessment,
        EducationLevel, University, Faculty, CurriculumProgram, LearningMaterial, Subject as SubjectModel
    )
    from sqlalchemy import func

    # Filter parameters
    sel_level = request.args.get("level", "").strip()
    sel_university = request.args.get("university", "").strip()
    sel_faculty = request.args.get("faculty", "").strip()
    sel_program = request.args.get("program", "").strip()
    sel_status = request.args.get("status", "").strip()

    # Query base students
    sq = User.query.filter_by(role="student")

    if sel_status == "active":
        sq = sq.filter_by(is_active=True)
    elif sel_status == "inactive":
        sq = sq.filter_by(is_active=False)

    if sel_level or sel_university or sel_program:
        sq = sq.join(StudentProfile)
        if sel_level:
            sq = sq.filter(StudentProfile.study_level == sel_level)
        if sel_university:
            sq = sq.filter(StudentProfile.university == sel_university)
        if sel_program:
            sq = sq.filter(StudentProfile.program == sel_program)

    filtered_students = sq.all()
    student_ids = [u.id for u in filtered_students]
    total_monitored = len(filtered_students)
    active_students = sum(1 for u in filtered_students if u.is_active)
    inactive_students = total_monitored - active_students

    # Calculate real profile completion rate
    if student_ids:
        profiles = StudentProfile.query.filter(StudentProfile.user_id.in_(student_ids)).all()
        comp_scores = []
        for p in profiles:
            fields = [p.study_level, p.university or p.country, p.program, p.cumulative_gpa or p.prior_academic_score, p.country]
            filled = sum(1 for f in fields if f is not None and str(f).strip() != "")
            comp_scores.append((filled / len(fields)) * 100)
        profile_completion_rate = round(sum(comp_scores) / len(comp_scores), 1) if comp_scores else 0.0
    else:
        profile_completion_rate = 0.0

    # Total AI Study Materials
    total_ai_materials = LearningMaterial.query.count()

    # Group analytics by Education Level
    all_levels = EducationLevel.query.filter_by(is_active=True).order_by(EducationLevel.sort_order).all()
    cohort_list = []

    for lvl in all_levels:
        lvl_name = lvl.name
        # Query profiles in this level matching global filter student IDs
        if student_ids:
            lvl_profiles = StudentProfile.query.filter(
                StudentProfile.user_id.in_(student_ids),
                StudentProfile.study_level == lvl_name
            ).all()
        else:
            lvl_profiles = []

        lvl_student_ids = [p.user_id for p in lvl_profiles]
        lvl_student_count = len(lvl_student_ids)

        if lvl_student_count > 0:
            lvl_users = [u for u in filtered_students if u.id in lvl_student_ids]
            lvl_active = sum(1 for u in lvl_users if u.is_active)
            lvl_inactive = lvl_student_count - lvl_active

            # GPA
            gpas = [p.cumulative_gpa for p in lvl_profiles if p.cumulative_gpa is not None]
            avg_gpa = round(sum(gpas) / len(gpas), 2) if gpas else None

            # Attendance
            atts = [p.attendance_pct for p in lvl_profiles if p.attendance_pct is not None]
            avg_attendance = round(sum(atts) / len(atts), 1) if atts else None

            # Study Hours (Check if StudyLog records exist)
            s_hours = db.session.query(func.sum(StudyLog.duration_hours)).filter(StudyLog.user_id.in_(lvl_student_ids)).scalar()
            avg_study_hours = round(s_hours / lvl_student_count, 1) if s_hours is not None else None

            # Assessment
            s_assess = db.session.query(func.avg(StudentAssessment.weighted_score)).filter(StudentAssessment.student_id.in_(lvl_student_ids)).scalar()
            avg_assessment = round(s_assess, 1) if s_assess is not None else None
        else:
            lvl_active = 0
            lvl_inactive = 0
            avg_gpa = None
            avg_attendance = None
            avg_study_hours = None
            avg_assessment = None

        cohort_list.append({
            "level": lvl_name,
            "student_count": lvl_student_count,
            "active_count": lvl_active,
            "inactive_count": lvl_inactive,
            "avg_gpa": avg_gpa,
            "avg_attendance": avg_attendance,
            "avg_study_hours": avg_study_hours,
            "avg_assessment": avg_assessment
        })

    # Risk Distribution calculation
    total_predictions = Prediction.query.filter(Prediction.user_id.in_(student_ids)).count() if student_ids else 0
    if total_predictions > 0:
        low_risk = Prediction.query.filter(Prediction.user_id.in_(student_ids), Prediction.predicted_risk_level == "Low Risk").count()
        med_risk = Prediction.query.filter(Prediction.user_id.in_(student_ids), Prediction.predicted_risk_level == "Medium Risk").count()
        high_risk = Prediction.query.filter(Prediction.user_id.in_(student_ids), Prediction.predicted_risk_level == "High Risk").count()
        has_predictions = True
    else:
        low_risk = 0
        med_risk = 0
        high_risk = 0
        has_predictions = False

    # AI Materials by Subject breakdown
    ai_materials_by_subject = []
    from app.models import Topic, Chapter
    subjects_all = SubjectModel.query.filter_by(is_active=True).order_by(SubjectModel.name).all()
    for s in subjects_all:
        m_count = LearningMaterial.query.join(Topic).join(Chapter).filter(Chapter.subject_id == s.id).count()
        if m_count > 0:
            ai_materials_by_subject.append({"subject": s.name, "count": m_count})
    ai_materials_by_subject.sort(key=lambda x: x["count"], reverse=True)


    # Filter dropdown choices
    education_levels = EducationLevel.query.filter_by(is_active=True).order_by(EducationLevel.sort_order).all()
    universities = University.query.filter_by(is_active=True).order_by(University.name).all()
    faculties = Faculty.query.filter_by(is_active=True).order_by(Faculty.name).all()
    programs = CurriculumProgram.query.filter_by(is_active=True).order_by(CurriculumProgram.name).all()

    return render_template(
        "admin/analytics.html",
        total_monitored=total_monitored,
        active_students=active_students,
        inactive_students=inactive_students,
        profile_completion_rate=profile_completion_rate,
        total_ai_materials=total_ai_materials,
        cohorts=cohort_list,
        has_predictions=has_predictions,
        low_risk=low_risk,
        med_risk=med_risk,
        high_risk=high_risk,
        ai_materials_by_subject=ai_materials_by_subject,
        education_levels=education_levels,
        universities=universities,
        faculties=faculties,
        programs=programs,
        sel_level=sel_level,
        sel_university=sel_university,
        sel_faculty=sel_faculty,
        sel_program=sel_program,
        sel_status=sel_status
    )


@admin_bp.route("/activity-log")
def activity_log():
    """System Audit Logs & Security History Center."""
    from app.models import AdminActivityLog, User
    import datetime

    action_filter = request.args.get("action", "").strip()
    q = request.args.get("q", "").strip()
    from_date_str = request.args.get("from_date", "").strip()
    to_date_str = request.args.get("to_date", "").strip()
    page = request.args.get("page", 1, type=int)
    per_page = 20

    query = AdminActivityLog.query

    if action_filter:
        query = query.filter_by(action=action_filter)

    if q:
        query = query.filter(
            (AdminActivityLog.action.ilike(f"%{q}%")) |
            (AdminActivityLog.entity_type.ilike(f"%{q}%")) |
            (AdminActivityLog.detail.ilike(f"%{q}%"))
        )

    if from_date_str:
        try:
            from_dt = datetime.datetime.strptime(from_date_str, "%Y-%m-%d")
            query = query.filter(AdminActivityLog.timestamp >= from_dt)
        except ValueError:
            pass

    if to_date_str:
        try:
            to_dt = datetime.datetime.strptime(to_date_str, "%Y-%m-%d") + datetime.timedelta(days=1)
            query = query.filter(AdminActivityLog.timestamp < to_dt)
        except ValueError:
            pass

    total = query.count()
    from math import ceil
    pages = ceil(total / per_page) if total else 1

    logs = query.order_by(AdminActivityLog.timestamp.desc()).offset((page - 1) * per_page).limit(per_page).all()

    # Pre-fetch admin emails
    admin_users = {u.id: u for u in User.query.filter_by(role="admin").all()}

    # Dynamic action list for filter dropdown
    distinct_actions = [r[0] for r in db.session.query(AdminActivityLog.action).distinct().all() if r[0]]

    return render_template(
        "admin/activity_log.html",
        logs=logs,
        admin_users=admin_users,
        page=page,
        pages=pages,
        total=total,
        actions=distinct_actions,
        action_filter=action_filter,
        q=q,
        from_date=from_date_str,
        to_date=to_date_str
    )



# ── SECTION 7: RESTART-FREE LIVE CONFIGURATION ────────────────────────────────
@admin_bp.route("/config", methods=["GET", "POST"])
@super_admin_required
def config():

    """System Configuration & Maintenance Control Center."""
    import os, sys, datetime
    from flask import current_app
    from app.models import AppSetting, AdminActivityLog, User, Subject as SubjectModel, ProgramSubject, Chapter, Topic, LearningMaterial, AssessmentQuestion
    from app.live_config import load_live_config
    
    if request.method == "POST":
        # Save all configs securely
        keys = [
            "GEMINI_API_KEY", "GEMINI_API_KEY_FREE", "GEMINI_API_KEY_PAID", "ANTHROPIC_API_KEY",
            "GEMINI_MODEL_MCQ", "GEMINI_MODEL_ASSISTANT_PRIMARY", "GEMINI_MODEL_ASSISTANT_FALLBACK",
            "GEMINI_DAILY_LIMIT_MCQ", "GEMINI_RPM_LIMIT_MCQ",
            "GEMINI_DAILY_LIMIT_ASSISTANT_PRIMARY", "GEMINI_DAILY_LIMIT_ASSISTANT_FALLBACK",
            "GEMINI_RPM_LIMIT_ASSISTANT_PRIMARY", "GEMINI_RPM_LIMIT_ASSISTANT_FALLBACK",
            "GEMINI_DAILY_LIMIT_MCQ_PAID", "GEMINI_RPM_LIMIT_MCQ_PAID",
            "GEMINI_DAILY_LIMIT_ASSISTANT_PRIMARY_PAID", "GEMINI_RPM_LIMIT_ASSISTANT_PRIMARY_PAID",
            "GEMINI_GLOBAL_DAILY_LIMIT_FREE", "GEMINI_GLOBAL_DAILY_LIMIT_PAID",
            "GEMINI_GLOBAL_RPM_LIMIT_FREE", "GEMINI_GLOBAL_RPM_LIMIT_PAID",
            "GEMINI_PAID_PROVIDER_RPM", "GEMINI_PAID_PROVIDER_RPD",
            "GEMINI_MODE", "GEMINI_ALLOW_CROSS_KEY_FALLBACK",
            "PLANNER_SESSION_MINUTES", "PLANNER_BREAK_MINUTES", "PLANNER_SESSIONS_PER_DAY",
            "MAINTENANCE_MESSAGE"
        ]
        for k in keys:
            if k in request.form:
                val = request.form.get(k, "").strip()
                setting = AppSetting.query.get(k)
                if setting:
                    setting.value = val
                else:
                    setting = AppSetting(key=k, value=val)
                    db.session.add(setting)
                
        # Sync legacy GEMINI_BILLING_ENABLED with canonical GEMINI_MODE
        if "GEMINI_MODE" in request.form or "save_general" in request.form:
            mode = request.form.get("GEMINI_MODE", "free").lower()
            billing = "True" if mode == "paid" else "False"
            setting_billing = AppSetting.query.get("GEMINI_BILLING_ENABLED")
            if setting_billing:
                setting_billing.value = billing
            else:
                setting_billing = AppSetting(key="GEMINI_BILLING_ENABLED", value=billing)
                db.session.add(setting_billing)
            
        db.session.commit()
        load_live_config(current_app._get_current_object(), force=True)
        log_admin_action("update_config", "AppSetting", None, "Updated application settings and flushed config cache")
        flash("Configuration updated and cache reloaded successfully.", "success")
        return redirect(url_for("admin.config"))
        
    settings = {s.key: s.value for s in AppSetting.query.all()}

    # Mail configuration inspection
    mail_config = {
        "server": current_app.config.get("MAIL_SERVER", "smtp.gmail.com"),
        "port": current_app.config.get("MAIL_PORT", 587),
        "use_tls": current_app.config.get("MAIL_USE_TLS", True),
        "username": current_app.config.get("MAIL_USERNAME", "hemantsah123456789@gmail.com"),
        "configured": bool(current_app.config.get("MAIL_USERNAME") and current_app.config.get("MAIL_PASSWORD")),
        "password_masked": "••••••••••••" if current_app.config.get("MAIL_PASSWORD") else "Not set"
    }

    # Gemini configuration inspection
    raw_api_key = settings.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY") or current_app.config.get("GEMINI_API_KEY") or ""
    raw_api_key_free = settings.get("GEMINI_API_KEY_FREE") or os.environ.get("GEMINI_API_KEY_FREE") or current_app.config.get("GEMINI_API_KEY_FREE") or ""
    raw_api_key_paid = settings.get("GEMINI_API_KEY_PAID") or os.environ.get("GEMINI_API_KEY_PAID") or current_app.config.get("GEMINI_API_KEY_PAID") or ""
    
    gemini_config = {
        "configured": bool(raw_api_key.strip() or raw_api_key_free.strip() or raw_api_key_paid.strip()),
        "masked_key": f"••••••••••••{raw_api_key[-4:]}" if len(raw_api_key) >= 4 else ("••••••••••••" if raw_api_key else "Not set"),
        "masked_key_free": f"••••••••••••{raw_api_key_free[-4:]}" if len(raw_api_key_free) >= 4 else ("••••••••••••" if raw_api_key_free else "Not set"),
        "masked_key_paid": f"••••••••••••{raw_api_key_paid[-4:]}" if len(raw_api_key_paid) >= 4 else ("••••••••••••" if raw_api_key_paid else "Not set"),
        "billing_enabled": settings.get("GEMINI_BILLING_ENABLED", "False") == "True",
        "gemini_mode": settings.get("GEMINI_MODE", "free").lower(),
        "mcq_model": settings.get("GEMINI_MODEL_MCQ") or current_app.config.get("GEMINI_MODEL_MCQ", "gemini-3.5-flash-lite"),
        "assistant_model": settings.get("GEMINI_MODEL_ASSISTANT_PRIMARY") or current_app.config.get("GEMINI_MODEL_ASSISTANT_PRIMARY", "gemini-3.6-flash"),
        "fallback_model": settings.get("GEMINI_MODEL_ASSISTANT_FALLBACK") or current_app.config.get("GEMINI_MODEL_ASSISTANT_FALLBACK", "gemini-3.5-flash-lite"),

        "mcq_daily_limit": settings.get("GEMINI_DAILY_LIMIT_MCQ") or current_app.config.get("GEMINI_DAILY_LIMIT_MCQ", "450"),
        "mcq_daily_limit_paid": settings.get("GEMINI_DAILY_LIMIT_MCQ_PAID") or current_app.config.get("GEMINI_DAILY_LIMIT_MCQ_PAID", "2000"),
        "assistant_daily_limit": settings.get("GEMINI_DAILY_LIMIT_ASSISTANT_PRIMARY") or current_app.config.get("GEMINI_DAILY_LIMIT_ASSISTANT_PRIMARY", "18"),
        "assistant_daily_limit_paid": settings.get("GEMINI_DAILY_LIMIT_ASSISTANT_PRIMARY_PAID") or current_app.config.get("GEMINI_DAILY_LIMIT_ASSISTANT_PRIMARY_PAID", "1000"),
    }

    # Maintenance mode state
    m_setting = AppSetting.query.get("MAINTENANCE_MODE")
    maintenance_active = (m_setting.value == "True") if m_setting else current_app.config.get("MAINTENANCE_MODE", False)
    m_msg_setting = AppSetting.query.get("MAINTENANCE_MESSAGE")
    maintenance_message = m_msg_setting.value if m_msg_setting else "Smart Study is currently undergoing scheduled maintenance. Please check back shortly."

    # Workspace backups inventory
    backups = []
    root_dir = current_app.root_path
    ws_dir = os.path.dirname(root_dir) if os.path.basename(root_dir) == "app" else root_dir
    active_db_path = os.path.join(ws_dir, "smart_study.db")
    active_db_size = os.path.getsize(active_db_path) if os.path.exists(active_db_path) else 0
    active_db_size_mb = round(active_db_size / (1024 * 1024), 2)

    try:
        for f in os.listdir(ws_dir):
            if f.endswith(".db") and f != "smart_study.db":
                b_path = os.path.join(ws_dir, f)
                b_size = os.path.getsize(b_path)
                b_mtime = os.path.getmtime(b_path)
                backups.append({
                    "filename": f,
                    "size_mb": round(b_size / (1024 * 1024), 2),
                    "mtime_formatted": datetime.datetime.fromtimestamp(b_mtime).strftime("%Y-%m-%d %H:%M:%S")
                })
        backups.sort(key=lambda x: x["filename"], reverse=True)
    except Exception:
        backups = []

    # System metrics summary
    system_info = {
        "flask_env": current_app.config.get("ENV", "production"),
        "debug": current_app.config.get("DEBUG", False),
        "python_version": sys.version.split(" ")[0],
        "db_type": "SQLite (Local File Storage)",
        "active_db_size_mb": active_db_size_mb,
        "admin_count": User.query.filter_by(role="admin").count(),
        "student_count": User.query.filter_by(role="student").count(),
        "last_backup": backups[0]["mtime_formatted"] if backups else "No backups created yet"
    }

    return render_template(
        "admin/config.html",
        settings=settings,
        mail_config=mail_config,
        gemini_config=gemini_config,
        maintenance_active=maintenance_active,
        maintenance_message=maintenance_message,
        backups=backups,
        active_db_size_mb=active_db_size_mb,
        system_info=system_info
    )


@admin_bp.route("/config/test-gemini", methods=["POST"])
def config_test_gemini():
    """Safe Gemini API connection test with logging (credentials masked)."""
    try:
        res = _check_gemini_api()
        if res.get("status") == "ok":
            log_admin_action("test_gemini_api", "GeminiAPI", None, f"Executed Gemini API connection test: OK ({res.get('latency_ms')}ms)")
            flash(f"Gemini API connection test SUCCESSFUL ({res.get('latency_ms')}ms latency).", "success")
        else:
            log_admin_action("test_gemini_api", "GeminiAPI", None, f"Executed Gemini API connection test: {res.get('status')} - {res.get('detail')}")
            flash(f"Gemini API test WARNING: {res.get('detail')}", "warning")
    except Exception as e:
        log_admin_action("test_gemini_api", "GeminiAPI", None, f"Gemini API test failed: {str(e)[:100]}")
        flash(f"Gemini API connection test failed: {e}", "danger")
    return redirect(url_for("admin.config"))


@admin_bp.route("/config/test-email", methods=["POST"])
def config_test_email():
    """Send test email via Flask-Mail to specified destination with validation."""
    from flask_mail import Message
    from app import mail
    dest_email = request.form.get("destination_email", "").strip()
    if not dest_email or "@" not in dest_email:
        flash("Please enter a valid destination email address.", "danger")
        return redirect(url_for("admin.config"))
        
    try:
        sender = current_app.config.get("MAIL_USERNAME") or "hemantsah123456789@gmail.com"
        msg = Message(
            subject="Smart Study Admin — Mail Configuration Test",
            sender=sender,
            recipients=[dest_email],
            body=f"Hello,\n\nThis is a test notification from the Smart Study Admin Control Center.\nSent at: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\nIf you received this email, your Flask-Mail SMTP configuration is working perfectly.\n\nRegards,\nSmart Study System Administrator"
        )
        mail.send(msg)
        log_admin_action("send_test_email", "FlaskMail", None, f"Sent SMTP test email to {dest_email}")
        flash(f"Test email successfully sent to {dest_email}.", "success")
    except Exception as e:
        log_admin_action("send_test_email", "FlaskMail", None, f"Failed sending test email to {dest_email}: {str(e)[:100]}")
        flash(f"Failed sending test email: {e}", "danger")
        
    return redirect(url_for("admin.config"))


@admin_bp.route("/config/maintenance", methods=["POST"])
def config_toggle_maintenance():
    """Toggle maintenance mode setting in AppSetting."""
    from app.models import AppSetting
    from app.live_config import load_live_config
    
    enable = request.form.get("enable") == "true"
    message = request.form.get("maintenance_message", "").strip() or "Smart Study is currently undergoing scheduled maintenance. Please check back shortly."
    
    s_mode = AppSetting.query.get("MAINTENANCE_MODE")
    if s_mode:
        s_mode.value = "True" if enable else "False"
    else:
        db.session.add(AppSetting(key="MAINTENANCE_MODE", value="True" if enable else "False"))
        
    s_msg = AppSetting.query.get("MAINTENANCE_MESSAGE")
    if s_msg:
        s_msg.value = message
    else:
        db.session.add(AppSetting(key="MAINTENANCE_MESSAGE", value=message))
        
    db.session.commit()
    load_live_config(current_app._get_current_object(), force=True)
    
    status_str = "ENABLED" if enable else "DISABLED"
    log_admin_action("toggle_maintenance", "AppSetting", None, f"Maintenance Mode {status_str}: {message}")
    flash(f"Maintenance Mode has been {status_str}. Administrator access remains active.", "warning" if enable else "success")
    return redirect(url_for("admin.config"))


@admin_bp.route("/config/create-backup", methods=["POST"])
def config_create_backup():
    """Create timestamped copy of smart_study.db with verification and logging."""
    import shutil
    try:
        root_dir = current_app.root_path
        ws_dir = os.path.dirname(root_dir) if os.path.basename(root_dir) == "app" else root_dir
        src_path = os.path.join(ws_dir, "smart_study.db")
        
        if not os.path.exists(src_path):
            flash("Database file smart_study.db not found.", "danger")
            return redirect(url_for("admin.config"))
            
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        dst_filename = f"smart_study_backup_{timestamp}.db"
        dst_path = os.path.join(ws_dir, dst_filename)
        
        shutil.copy2(src_path, dst_path)
        
        if os.path.exists(dst_path) and os.path.getsize(dst_path) > 0:
            size_mb = round(os.path.getsize(dst_path) / (1024 * 1024), 2)
            log_admin_action("create_backup", "Database", None, f"Created database backup: {dst_filename} ({size_mb} MB)")
            flash(f"Database backup created successfully: {dst_filename} ({size_mb} MB).", "success")
        else:
            flash("Backup file created but appeared empty. Please verify file integrity.", "danger")
    except Exception as e:
        log_admin_action("create_backup", "Database", None, f"Backup creation error: {str(e)[:100]}")
        flash(f"Error creating database backup: {e}", "danger")
        
    return redirect(url_for("admin.config"))


@admin_bp.route("/config/export-curriculum")
def config_export_curriculum():
    """Safe read-only CSV export of Curriculum Subjects & ProgramSubject mappings."""
    import csv, io
    from flask import Response
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "subject_id", "subject_code", "subject_name", "level_of_study",
        "program_tag", "credit_hours", "difficulty_level", "is_active"
    ])
    
    subjects = SubjectModel.query.order_by(SubjectModel.id).all()
    for s in subjects:
        writer.writerow([
            s.id, s.code or "", s.name, s.level_of_study or "",
            s.program or "", s.credit_hours or 3, s.difficulty_level or 3, s.is_active
        ])
        
    log_admin_action("export_curriculum_csv", "Subject", None, f"Exported {len(subjects)} subjects to CSV")
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=curriculum_subjects_export.csv"}
    )


@admin_bp.route("/config/export-curriculum-json")
def config_export_curriculum_json():
    """Safe read-only JSON export of Curriculum Subjects."""
    subjects = SubjectModel.query.order_by(SubjectModel.id).all()
    data = []
    for s in subjects:
        data.append({
            "id": s.id, "code": s.code, "name": s.name,
            "level_of_study": s.level_of_study, "program": s.program,
            "credit_hours": s.credit_hours, "difficulty_level": s.difficulty_level,
            "is_active": s.is_active
        })
    log_admin_action("export_curriculum_json", "Subject", None, f"Exported {len(subjects)} subjects to JSON")
    return jsonify(data)


@admin_bp.route("/config/export-audit-logs")
def config_export_audit_logs():
    """Safe read-only CSV export of Admin Activity Audit Logs."""
    import csv, io
    from flask import Response
    from app.models import AdminActivityLog
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["log_id", "timestamp", "admin_user_id", "action", "entity_type", "entity_id", "detail"])
    
    logs = AdminActivityLog.query.order_by(AdminActivityLog.id.desc()).all()
    for l in logs:
        writer.writerow([
            l.id, l.timestamp.strftime("%Y-%m-%d %H:%M:%S") if l.timestamp else "",
            l.admin_user_id, l.action, l.entity_type or "", l.entity_id or "", l.detail or ""
        ])
        
    log_admin_action("export_audit_logs_csv", "AdminActivityLog", None, f"Exported {len(logs)} audit logs to CSV")
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=admin_audit_logs.csv"}
    )



# ── SECTION 8: BULK OPERATIONS ────────────────────────────────────────────────
@admin_bp.route("/bulk", methods=["GET", "POST"])
def bulk():
    from app.models import Notification, EducationLevel, StudentProfile, Prediction
    
    levels = [l.name for l in EducationLevel.query.filter_by(is_active=True).order_by(EducationLevel.sort_order).all()]
    if not levels:
        levels = [r[0] for r in db.session.query(StudentProfile.study_level).distinct().all() if r[0]]
        
    if request.method == "POST":
        action = request.form.get("action")
        
        if action == "batch_ml":
            # Run predictions for all students
            students = User.query.filter_by(role="student").all()
            success_count = 0
            fail_count = 0
            
            from app.routes.student import (
                get_profile_subjects, get_subject_performance_snapshot,
                get_subject_features, load_ml_model,
            )
            import numpy as np
            
            model = load_ml_model("random_forest")
            scaler = load_ml_model("scaler")
            prediction_rank = {"low": 0, "medium": 1, "high": 2}
            
            for s in students:
                profile = StudentProfile.query.filter_by(user_id=s.id).first()
                if not profile:
                    fail_count += 1
                    continue
                    
                student_subjects = get_profile_subjects(profile)
                if not student_subjects:
                    fail_count += 1
                    continue
                    
                try:
                    raw_gpa = float(profile.cumulative_gpa or profile.prior_academic_score or 0.0)
                    attendance = float(profile.attendance_pct or 85.0)
                    target_weekly_hours = float(profile.target_weekly_hours or 14.0)
                    per_subject_weekly_hours = max(1.0, target_weekly_hours / max(1, len(student_subjects)))
                    
                    overall_risk = "low"
                    for subject in student_subjects:
                        snapshot = get_subject_performance_snapshot(s.id, subject.id)
                        if snapshot["source"] == "missing" or snapshot["score"] is None:
                            continue
                        performance_score = snapshot["score"]
                        difficulty = float(subject.difficulty_level or 3.0)
                        features = get_subject_features(
                            s.id, subject.name, performance_score,
                            attendance, per_subject_weekly_hours, difficulty, 30, None
                        )
                        if model and scaler:
                            f_scaled = scaler.transform(np.array([features]))
                            if hasattr(model, "predict_proba"):
                                probs = model.predict_proba(f_scaled)[0]
                                risk_pred = int(np.argmax(probs))
                            else:
                                risk_pred = min(2, max(0, int(model.predict(f_scaled)[0])))
                        else:
                            risk_pred = 1
                        risk_lvl = ["low", "medium", "high"][risk_pred]
                        if prediction_rank.get(risk_lvl, 0) > prediction_rank.get(overall_risk, 0):
                            overall_risk = risk_lvl
                            
                    # Update Prediction table
                    existing = Prediction.query.filter_by(user_id=s.id).order_by(Prediction.date.desc()).first()
                    if existing:
                        existing.predicted_risk_level = overall_risk
                        existing.date = datetime.utcnow()
                    else:
                        new_pred = Prediction(user_id=s.id, predicted_risk_level=overall_risk, date=datetime.utcnow())
                        db.session.add(new_pred)
                    success_count += 1
                except Exception:
                    fail_count += 1
                    
            db.session.commit()
            log_admin_action("batch_ml_prediction", "Prediction", None, f"Triggered batch ML prediction. Success: {success_count}, Fails: {fail_count}")
            flash(f"Batch ML run completed. Success: {success_count}, Skip/Fails: {fail_count}", "success")
            return redirect(url_for("admin.bulk"))
            
        elif action == "bulk_notification":
            target = request.form.get("target")
            cohort = request.form.get("cohort")
            risk_level = request.form.get("risk_level")
            message = request.form.get("message", "").strip()
            
            if not message:
                flash("Notification message cannot be empty.", "warning")
                return redirect(url_for("admin.bulk"))
                
            # Filter users
            query = User.query.filter_by(role="student")
            
            if target == "cohort" and cohort:
                query = query.join(StudentProfile).filter(StudentProfile.study_level == cohort)
            elif target == "risk" and risk_level:
                all_students = query.all()
                filtered_students = []
                for s in all_students:
                    pred = Prediction.query.filter_by(user_id=s.id).order_by(Prediction.date.desc()).first()
                    r_lvl = (pred.predicted_risk_level or "low").lower() if pred else "low"
                    if r_lvl == risk_level.lower():
                        filtered_students.append(s)
                query = filtered_students
                
            # Send notifications
            sent_count = 0
            target_list = query if isinstance(query, list) else query.all()
            for s in target_list:
                notif = Notification(
                    user_id=s.id,
                    message=message,
                    is_read=False,
                    date=datetime.utcnow()
                )
                db.session.add(notif)
                sent_count += 1
                
            db.session.commit()
            log_admin_action("bulk_notification", "Notification", None, f"Sent bulk notification to {sent_count} students (Target: {target})")
            flash(f"Bulk notification sent successfully to {sent_count} students.", "success")
            return redirect(url_for("admin.bulk"))
            
    return render_template("admin/bulk.html", cohorts=levels)


# ── SECTION 4: SYSTEM HEALTH DASHBOARD ───────────────────────────────────────
import os, time, sys
from flask import current_app

# Replace the stub
# (the stub exists from append_stubs.py; Flask will use the LAST registered
#  route for duplicates, but to be safe we'll use a new internal function
#  and route this under /admin/health which the blueprint already has stubs for)


def _check_gemini_api():
    """Ping Gemini with a minimal token to verify the API key is live."""
    try:
        mode = current_app.config.get("GEMINI_MODE", "free").lower()
        billing_on = (mode == "paid")
        if billing_on:
            api_key = current_app.config.get("GEMINI_API_KEY_PAID") or current_app.config.get("GEMINI_API_KEY")
        else:
            api_key = current_app.config.get("GEMINI_API_KEY_FREE") or current_app.config.get("GEMINI_API_KEY")
            
        if not api_key:
            return {"status": "unconfigured", "latency_ms": None, "detail": f"No active API key set for mode {mode}"}
            
        test_model = current_app.config.get("GEMINI_MODEL_ASSISTANT_FALLBACK", "gemini-3.1-flash-lite")
        try:
            from google import genai as _genai
            client = _genai.Client(api_key=api_key)
            start = time.perf_counter()
            resp = client.models.generate_content(
                model=test_model,
                contents="Reply with exactly: OK",
            )
            latency = round((time.perf_counter() - start) * 1000)
            text = getattr(resp, "text", "") or ""
            return {"status": "ok", "latency_ms": latency, "detail": text.strip()[:80]}
        except ImportError:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(test_model)
            start = time.perf_counter()
            resp = model.generate_content("Reply with exactly: OK")
            latency = round((time.perf_counter() - start) * 1000)
            return {"status": "ok", "latency_ms": latency, "detail": (resp.text or "")[:80]}
    except Exception as e:
        return {"status": "error", "latency_ms": None, "detail": str(e)[:120]}


def _check_ml_model():
    """Check that the Random Forest model and scaler are loadable."""
    try:
        from app.routes.student import load_ml_model
        model = load_ml_model("random_forest")
        scaler = load_ml_model("scaler")
        if model and scaler:
            return {"status": "ok", "detail": f"RF model: {type(model).__name__}, Scaler: {type(scaler).__name__}"}
        return {"status": "missing", "detail": "Model or scaler not found — train ML first"}
    except Exception as e:
        return {"status": "error", "detail": str(e)[:120]}


def _check_db():
    """Verify database is reachable and return table row counts."""
    try:
        start = time.perf_counter()
        student_count = User.query.filter_by(role="student").count()
        latency = round((time.perf_counter() - start) * 1000)
        pred_count = Prediction.query.count()
        return {"status": "ok", "latency_ms": latency, "detail": f"Students: {student_count}, Predictions: {pred_count}"}
    except Exception as e:
        return {"status": "error", "latency_ms": None, "detail": str(e)[:120]}


def _get_model_config():
    """Return a dict of model config for display."""
    cfg = current_app.config
    return [
        {"label": "MCQ Generator", "model": cfg.get("GEMINI_MODEL_MCQ", "—"), "daily_limit": cfg.get("GEMINI_DAILY_LIMIT_MCQ", "—"), "rpm": cfg.get("GEMINI_RPM_LIMIT_MCQ", "—")},
        {"label": "AI Assistant (Primary)", "model": cfg.get("GEMINI_MODEL_ASSISTANT_PRIMARY", "—"), "daily_limit": cfg.get("GEMINI_DAILY_LIMIT_ASSISTANT_PRIMARY", "—"), "rpm": cfg.get("GEMINI_RPM_LIMIT_ASSISTANT_PRIMARY", "—")},
        {"label": "AI Assistant (Fallback)", "model": cfg.get("GEMINI_MODEL_ASSISTANT_FALLBACK", "—"), "daily_limit": cfg.get("GEMINI_DAILY_LIMIT_ASSISTANT_FALLBACK", "—"), "rpm": "—"},
    ]


def _get_disk_info():
    try:
        import shutil
        total, used, free = shutil.disk_usage("/")
        return {
            "total_gb": round(total / 1e9, 1),
            "used_gb": round(used / 1e9, 1),
            "free_gb": round(free / 1e9, 1),
            "pct_used": round(used / total * 100, 1),
        }
    except Exception:
        return {}


def _get_python_info():
    return {
        "version": sys.version.split(" ")[0],
        "executable": sys.executable,
        "platform": sys.platform,
    }



# ── SECTION 2: CONTENT MANAGEMENT ────────────────────────────────────────────

# Replace stub in-place by redefining — Flask will use the last definition
# for the same URL. We reload the blueprint so both definitions register,
# but /admin/content will resolve to this one since blueprints apply routes
# in order. Using url_for('admin.content_subjects') will point here correctly.

from app.models import Subject as SubjectModel

@admin_bp.route("/content/questions")
def content_questions():
    """Browse and delete auto-generated MCQ questions."""
    from app.models import AssessmentQuestion
    page = request.args.get("page", 1, type=int)
    per_page = 30
    subject_id = request.args.get("subject_id", type=int)
    difficulty = request.args.get("difficulty", "").strip()

    q = AssessmentQuestion.query
    if subject_id:
        q = q.filter_by(subject_id=subject_id)
    if difficulty:
        q = q.filter_by(difficulty=difficulty)

    total = q.count()
    from math import ceil
    pages = ceil(total / per_page) if total else 1
    questions = q.order_by(AssessmentQuestion.generated_at.desc()).offset((page-1)*per_page).limit(per_page).all()
    subjects = SubjectModel.query.order_by(SubjectModel.name).all()
    return render_template(
        "admin/content/questions.html",
        questions=questions, subjects=subjects, page=page, pages=pages,
        subject_id=subject_id, difficulty=difficulty, total=total,
    )


@admin_bp.route("/content/questions/<int:q_id>/delete", methods=["POST"])
def content_delete_question(q_id):
    from app.models import AssessmentQuestion
    question = AssessmentQuestion.query.get_or_404(q_id)
    db.session.delete(question)
    db.session.commit()
    log_admin_action("delete_question", "AssessmentQuestion", q_id, f"Deleted MCQ question id={q_id}")
    flash("Question deleted.", "success")
    return redirect(url_for("admin.content_questions"))


@admin_bp.route("/content/chapters")
def content_chapters():
    """Browse chapters by subject."""
    from app.models import Chapter
    subject_id = request.args.get("subject_id", type=int)
    subjects = SubjectModel.query.order_by(SubjectModel.name).all()
    chapters = []
    if subject_id:
        chapters = Chapter.query.filter_by(subject_id=subject_id).order_by(Chapter.chapter_number).all()
    return render_template(
        "admin/content/chapters.html",
        subjects=subjects, chapters=chapters, subject_id=subject_id,
    )


@admin_bp.route("/content/materials")
def content_materials():
    """Searchable & filterable Learning Materials directory with server-side pagination."""
    from app.models import LearningMaterial, Topic, Chapter, Subject, EducationLevel
    
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 15, type=int)
    q = request.args.get("q", "").strip()
    subject_id = request.args.get("subject_id", type=int)
    level = request.args.get("level", "").strip()
    difficulty = request.args.get("difficulty", "").strip()
    
    query = LearningMaterial.query.join(Topic).join(Chapter).join(Subject)
    
    if q:
        query = query.filter(
            (LearningMaterial.title.ilike(f"%{q}%")) |
            (LearningMaterial.introduction.ilike(f"%{q}%")) |
            (LearningMaterial.concepts.ilike(f"%{q}%"))
        )
    if subject_id:
        query = query.filter(Chapter.subject_id == subject_id)
    if level:
        query = query.filter(Subject.level_of_study == level)
    if difficulty:
        query = query.filter(LearningMaterial.difficulty_level == difficulty)
        
    pagination = query.order_by(LearningMaterial.id.desc()).paginate(page=page, per_page=per_page, error_out=False)
    materials = pagination.items
    
    # Pre-attach hierarchy metadata for each material
    for m in materials:
        m.topic_obj = Topic.query.get(m.topic_id) if m.topic_id else None
        if m.topic_obj:
            m.chapter_obj = m.topic_obj.chapter
            m.subject_obj = m.chapter_obj.subject if m.chapter_obj else None
        else:
            m.chapter_obj = None
            m.subject_obj = None

    subjects = SubjectModel.query.order_by(SubjectModel.name).all()
    levels = EducationLevel.query.filter_by(is_active=True).order_by(EducationLevel.sort_order).all()
    total_materials = LearningMaterial.query.count()

    return render_template(
        "admin/content/materials.html",
        materials=materials,
        pagination=pagination,
        page=page,
        q=q,
        subject_id=subject_id,
        level=level,
        difficulty=difficulty,
        subjects=subjects,
        levels=levels,
        total_materials=total_materials
    )


@admin_bp.route("/content/materials/<int:material_id>/preview")
def content_material_preview(material_id):
    """Read-only Admin preview of a learning material."""
    from app.models import LearningMaterial, Topic
    material = LearningMaterial.query.get_or_404(material_id)
    topic = Topic.query.get(material.topic_id) if material.topic_id else None
    chapter = topic.chapter if topic else None
    subject = chapter.subject if chapter else None

    # Calculate content length
    content_len = len(material.introduction or "") + len(material.concepts or "") + len(material.detailed_explanation or "")

    return render_template(
        "admin/content/preview.html",
        material=material,
        topic=topic,
        chapter=chapter,
        subject=subject,
        content_len=content_len
    )


@admin_bp.route("/content/stats")
def content_stats():
    """Content overview stats: subject/chapter/topic/material counts, broken PDFs check, recent materials."""
    import os
    from app.models import Chapter, AssessmentQuestion, Topic, LearningMaterial, UploadedMaterial, AcademicDocument
    from sqlalchemy import func
    
    subjects = SubjectModel.query.order_by(SubjectModel.name).all()
    rows = []
    for s in subjects:
        ch_count = Chapter.query.filter_by(subject_id=s.id).count()
        q_count = AssessmentQuestion.query.filter_by(subject_id=s.id).count()
        
        ch_ids = [ch.id for ch in Chapter.query.filter_by(subject_id=s.id).all()]
        tp_count = Topic.query.filter(Topic.chapter_id.in_(ch_ids)).count() if ch_ids else 0
        
        diff_counts = {}
        for diff in ("beginner", "intermediate", "advanced"):
            diff_counts[diff] = AssessmentQuestion.query.filter_by(
                subject_id=s.id, difficulty=diff
            ).count()
            
        rows.append({
            "subject": s,
            "chapters": ch_count,
            "topics": tp_count,
            "questions": q_count,
            "diff_counts": diff_counts,
        })
        
    total_chapters = Chapter.query.count()
    total_topics = Topic.query.count()
    total_materials = LearningMaterial.query.count()
    total_questions = AssessmentQuestion.query.count()
    total_uploaded = UploadedMaterial.query.count()
    total_documents = AcademicDocument.query.count()
    subjects_zero_q = sum(1 for r in rows if r["questions"] == 0)

    # Broken/Blank PDFs scan (< 5KB check)
    broken_pdfs = []
    cache_dir = os.path.join(current_app.root_path, "static", "cache", "pdfs")
    if os.path.exists(cache_dir):
        for f in os.listdir(cache_dir):
            if f.startswith("chapter_") and f.endswith(".pdf"):
                path = os.path.join(cache_dir, f)
                size = os.path.getsize(path)
                if size < 5000:
                    try:
                        tid = int(f.replace("chapter_", "").replace(".pdf", ""))
                        topic = Topic.query.get(tid)
                        broken_pdfs.append({
                            "filename": f,
                            "topic_id": tid,
                            "topic_name": topic.name if topic else "Unknown Topic",
                            "subject_name": topic.chapter.subject.name if topic and topic.chapter and topic.chapter.subject else "Unknown Subject",
                            "size": size
                        })
                    except Exception:
                        pass

    recent_materials = LearningMaterial.query.order_by(LearningMaterial.id.desc()).limit(5).all()
    for m in recent_materials:
        t = Topic.query.get(m.topic_id) if m.topic_id else None
        m.topic_obj = t
        m.subject_obj = t.chapter.subject if t and t.chapter else None

    return render_template(
        "admin/content/stats.html",
        rows=rows,
        total_chapters=total_chapters,
        total_topics=total_topics,
        total_materials=total_materials,
        total_questions=total_questions,
        total_uploaded=total_uploaded,
        total_documents=total_documents,
        subjects_zero_q=subjects_zero_q,
        broken_pdfs=broken_pdfs,
        recent_materials=recent_materials
    )



@admin_bp.route("/content/pdfs/regenerate/<int:topic_id>", methods=["POST"])
def content_regenerate_pdf(topic_id):
    """Delete a cached PDF so it will be regenerated on the next download request."""
    import os
    pdf_filename = f"chapter_{topic_id}.pdf"
    cache_dir = os.path.join(current_app.root_path, "static", "cache", "pdfs")
    pdf_path = os.path.join(cache_dir, pdf_filename)
    if os.path.exists(pdf_path):
        try:
            os.remove(pdf_path)
            log_admin_action("delete_cached_pdf", "Topic", topic_id, f"Deleted broken cached PDF '{pdf_filename}' for regeneration")
            flash(f"Deleted cached PDF '{pdf_filename}'. It will be generated fresh upon the next download attempt.", "success")
        except Exception as e:
            flash(f"Error removing cached PDF: {e}", "danger")
    else:
        flash("Cached PDF not found.", "warning")
    return redirect(url_for("admin.content_stats"))




# ── SECTION 2: QUESTION BANK REGENERATION ─────────────────────────────────────

@admin_bp.route("/content/questions/regenerate/<int:subject_id>", methods=["POST"])
def content_regenerate_questions(subject_id):
    """Trigger MCQ regeneration for a subject (respects daily quota)."""
    from app.models import AssessmentQuestion
    from app.routes.student import generate_assessment_questions_for_subject
    subj = SubjectModel.query.get_or_404(subject_id)
    try:
        existing = AssessmentQuestion.query.filter_by(subject_id=subject_id).count()
        generate_assessment_questions_for_subject(subject_id)
        new_count = AssessmentQuestion.query.filter_by(subject_id=subject_id).count()
        added = new_count - existing
        log_admin_action("regenerate_question_bank", "Subject", subject_id,
                         f"Regenerated MCQ bank for '{subj.name}': +{added} questions")
        flash(f"MCQ regeneration done for '{subj.name}'. +{added} new questions.", "success")
    except Exception as e:
        flash(f"Regeneration failed: {e}", "danger")
    return redirect(url_for("admin.content_stats"))


@admin_bp.route("/content/chapters/<int:subject_id>/topics")
def content_chapter_topics(subject_id):
    """List chapters and topics for a subject."""
    from app.models import Chapter, Topic
    subj = SubjectModel.query.get_or_404(subject_id)
    chapters = Chapter.query.filter_by(subject_id=subject_id).order_by(Chapter.chapter_number).all()
    topics_by_chapter = {
        ch.id: Topic.query.filter_by(chapter_id=ch.id).order_by(Topic.topic_number).all()
        for ch in chapters
    }
    return render_template("admin/content/topics.html",
                           subject=subj, chapters=chapters, topics_by_chapter=topics_by_chapter)


# ── SECTION 3: STUDENT SCHEDULE REGENERATE ────────────────────────────────────

@admin_bp.route("/students/<int:student_id>/regenerate-schedule", methods=["POST"])
def student_regenerate_schedule(student_id):
    """Clear study plan so next Planner visit regenerates it."""
    from app.models import StudyPlan, StudentProfile
    student = User.query.get_or_404(student_id)
    profile = StudentProfile.query.filter_by(user_id=student_id).first()
    if not profile:
        flash("Student has no profile.", "warning")
        return redirect(url_for("admin.student_detail", student_id=student_id))
    try:
        StudyPlan.query.filter_by(student_id=student_id).delete()
        db.session.commit()
        log_admin_action("regenerate_schedule", "User", student_id,
                         f"Cleared study plan for {student.email}")
        flash(f"Study plan cleared for {student.full_name or student.email}. "
              "Next Planner visit will regenerate it.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Could not clear schedule: {e}", "danger")
    return redirect(url_for("admin.student_detail", student_id=student_id))


# ── SECTION 4: HEALTH — API USAGE DATA ────────────────────────────────────────

def _get_daily_api_usage():
    from app.models import DailyAPIUsage
    from datetime import date as _date
    today = _date.today()
    rows = DailyAPIUsage.query.filter_by(usage_date=today).all()
    cfg = current_app.config
    limits = {
        "mcq": cfg.get("GEMINI_DAILY_LIMIT_MCQ", 450),
        "assistant": cfg.get("GEMINI_DAILY_LIMIT_ASSISTANT_PRIMARY", 45),
    }
    result = []
    for r in rows:
        limit = limits.get(r.feature)
        pct = round(r.call_count / limit * 100, 1) if limit and limit > 0 else None
        result.append({
            "feature": r.feature, "model": r.model_name or "—",
            "count": r.call_count, "limit": limit or "—", "pct": pct,
        })
    return result


# ── SECTION 5: ANALYTICS DETAIL ───────────────────────────────────────────────

@admin_bp.route("/analytics/detail")
def analytics_detail():
    from app.models import StudentProfile, StudyLog, StudentAssessment
    from sqlalchemy import func

    rf_importances = []
    try:
        from app.routes.student import load_ml_model
        model = load_ml_model("random_forest")
        if model and hasattr(model, "feature_importances_"):
            feature_names = [
                "Attendance %", "Assignment Completion %", "Weekly Study Hours",
                "Total Study Hours", "Study Days (240d)", "Subject Difficulty",
                "Avg Exam Score %", "Midterm Score %", "Final Score %",
                "Assignment Avg %", "Year of Study", "Cumulative GPA",
            ]
            combined = sorted(zip(feature_names, model.feature_importances_),
                              key=lambda x: x[1], reverse=True)
            rf_importances = [{"name": n, "importance": round(v * 100, 2)} for n, v in combined]
    except Exception:
        rf_importances = []

    try:
        total_students = User.query.filter_by(role="student", is_active=True).count()
        students_with_logs = db.session.query(StudyLog.user_id).distinct().count()
        adherence_rate = round(students_with_logs / total_students * 100, 1) if total_students else 0.0
    except Exception:
        adherence_rate = 0.0

    try:
        subjects_all = SubjectModel.query.filter_by(is_active=True).order_by(SubjectModel.name).all()
        total_assessed = StudentProfile.query.filter_by(has_completed_assessment=True).count()
        assessment_by_subject = sorted(
            [{"subject": s.name,
              "count": StudentAssessment.query.filter_by(subject_id=s.id).count()}
             for s in subjects_all[:20]],
            key=lambda x: x["count"], reverse=True,
        )
    except Exception:
        assessment_by_subject, total_assessed = [], 0

    missed_topics = []
    try:
        from app.models import AssessmentResponse, AssessmentQuestion
        wrong_counts = (
            db.session.query(
                AssessmentResponse.question_id,
                func.count(AssessmentResponse.id).label("wc"),
            )
            .filter_by(is_correct=False)
            .group_by(AssessmentResponse.question_id)
            .order_by(func.count(AssessmentResponse.id).desc())
            .limit(10)
            .all()
        )
        for qid, cnt in wrong_counts:
            q = AssessmentQuestion.query.get(qid)
            if q:
                missed_topics.append({
                    "question": q.question_text[:100],
                    "subject": q.subject.name if q.subject else "—",
                    "wrong_count": cnt,
                })
    except Exception:
        missed_topics = []

    return render_template(
        "admin/analytics_detail.html",
        rf_importances=rf_importances,
        adherence_rate=adherence_rate,
        assessment_by_subject=assessment_by_subject,
        total_assessed=total_assessed,
        missed_topics=missed_topics,
    )


# ── SECTION 7: CONFIG — STUDY PLANNER SETTINGS ────────────────────────────────

@admin_bp.route("/config/planner", methods=["POST"])
@super_admin_required
def config_planner():

    from app.models import AppSetting
    for k in ["PLANNER_SESSION_MINUTES", "PLANNER_BREAK_MINUTES", "PLANNER_SESSIONS_PER_DAY"]:
        val = request.form.get(k, "").strip()
        if not val:
            continue
        s = AppSetting.query.get(k)
        if s:
            s.value = val
        else:
            db.session.add(AppSetting(key=k, value=val))
    db.session.commit()
    from app.live_config import load_live_config
    load_live_config(current_app._get_current_object(), force=True)
    log_admin_action("update_planner_config", "AppSetting", None, "Updated Study Planner defaults")
    flash("Study Planner defaults saved.", "success")
    return redirect(url_for("admin.config"))


# ── SECTION 8: BULK-SEED QUESTION BANKS (QUEUED / RATE-LIMITED) ───────────────

import threading as _threading
_bulk_seed_state = {"running": False, "done": 0, "total": 0, "errors": [], "log": []}
_bulk_seed_lock = _threading.Lock()


@admin_bp.route("/bulk/seed-questions", methods=["GET", "POST"])
def bulk_seed_questions():
    from app.models import AssessmentQuestion
    subjects = SubjectModel.query.filter_by(is_active=True).order_by(SubjectModel.name).all()

    if request.method == "POST":
        subject_ids = request.form.getlist("subject_ids", type=int)
        if not subject_ids:
            flash("Select at least one subject.", "warning")
            return redirect(url_for("admin.bulk_seed_questions"))
        with _bulk_seed_lock:
            if _bulk_seed_state["running"]:
                flash("A bulk-seed job is already running.", "warning")
                return redirect(url_for("admin.bulk_seed_questions"))
            _bulk_seed_state.update({
                "running": True, "done": 0, "total": len(subject_ids), "errors": [], "log": [],
            })

        from flask import current_app as _ca
        _app = _ca._get_current_object()

        def _seed_worker(app, ids):
            import time as _time
            with app.app_context():
                from app.models import DailyAPIUsage, AppSetting
                from app.services.ai_service import AIService, QuotaExceededError
                from datetime import date as _d
                ai = AIService()
                for sid in ids:
                    with _bulk_seed_lock:
                        if not _bulk_seed_state["running"]:
                            break
                    subj = SubjectModel.query.get(sid)
                    if not subj:
                        with _bulk_seed_lock:
                            _bulk_seed_state["done"] += 1
                            _bulk_seed_state["errors"].append(f"Subject id={sid} not found")
                        continue
                    try:
                        today = _d.today()
                        used_row = DailyAPIUsage.query.filter_by(
                            feature="mcq", usage_date=today).first()
                        used = used_row.call_count if used_row else 0
                        limit_s = AppSetting.query.get("GEMINI_DAILY_LIMIT_MCQ")
                        limit = int(limit_s.value) if limit_s else app.config.get(
                            "GEMINI_DAILY_LIMIT_MCQ", 450)
                        if used >= limit:
                            msg = f"Daily MCQ quota exhausted ({used}/{limit}). Stopping."
                            with _bulk_seed_lock:
                                _bulk_seed_state["log"].append(msg)
                                _bulk_seed_state["running"] = False
                            break
                        existing = AssessmentQuestion.query.filter_by(subject_id=sid).count()
                        from app.routes.student import generate_assessment_questions_for_subject
                        generate_assessment_questions_for_subject(sid)
                        new_count = AssessmentQuestion.query.filter_by(subject_id=sid).count()
                        msg = f"+ {subj.name}: +{new_count - existing} questions"
                    except QuotaExceededError:
                        msg = f"- {subj.name}: daily quota hit, stopping"
                        with _bulk_seed_lock:
                            _bulk_seed_state["log"].append(msg)
                            _bulk_seed_state["running"] = False
                        break
                    except Exception as exc:
                        msg = f"- {subj.name}: {str(exc)[:80]}"
                        with _bulk_seed_lock:
                            _bulk_seed_state["errors"].append(msg)
                    with _bulk_seed_lock:
                        _bulk_seed_state["done"] += 1
                        _bulk_seed_state["log"].append(msg)
                    _time.sleep(2)
                with _bulk_seed_lock:
                    _bulk_seed_state["running"] = False

        _threading.Thread(target=_seed_worker, args=(_app, subject_ids), daemon=True).start()
        log_admin_action("bulk_seed_questions", "Subject", None,
                         f"Bulk MCQ seed: {len(subject_ids)} subjects queued")
        flash(f"Bulk seed started for {len(subject_ids)} subjects. Monitor progress below.", "info")
        return redirect(url_for("admin.bulk_seed_questions"))

    with _bulk_seed_lock:
        state = dict(_bulk_seed_state)
    q_counts = {
        s.id: AssessmentQuestion.query.filter_by(subject_id=s.id).count() for s in subjects
    }
    return render_template("admin/bulk_seed.html", subjects=subjects, state=state, q_counts=q_counts)


@admin_bp.route("/bulk/seed-questions/status")
def bulk_seed_status():
    with _bulk_seed_lock:
        return jsonify(dict(_bulk_seed_state))


@admin_bp.route("/bulk/seed-questions/stop", methods=["POST"])
def bulk_seed_stop():
    with _bulk_seed_lock:
        _bulk_seed_state["running"] = False
    flash("Bulk-seed stopped.", "warning")
    return redirect(url_for("admin.bulk_seed_questions"))


# ── SECTION 8: STUDENT DATA EXPORT ────────────────────────────────────────────

@admin_bp.route("/bulk/export-students")
def bulk_export_students():
    import csv
    import io
    from app.models import StudentProfile, StudentAssessment, StudyLog
    from flask import Response
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "user_id", "email", "full_name", "is_active", "date_registered",
        "study_level", "country", "program", "semester", "university",
        "cumulative_gpa", "attendance_pct", "has_completed_assessment",
        "target_weekly_hours", "assessment_count", "study_log_hours",
    ])
    students = User.query.filter_by(role="student").order_by(User.id).all()
    for u in students:
        p = StudentProfile.query.filter_by(user_id=u.id).first()
        a_count = StudentAssessment.query.filter_by(student_id=u.id).count()
        log_hrs = (
            db.session.query(db.func.sum(StudyLog.duration_hours))
            .filter_by(user_id=u.id).scalar() or 0.0
        )
        writer.writerow([
            u.id, u.email, u.full_name or "", u.is_active,
            u.date_registered.strftime("%Y-%m-%d") if u.date_registered else "",
            p.study_level if p else "", p.country if p else "",
            p.program if p else "", p.semester if p else "",
            p.university if p else "",
            p.cumulative_gpa if p else "", p.attendance_pct if p else "",
            p.has_completed_assessment if p else False,
            p.target_weekly_hours if p else "",
            a_count, round(float(log_hrs), 2),
        ])
    log_admin_action("export_students_csv", "User", None,
                     f"Exported {len(students)} students to CSV")
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=students_export.csv"},
    )


@admin_bp.route("/bulk/export-students-json")
def bulk_export_students_json():
    from app.models import StudentProfile, StudentAssessment, StudyLog
    students = User.query.filter_by(role="student").order_by(User.id).all()
    data = []
    for u in students:
        p = StudentProfile.query.filter_by(user_id=u.id).first()
        a_count = StudentAssessment.query.filter_by(student_id=u.id).count()
        log_hrs = (
            db.session.query(db.func.sum(StudyLog.duration_hours))
            .filter_by(user_id=u.id).scalar() or 0.0
        )
        data.append({
            "user_id": u.id, "email": u.email, "full_name": u.full_name,
            "is_active": u.is_active,
            "date_registered": u.date_registered.isoformat() if u.date_registered else None,
            "profile": {
                "study_level": p.study_level, "country": p.country,
                "program": p.program, "semester": p.semester,
                "university": p.university, "cumulative_gpa": p.cumulative_gpa,
                "attendance_pct": p.attendance_pct,
                "has_completed_assessment": p.has_completed_assessment,
                "target_weekly_hours": p.target_weekly_hours,
            } if p else None,
            "assessment_count": a_count,
            "total_study_hours": round(float(log_hrs), 2),
        })
    log_admin_action("export_students_json", "User", None,
                     f"Exported {len(students)} students to JSON")
    return jsonify(data)


# ── SECTION 8: CURRICULUM IMPORT FROM CSV ─────────────────────────────────────

@admin_bp.route("/bulk/import-curriculum", methods=["GET", "POST"])
def bulk_import_curriculum():
    import csv
    import io
    results = []
    if request.method == "POST":
        f = request.files.get("csv_file")
        if not f or not f.filename.lower().endswith(".csv"):
            flash("Please upload a .csv file.", "danger")
            return redirect(url_for("admin.bulk_import_curriculum"))
        stream = io.StringIO(f.stream.read().decode("utf-8-sig"), newline=None)
        reader = csv.DictReader(stream)
        added = skipped = 0
        for row in reader:
            name = (row.get("name") or "").strip()
            if not name:
                continue
            code = (row.get("code") or "").strip() or None
            level = (row.get("level_of_study") or "").strip()
            program = (row.get("program") or "").strip() or None
            semester = (row.get("semester") or "").strip() or None
            try:
                credit_hours = int(row.get("credit_hours") or 3)
                difficulty = int(row.get("difficulty_level") or 3)
            except ValueError:
                credit_hours, difficulty = 3, 3
            exists = SubjectModel.query.filter_by(name=name, level_of_study=level).first()
            if exists:
                results.append({"name": name, "status": "skipped (duplicate)"})
                skipped += 1
                continue
            db.session.add(SubjectModel(
                name=name, code=code, level_of_study=level,
                program=program, semester=semester,
                credit_hours=credit_hours, difficulty_level=difficulty,
                country="Nepal", curriculum="National", is_active=True,
            ))
            results.append({"name": name, "status": "added"})
            added += 1
        db.session.commit()
        log_admin_action("import_curriculum_csv", "Subject", None,
                         f"CSV import: {added} added, {skipped} skipped")
        flash(f"Import complete: {added} subjects added, {skipped} skipped.", "success")
    return render_template("admin/bulk_import.html", results=results)


# ── SECTION 9: UNIFIED GLOBAL SEARCH & ADMIN PROFILE ────────────────────────────

@admin_bp.route("/search")
def search():
    """Unified Global Admin Search across Students, Programs, Subjects, Chapters, Topics, Materials, Universities, Faculties."""
    from app.models import (
        User, StudentProfile, CurriculumProgram, Subject as SubjectModel,
        Chapter, Topic, LearningMaterial, University, Faculty
    )

    q = request.args.get("q", "").strip()
    category = request.args.get("category", "all").strip()

    results = {
        "students": [],
        "programs": [],
        "subjects": [],
        "chapters": [],
        "topics": [],
        "materials": [],
        "universities": [],
        "faculties": [],
    }
    total_matches = 0

    if q and len(q) >= 2:
        wildcard = f"%{q}%"

        # 1. Students
        if category in ("all", "students"):
            student_users = User.query.filter(
                User.role == "student",
                (User.full_name.ilike(wildcard)) | (User.email.ilike(wildcard))
            ).limit(10).all()
            for u in student_users:
                p = StudentProfile.query.filter_by(user_id=u.id).first()
                results["students"].append({
                    "id": u.id,
                    "name": u.full_name or u.email,
                    "email": u.email,
                    "level": p.study_level if p else "Unassigned",
                    "url": url_for("admin.student_detail", student_id=u.id)
                })

        # 2. Programs
        if category in ("all", "programs"):
            progs = CurriculumProgram.query.filter(
                CurriculumProgram.name.ilike(wildcard)
            ).limit(10).all()
            for p in progs:
                results["programs"].append({
                    "id": p.id,
                    "name": p.name,
                    "code": "",
                    "level": p.education_level.name if p.education_level else "",
                    "url": url_for("admin.curriculum_program_detail", program_id=p.id)
                })


        # 3. Subjects
        if category in ("all", "subjects"):
            subjs = SubjectModel.query.filter(
                (SubjectModel.name.ilike(wildcard)) | (SubjectModel.code.ilike(wildcard))
            ).limit(10).all()
            for s in subjs:
                results["subjects"].append({
                    "id": s.id,
                    "name": s.name,
                    "code": s.code or "",
                    "level": s.level_of_study or "",
                    "url": url_for("admin.curriculum_subjects", q=s.name)
                })

        # 4. Chapters
        if category in ("all", "chapters"):
            chaps = Chapter.query.filter(Chapter.name.ilike(wildcard)).limit(10).all()
            for c in chaps:
                results["chapters"].append({
                    "id": c.id,
                    "name": c.name,
                    "chapter_number": c.chapter_number,
                    "subject": c.subject.name if c.subject else "",
                    "url": url_for("admin.content_chapters", subject_id=c.subject_id) if c.subject_id else url_for("admin.content_chapters")
                })

        # 5. Topics
        if category in ("all", "topics"):
            topcs = Topic.query.filter(Topic.name.ilike(wildcard)).limit(10).all()
            for t in topcs:
                results["topics"].append({
                    "id": t.id,
                    "name": t.name,
                    "chapter": t.chapter.name if t.chapter else "",
                    "url": url_for("admin.content_materials", q=t.name)
                })

        # 6. Learning Materials
        if category in ("all", "materials"):
            mats = LearningMaterial.query.filter(
                (LearningMaterial.title.ilike(wildcard)) | (LearningMaterial.introduction.ilike(wildcard))
            ).limit(10).all()
            for m in mats:
                t_obj = Topic.query.get(m.topic_id) if m.topic_id else None
                sub_name = t_obj.chapter.subject.name if (t_obj and t_obj.chapter and t_obj.chapter.subject) else ""
                results["materials"].append({
                    "id": m.id,
                    "title": m.title or "Untitled Material",
                    "topic": t_obj.name if t_obj else "",
                    "subject": sub_name,
                    "url": url_for("admin.content_material_preview", material_id=m.id)
                })


        # 7. Universities
        if category in ("all", "universities"):
            unis = University.query.filter(
                (University.name.ilike(wildcard)) | (University.country.ilike(wildcard))
            ).limit(10).all()
            for u in unis:
                results["universities"].append({
                    "id": u.id,
                    "name": u.name,
                    "country": u.country or "",
                    "url": url_for("admin.curriculum_universities")
                })

        # 8. Faculties
        if category in ("all", "faculties"):
            facs = Faculty.query.filter(Faculty.name.ilike(wildcard)).limit(10).all()
            for f in facs:
                results["faculties"].append({
                    "id": f.id,
                    "name": f.name,
                    "university": f.university.name if f.university else "",
                    "url": url_for("admin.curriculum_faculties")
                })

        total_matches = sum(len(v) for v in results.values())

    return render_template(
        "admin/search.html",
        q=q,
        category=category,
        results=results,
        total_matches=total_matches
    )


@admin_bp.route("/profile", methods=["GET", "POST"])
def profile():
    """Admin Profile & Account Security Management."""
    from app.models import AdminActivityLog, User
    from app import bcrypt, db
    from werkzeug.security import check_password_hash, generate_password_hash
    import re

    if request.method == "POST":
        action_type = request.form.get("action_type")

        if action_type == "change_password":
            current_pw = request.form.get("current_password", "").strip()
            new_pw = request.form.get("new_password", "").strip()
            confirm_pw = request.form.get("confirm_password", "").strip()

            # 1. Verify current password
            if not current_user.password_hash:
                flash("Admin password hash is not configured.", "danger")
                return redirect(url_for("admin.profile"))

            # Check password hash using bcrypt or Werkzeug
            valid_pw = False
            try:
                valid_pw = bcrypt.check_password_hash(current_user.password_hash, current_pw)
            except Exception:
                try:
                    valid_pw = check_password_hash(current_user.password_hash, current_pw)
                except Exception:
                    valid_pw = False

            if not valid_pw:
                flash("Current password verification failed. Please check your password and try again.", "danger")
                return redirect(url_for("admin.profile"))

            # 2. Check confirmation match
            if new_pw != confirm_pw:
                flash("New password and confirmation password do not match.", "danger")
                return redirect(url_for("admin.profile"))

            # 3. Strong password validation (min 8 chars, uppercase, lowercase, number)
            if len(new_pw) < 8 or not re.search(r"[A-Z]", new_pw) or not re.search(r"[a-z]", new_pw) or not re.search(r"[0-9]", new_pw):
                flash("New password must be at least 8 characters long and include uppercase letters, lowercase letters, and numbers.", "danger")
                return redirect(url_for("admin.profile"))

            # 4. Hash new password & save
            try:
                current_user.password_hash = bcrypt.generate_password_hash(new_pw).decode("utf-8")
            except Exception:
                current_user.password_hash = generate_password_hash(new_pw)

            db.session.commit()

            # 5. Log action without credentials
            log_admin_action("change_admin_password", "User", current_user.id, f"Updated admin password for account {current_user.email} (ID {current_user.id})")
            flash("Admin password updated successfully! Please use your new password for future logins.", "success")
            return redirect(url_for("admin.profile"))

    # Recent activity logs specific to this admin
    recent_logs = AdminActivityLog.query.filter_by(admin_user_id=current_user.id).order_by(AdminActivityLog.timestamp.desc()).limit(10).all()

    return render_template(
        "admin/profile.html",
        recent_logs=recent_logs
    )


@admin_bp.route("/ml/retrain", methods=["POST"])
def admin_retrain_ml():
    from app.services.ml_service import retrain_level_models
    try:
        results = retrain_level_models()
        log_admin_action("retrain_ml_models", "MLModels", None, "Retrained Random Forest models across all academic levels.")
        return jsonify({"status": "success", "results": results}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ── SUPER ADMIN: ADMIN MANAGEMENT & APPROVAL WORKFLOW ───────────────────────

@admin_bp.route("/manage-admins")
@super_admin_required
def manage_admins():
    """
    Super Admin Management Area:
    View all Regular Admins, Pending Admin Requests, Approval Actions, and Audit Logs.
    """
    pending_requests = AdminRegistrationRequest.query.filter_by(status="PENDING").order_by(AdminRegistrationRequest.created_at.desc()).all()
    processed_requests = AdminRegistrationRequest.query.filter(AdminRegistrationRequest.status.in_(["APPROVED", "REJECTED"])).order_by(AdminRegistrationRequest.actioned_at.desc()).limit(20).all()
    
    # Regular Admins (excluding Primary Super Admin)
    regular_admins = User.query.filter(User.role == 'admin').order_by(User.date_registered.desc()).all()
    
    # Super Admin account inspection
    primary_super_admin = User.query.filter(db.func.lower(User.email) == SUPER_ADMIN_EMAIL.lower()).first()

    return render_template(
        "admin/manage_admins.html",
        pending_requests=pending_requests,
        processed_requests=processed_requests,
        regular_admins=regular_admins,
        primary_super_admin=primary_super_admin,
        super_admin_email=SUPER_ADMIN_EMAIL
    )

@admin_bp.route("/requests")
@super_admin_required
def admin_requests():
    return redirect(url_for("admin.manage_admins"))


@admin_bp.route("/requests/<int:req_id>/approve", methods=["POST"])
@super_admin_required
def approve_admin_request(req_id):
    """
    Super Admin approval of an Admin Registration Request.
    Generates a secure 6-digit single-use verification code valid for 24 hours
    and dispatches it to the applicant's personal email.
    """
    req = AdminRegistrationRequest.query.get_or_404(req_id)
    if req.status != 'PENDING':
        flash(f"Request for {req.email} has already been processed (status: {req.status}).", "warning")
        return redirect(url_for("admin.manage_admins"))

    import secrets
    code = "".join(secrets.choice("0123456789") for _ in range(6))
    now = datetime.utcnow()
    expires = now + timedelta(hours=24)

    req.status = 'APPROVED'
    req.verification_code = code
    req.code_expires_at = expires
    req.code_used = False
    req.actioned_at = now
    req.actioned_by_id = current_user.id
    db.session.commit()

    # Log in AdminActivityLog
    log_admin_action(
        "approved_admin_request",
        "AdminRegistrationRequest",
        req.id,
        f"Super Admin approved Regular Admin request for {req.full_name} ({req.email}). Verification code generated (valid 24h)."
    )

    # Email 24-hour verification code to applicant's personal email
    from flask_mail import Message
    from app import mail
    try:
        msg = Message(
            subject="Admin Account Approved - Smart Study Verification Code",
            recipients=[req.email],
            body=(
                f"Hello {req.full_name},\n\n"
                f"Your Admin Registration Request for Smart Study has been APPROVED by the Super Admin!\n\n"
                f"Your single-use 24-hour verification code is:\n\n"
                f"   {code}\n\n"
                f"Please visit the verification page to activate your Regular Admin account:\n"
                f"{url_for('auth.verify_admin_code', email=req.email, _external=True)}\n\n"
                f"This code will expire in 24 hours. If you did not request this, please ignore."
            )
        )
        mail.send(msg)
        flash(f"Admin request for '{req.full_name}' ({req.email}) APPROVED! Single-use 24-hour verification code emailed to applicant.", "success")
    except Exception as e:
        flash(f"Admin request APPROVED, but failed to send verification email to {req.email}: {e}", "warning")

    return redirect(url_for("admin.manage_admins"))


@admin_bp.route("/requests/<int:req_id>/reject", methods=["POST"])
@super_admin_required
def reject_admin_request(req_id):
    """
    Super Admin rejection of an Admin Registration Request.
    """
    req = AdminRegistrationRequest.query.get_or_404(req_id)
    req.status = 'REJECTED'
    req.actioned_at = datetime.utcnow()
    req.actioned_by_id = current_user.id
    db.session.commit()

    log_admin_action(
        "rejected_admin_request",
        "AdminRegistrationRequest",
        req.id,
        f"Super Admin rejected Regular Admin request for {req.full_name} ({req.email})."
    )
    flash(f"Admin registration request for '{req.full_name}' ({req.email}) REJECTED.", "info")
    return redirect(url_for("admin.manage_admins"))


@admin_bp.route("/admins/<int:user_id>/disable", methods=["POST"])
@super_admin_required
def disable_regular_admin(user_id):
    """Disable a Regular Admin account."""
    target_user = User.query.get_or_404(user_id)
    if is_protected_primary_super_admin(target_user):
        flash("CRITICAL GUARD: Primary Super Admin (hemantsah123456789@gmail.com) CANNOT be disabled or modified!", "danger")
        return redirect(url_for("admin.manage_admins"))

    target_user.is_active = False
    db.session.commit()

    log_admin_action("disabled_regular_admin", "User", user_id, f"Super Admin disabled Regular Admin {target_user.email} (ID {user_id})")
    flash(f"Regular Admin account '{target_user.email}' disabled successfully.", "warning")
    return redirect(url_for("admin.manage_admins"))


@admin_bp.route("/admins/<int:user_id>/reactivate", methods=["POST"])
@super_admin_required
def reactivate_regular_admin(user_id):
    """Reactivate a Regular Admin account."""
    target_user = User.query.get_or_404(user_id)
    target_user.is_active = True
    db.session.commit()

    log_admin_action("reactivated_regular_admin", "User", user_id, f"Super Admin reactivated Regular Admin {target_user.email} (ID {user_id})")
    flash(f"Regular Admin account '{target_user.email}' reactivated successfully.", "success")
    return redirect(url_for("admin.manage_admins"))


# ── SUPER ADMIN-ONLY PERMANENT DELETION ENDPOINTS (7 TOTAL) ────────────────

@admin_bp.route("/admins/<int:user_id>/delete-permanent", methods=["POST"])
@super_admin_required
def delete_permanent_admin(user_id):
    """Permanently delete a Regular Admin account (Super Admin Only)."""
    target_user = User.query.get_or_404(user_id)
    if is_protected_primary_super_admin(target_user):
        flash("CRITICAL GUARD: Primary Super Admin (hemantsah123456789@gmail.com) CANNOT be deleted under any circumstances!", "danger")
        return redirect(url_for("admin.manage_admins"))

    confirm_text = request.form.get("confirm_text", "").strip().lower()
    if confirm_text != target_user.email.strip().lower():
        flash(f"Confirmation string mismatch. Expected '{target_user.email}', received '{confirm_text}'. Permanent deletion aborted.", "danger")
        return redirect(url_for("admin.manage_admins"))

    try:
        deleted_email = target_user.email
        db.session.delete(target_user)
        db.session.commit()
        log_admin_action("permanently_deleted_admin", "User", user_id, f"Super Admin permanently deleted Regular Admin {deleted_email} (ID {user_id})")
        flash(f"Regular Admin '{deleted_email}' permanently deleted.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Failed to permanently delete admin: {e}", "danger")

    return redirect(url_for("admin.manage_admins"))


@admin_bp.route("/students/<int:student_id>/delete-permanent", methods=["POST"])
@super_admin_required
def delete_permanent_student(student_id):
    """Permanently delete a Student account and associated records (Super Admin Only)."""
    student = User.query.filter_by(id=student_id, role='student').first_or_404()
    if is_protected_primary_super_admin(student):
        flash("CRITICAL GUARD: Primary Super Admin account cannot be deleted!", "danger")
        return redirect(url_for("admin.students"))

    confirm_text = request.form.get("confirm_text", "").strip().lower()
    if confirm_text != student.email.strip().lower():
        flash(f"Confirmation email mismatch. Expected '{student.email}', received '{confirm_text}'. Permanent deletion aborted.", "danger")
        return redirect(url_for("admin.student_detail", student_id=student_id))

    try:
        import os
        from app.models import (
            StudentProfile, StudentSubject, Prediction, StudyLog, Assignment,
            Exam, Schedule, Recommendation, Goal, AvailabilitySlot, StudentSeenQuestion,
            StudyPlan, AcademicDocument, ExtractedMark, StudentAssessment, AssessmentResponse,
            UploadedMaterial, MaterialChunk, MaterialImportBatch, MaterialImportUnmatched,
            ModuleDescriptor, FlashcardReview, SubjectBook, QuizScore, StudyLogAnalysis,
            LearningProgress, StudentNote, SubjectPerformanceHistory, AIStudyMaterial,
            ReviewedChapter, ChapterQuizScore, ChapterQuizResult, TopicSeenQuestion,
            BookmarkedChapter, ChapterNote, Notification
        )

        # 1. Clean up UploadedMaterial & MaterialChunks & physical files & ModuleDescriptors
        materials = UploadedMaterial.query.filter_by(user_id=student_id).all()
        for m in materials:
            MaterialChunk.query.filter_by(material_id=m.id).delete()
            ModuleDescriptor.query.filter_by(source_material_id=m.id).delete()
            if m.file_path and os.path.exists(m.file_path):
                try:
                    os.remove(m.file_path)
                except Exception:
                    pass
            db.session.delete(m)

        # Clean up any remaining MaterialChunk by user_id
        MaterialChunk.query.filter_by(user_id=student_id).delete()
        ModuleDescriptor.query.filter_by(user_id=student_id).delete()

        # 2. Clean up MaterialImportBatches & Unmatched
        batches = MaterialImportBatch.query.filter_by(user_id=student_id).all()
        for b in batches:
            MaterialImportUnmatched.query.filter_by(batch_id=b.id).delete()
            if b.stored_zip_path and os.path.exists(b.stored_zip_path):
                try:
                    os.remove(b.stored_zip_path)
                except Exception:
                    pass
            db.session.delete(b)

        # 3. Clean up AcademicDocuments & physical files
        docs = AcademicDocument.query.filter_by(student_id=student_id).all()
        for d in docs:
            ExtractedMark.query.filter_by(document_id=d.id).delete()
            if d.file_path and os.path.exists(d.file_path):
                try:
                    os.remove(d.file_path)
                except Exception:
                    pass
            db.session.delete(d)

        # 4. Clean up Assessments & Quiz Scores
        assessments = StudentAssessment.query.filter_by(student_id=student_id).all()
        for a in assessments:
            AssessmentResponse.query.filter_by(assessment_id=a.id).delete()
            db.session.delete(a)

        quiz_scores = ChapterQuizScore.query.filter_by(student_id=student_id).all()
        for qs in quiz_scores:
            ChapterQuizResult.query.filter_by(quiz_score_id=qs.id).delete()
            db.session.delete(qs)

        ChapterQuizResult.query.filter_by(student_id=student_id).delete()
        QuizScore.query.filter_by(user_id=student_id).delete()

        # 5. Clean up Flashcard Reviews, Books, Learning Progress, Notes
        FlashcardReview.query.filter_by(user_id=student_id).delete()
        SubjectBook.query.filter_by(user_id=student_id).delete()
        StudyLogAnalysis.query.filter_by(user_id=student_id).delete()
        LearningProgress.query.filter_by(user_id=student_id).delete()
        StudentNote.query.filter_by(user_id=student_id).delete()
        SubjectPerformanceHistory.query.filter_by(user_id=student_id).delete()
        AIStudyMaterial.query.filter_by(user_id=student_id).delete()
        ReviewedChapter.query.filter_by(student_id=student_id).delete()
        TopicSeenQuestion.query.filter_by(student_id=student_id).delete()
        BookmarkedChapter.query.filter_by(student_id=student_id).delete()
        ChapterNote.query.filter_by(student_id=student_id).delete()

        # 6. Clean up Core Planner & Profile Records
        StudentProfile.query.filter_by(user_id=student_id).delete()
        StudentSubject.query.filter_by(user_id=student_id).delete()
        Prediction.query.filter_by(user_id=student_id).delete()
        StudyLog.query.filter_by(user_id=student_id).delete()
        Assignment.query.filter_by(user_id=student_id).delete()
        Exam.query.filter_by(user_id=student_id).delete()
        Schedule.query.filter_by(user_id=student_id).delete()
        Recommendation.query.filter_by(user_id=student_id).delete()
        Goal.query.filter_by(user_id=student_id).delete()
        Notification.query.filter_by(user_id=student_id).delete()
        AvailabilitySlot.query.filter_by(user_id=student_id).delete()
        StudentSeenQuestion.query.filter_by(student_id=student_id).delete()
        StudyPlan.query.filter_by(student_id=student_id).delete()

        email_deleted = student.email
        db.session.delete(student)
        db.session.commit()

        log_admin_action("permanently_deleted_student", "User", student_id, f"Super Admin permanently deleted Student account {email_deleted} (ID {student_id})")
        flash(f"Student account '{email_deleted}' and all associated records permanently deleted.", "success")
        return redirect(url_for("admin.students"))
    except Exception as e:
        db.session.rollback()
        flash(f"Failed to permanently delete student: {e}", "danger")
        return redirect(url_for("admin.student_detail", student_id=student_id))


@admin_bp.route("/curriculum/levels/<int:level_id>/delete-permanent", methods=["POST"])
@super_admin_required
def delete_permanent_level(level_id):
    """Permanently delete an Education Level record (Super Admin Only)."""
    level = EducationLevel.query.get_or_404(level_id)
    confirm_text = request.form.get("confirm_text", "").strip()
    if confirm_text != level.name:
        flash(f"Confirmation name mismatch. Expected '{level.name}', received '{confirm_text}'. Permanent deletion aborted.", "danger")
        return redirect(url_for("admin.curriculum_levels"))

    # Safety check: student usage
    usage_count = StudentProfile.query.filter_by(study_level=level.name).count()
    if usage_count > 0:
        flash(f"Deletion blocked: {usage_count} active student profile(s) rely on Education Level '{level.name}'. Reassign students before permanently deleting.", "danger")
        return redirect(url_for("admin.curriculum_levels"))

    try:
        lvl_name = level.name
        db.session.delete(level)
        db.session.commit()
        log_admin_action("permanently_deleted_level", "EducationLevel", level_id, f"Super Admin permanently deleted Education Level '{lvl_name}' (ID {level_id})")
        flash(f"Education Level '{lvl_name}' permanently deleted.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Failed to delete Education Level: {e}", "danger")

    return redirect(url_for("admin.curriculum_levels"))


@admin_bp.route("/curriculum/universities/<int:uni_id>/delete-permanent", methods=["POST"])
@super_admin_required
def delete_permanent_university(uni_id):
    """Permanently delete a University record (Super Admin Only)."""
    uni = University.query.get_or_404(uni_id)
    confirm_text = request.form.get("confirm_text", "").strip()
    if confirm_text != uni.name:
        flash(f"Confirmation name mismatch. Expected '{uni.name}', received '{confirm_text}'. Permanent deletion aborted.", "danger")
        return redirect(url_for("admin.curriculum_universities"))

    usage_count = StudentProfile.query.filter(StudentProfile.university.like(f"{uni.name}%")).count()
    if usage_count > 0:
        flash(f"Deletion blocked: {usage_count} student profile(s) reference University '{uni.name}'.", "danger")
        return redirect(url_for("admin.curriculum_universities"))

    try:
        u_name = uni.name
        db.session.delete(uni)
        db.session.commit()
        log_admin_action("permanently_deleted_university", "University", uni_id, f"Super Admin permanently deleted University '{u_name}' (ID {uni_id})")
        flash(f"University '{u_name}' permanently deleted.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Failed to delete University: {e}", "danger")

    return redirect(url_for("admin.curriculum_universities"))


@admin_bp.route("/curriculum/faculties/<int:fac_id>/delete-permanent", methods=["POST"])
@super_admin_required
def delete_permanent_faculty(fac_id):
    """Permanently delete a Faculty/Stream record (Super Admin Only)."""
    fac = Faculty.query.get_or_404(fac_id)
    confirm_text = request.form.get("confirm_text", "").strip()
    if confirm_text != fac.name:
        flash(f"Confirmation name mismatch. Expected '{fac.name}', received '{confirm_text}'. Permanent deletion aborted.", "danger")
        return redirect(url_for("admin.curriculum_faculties"))

    try:
        f_name = fac.name
        db.session.delete(fac)
        db.session.commit()
        log_admin_action("permanently_deleted_faculty", "Faculty", fac_id, f"Super Admin permanently deleted Faculty '{f_name}' (ID {fac_id})")
        flash(f"Faculty/Stream '{f_name}' permanently deleted.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Failed to delete Faculty: {e}", "danger")

    return redirect(url_for("admin.curriculum_faculties"))


@admin_bp.route("/curriculum/programs/<int:program_id>/delete-permanent", methods=["POST"])
@super_admin_required
def delete_permanent_program(program_id):
    """Permanently delete an Academic Program record (Super Admin Only)."""
    prog = CurriculumProgram.query.get_or_404(program_id)
    confirm_text = request.form.get("confirm_text", "").strip()
    if confirm_text != prog.name:
        flash(f"Confirmation name mismatch. Expected '{prog.name}', received '{confirm_text}'. Permanent deletion aborted.", "danger")
        return redirect(url_for("admin.curriculum_programs"))

    try:
        p_name = prog.name
        ProgramSubject.query.filter_by(program_id=program_id).delete()
        db.session.delete(prog)
        db.session.commit()
        log_admin_action("permanently_deleted_program", "CurriculumProgram", program_id, f"Super Admin permanently deleted Academic Program '{p_name}' (ID {program_id})")
        flash(f"Academic Program '{p_name}' permanently deleted.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Failed to delete Academic Program: {e}", "danger")

    return redirect(url_for("admin.curriculum_programs"))


@admin_bp.route("/curriculum/subjects/<int:subject_id>/delete-permanent", methods=["POST"])
@super_admin_required
def delete_permanent_subject(subject_id):
    """Permanently delete a Master Subject record (Super Admin Only)."""
    subj = Subject.query.get_or_404(subject_id)
    confirm_text = request.form.get("confirm_text", "").strip()
    if confirm_text != subj.name:
        flash(f"Confirmation name mismatch. Expected '{subj.name}', received '{confirm_text}'. Permanent deletion aborted.", "danger")
        return redirect(url_for("admin.curriculum_subjects"))

    try:
        from app.models import Chapter, Topic, AssessmentQuestion, LearningMaterial
        s_name = subj.name
        
        StudentSubject.query.filter_by(subject_id=subject_id).delete()
        ProgramSubject.query.filter_by(subject_id=subject_id).delete()

        chapters = Chapter.query.filter_by(subject_id=subject_id).all()
        for ch in chapters:
            topics = Topic.query.filter_by(chapter_id=ch.id).all()
            for tp in topics:
                AssessmentQuestion.query.filter_by(topic_id=tp.id).delete()
                LearningMaterial.query.filter_by(topic_id=tp.id).delete()
                db.session.delete(tp)
            db.session.delete(ch)

        AssessmentQuestion.query.filter_by(subject_id=subject_id).delete()
        db.session.delete(subj)
        db.session.commit()

        log_admin_action("permanently_deleted_subject", "Subject", subject_id, f"Super Admin permanently deleted Master Subject '{s_name}' (ID {subject_id})")
        flash(f"Master Subject '{s_name}' permanently deleted.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Failed to delete Master Subject: {e}", "danger")

    return redirect(url_for("admin.curriculum_subjects"))



