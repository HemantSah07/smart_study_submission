from datetime import datetime
from flask_login import UserMixin
from app import db, login_manager

@login_manager.user_loader
def load_user(user_id):
    from flask import session, request
    try:
        impersonate_id = session.get('impersonating_student_id')
        print(f"[DEBUG load_user] path={request.path} user_id={user_id} impersonate_id={impersonate_id}")
        if impersonate_id:
            # Only load the student when accessing non-admin endpoints
            if not request.path.startswith('/admin'):
                student = User.query.get(int(impersonate_id))
                if student:
                    print(f"[DEBUG load_user] IMPERSONATING returned student {student.id}")
                    return student
    except Exception as e:
        print("[DEBUG load_user] exception:", e)
        pass
    u = User.query.get(int(user_id))
    print(f"[DEBUG load_user] returned user {u.id if u else None} (role={u.role if u else None})")
    return u

SUPER_ADMIN_EMAIL = "hemantsah123456789@gmail.com"

class User(db.Model, UserMixin):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=False, nullable=True) # Made nullable for CSV users
    full_name = db.Column(db.String(100))
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="student") # student, admin, super_admin
    is_active = db.Column(db.Boolean, default=True)
    date_registered = db.Column(db.DateTime, default=datetime.utcnow)
    email_verified_status = db.Column(db.String(32), default='unknown')
    # Seed accounts created by load_data.py cannot log in regardless of password.
    # Only accounts created via create_admin.py or real registration have this False.
    is_seed_account = db.Column(db.Boolean, default=False, nullable=False)

    @property
    def is_protected_super_admin(self):
        return bool(self.email and self.email.strip().lower() == SUPER_ADMIN_EMAIL.lower())

    @property
    def is_super_admin(self):
        return self.is_protected_super_admin or self.role == 'super_admin'

    @property
    def is_admin(self):
        return self.is_super_admin or self.role in ['admin', 'super_admin']

    @property
    def profile(self):
        from app.models import StudentProfile
        return StudentProfile.query.filter_by(user_id=self.id).first()


class StudentProfile(db.Model):
    __tablename__ = "student_profiles"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    student_number = db.Column(db.String(20), unique=True)
    program = db.Column(db.String(100))
    year_of_study = db.Column(db.Integer)
    cumulative_gpa = db.Column(db.Float)
    has_completed_assessment = db.Column(db.Boolean, default=False)
    prior_academic_score = db.Column(db.Float, default=0.0)
    documents_uploaded = db.Column(db.Integer, default=0)
    academic_level = db.Column(db.String(20), default='average') # weak, average, good, excellent
    level_of_study = db.Column(db.String(50))
    semester = db.Column(db.String(50))
    study_level = db.Column(db.String(50), nullable=True, default='Class 9')
    university = db.Column(db.String(100), nullable=True)
    
    # Universal additions
    country = db.Column(db.String(100), default="Nepal")
    timezone = db.Column(db.String(64), default="Asia/Kathmandu")
    curriculum = db.Column(db.String(100), default="National")
    learning_style = db.Column(db.String(50), default="Mixed")
    explanation_level = db.Column(db.String(50), default="Intermediate")
    response_length = db.Column(db.String(50), default="Medium")
    quiz_difficulty = db.Column(db.String(50), default="Medium")
    study_goal = db.Column(db.String(100), default="Improve Grades")
    preferred_language = db.Column(db.String(50), default="English")
    profile_pic = db.Column(db.String(200))
    target_weekly_hours = db.Column(db.Float, default=20.0)
    commute_buffer_minutes = db.Column(db.Integer, default=0)
    attendance_pct = db.Column(db.Float, default=85.0)  # Student's actual attendance percentage (0–100)
    target_score_goal = db.Column(db.Float, default=70.0)   # Desired academic percentage (contextual only)
    peak_focus_time = db.Column(db.String(20), default="Morning")  # Morning/Afternoon/Evening/Night
    program_duration = db.Column(db.String(20), nullable=True)     # e.g. "3 Years", "4 Years" (Bachelors only)
    university_type = db.Column(db.String(50), nullable=True)      # e.g. "National", "Foreign"
    university_country = db.Column(db.String(100), nullable=True)   # e.g. "United Kingdom", "Malaysia"


# ── Curriculum Taxonomy (Section 1: Admin Curriculum Management) ─────────────

class EducationLevel(db.Model):
    """
    Canonical education levels (Class 6 … Class 12, Bachelors, Masters).
    Replaces the hardcoded LEVEL_OPTIONS in profile-fields.js.
    """
    __tablename__ = "education_levels"
    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(50), nullable=False)   # e.g. "Class 10", "Bachelors"
    country     = db.Column(db.String(100), nullable=False, default="Nepal")
    sort_order  = db.Column(db.Integer, nullable=False, default=0)
    is_active   = db.Column(db.Boolean, nullable=False, default=True)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    deleted_at  = db.Column(db.DateTime, nullable=True)          # soft-delete timestamp
    deleted_by  = db.Column(db.Integer, nullable=True)           # admin user_id who deactivated
    __table_args__ = (db.UniqueConstraint("name", "country", name="uq_education_level_name_country"),)


class University(db.Model):
    """
    Universities shown in profile / registration for Bachelors / Masters.
    Replaces the hardcoded university list in templates.
    """
    __tablename__ = "universities"
    id           = db.Column(db.Integer, primary_key=True)
    name         = db.Column(db.String(150), nullable=False)
    abbreviation = db.Column(db.String(30), nullable=True)
    country      = db.Column(db.String(100), nullable=False, default="Nepal")
    is_active    = db.Column(db.Boolean, nullable=False, default=True)
    sort_order   = db.Column(db.Integer, nullable=False, default=0)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)
    deleted_at   = db.Column(db.DateTime, nullable=True)
    deleted_by   = db.Column(db.Integer, nullable=True)
    __table_args__ = (db.UniqueConstraint("name", "country", name="uq_university_name_country"),)


class Faculty(db.Model):
    """
    Faculties / streams shown for Class 11, Class 12 (NEB).
    Replaces NEB_GENERAL_FACULTIES and NEB_TECHNICAL_STREAMS in profile-fields.js.
    """
    __tablename__ = "faculties"
    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(150), nullable=False)
    country     = db.Column(db.String(100), nullable=False, default="Nepal")
    level_name  = db.Column(db.String(50), nullable=True)   # e.g. "Class 11", "Class 12"; NULL = all
    is_active   = db.Column(db.Boolean, nullable=False, default=True)
    sort_order  = db.Column(db.Integer, nullable=False, default=0)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    deleted_at  = db.Column(db.DateTime, nullable=True)
    deleted_by  = db.Column(db.Integer, nullable=True)


class CurriculumProgram(db.Model):
    """
    Bachelors / Masters programs (BBA, BCA, BSc IT …).
    Replaces NEPAL_BACHELORS_PROGRAMS / NEPAL_MASTERS_PROGRAMS in profile-fields.js.
    has_duration = True means the Program Duration dropdown should appear.
    duration_options_json = JSON list of {value, label} objects.
    """
    __tablename__ = "curriculum_programs"
    id                   = db.Column(db.Integer, primary_key=True)
    name                 = db.Column(db.String(150), nullable=False)
    level_name           = db.Column(db.String(50), nullable=False)  # "Bachelors" or "Masters"
    country              = db.Column(db.String(100), nullable=False, default="Nepal")
    has_duration         = db.Column(db.Boolean, nullable=False, default=False)
    duration_options_json= db.Column(db.Text, nullable=True)  # JSON: [{"value":"3 Years","label":"..."}]
    is_active            = db.Column(db.Boolean, nullable=False, default=True)
    sort_order           = db.Column(db.Integer, nullable=False, default=0)
    created_at           = db.Column(db.DateTime, default=datetime.utcnow)
    deleted_at           = db.Column(db.DateTime, nullable=True)
    deleted_by           = db.Column(db.Integer, nullable=True)
    __table_args__ = (db.UniqueConstraint("name", "level_name", "country", name="uq_program_name_level_country"),)


class ProgramSubject(db.Model):
    """
    Many-to-many association between CurriculumProgram and Subject.

    A single global Subject can be shared by multiple Programs (e.g. Mathematics
    used by BSc CSIT, BSc IT Core, and BSc IT Cloud simultaneously).

    Detaching a subject ONLY removes/deactivates this mapping row.
    The global Subject record is NEVER deleted via this mechanism.

    Fields:
        semester   - where in the program the subject appears (e.g. "Semester 1")
        term       - optional sub-grouping (e.g. "Core", "Elective", "Dissertation")
        sort_order - display order within that semester (program-specific)
        is_active  - soft-disable mapping without touching the global Subject
        deleted_at / deleted_by - soft-delete audit trail
    """
    __tablename__ = "program_subjects"
    id         = db.Column(db.Integer, primary_key=True)
    program_id = db.Column(db.Integer, db.ForeignKey('curriculum_programs.id', ondelete='CASCADE'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id', ondelete='RESTRICT'), nullable=False)
    semester   = db.Column(db.String(50), nullable=True)    # e.g. "Semester 1", "Core"
    term       = db.Column(db.String(50), nullable=True)    # optional sub-grouping
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    is_active  = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    deleted_at = db.Column(db.DateTime, nullable=True)
    deleted_by = db.Column(db.Integer, nullable=True)

    # Relationships — read-only joins for convenience
    program = db.relationship('CurriculumProgram', backref=db.backref('program_subjects', lazy='dynamic'))
    subject = db.relationship('Subject', backref=db.backref('program_subjects', lazy='dynamic'))

    __table_args__ = (
        db.UniqueConstraint('program_id', 'subject_id', name='uq_program_subject'),
    )


class StudentSubject(db.Model):
    __tablename__ = "student_subjects"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False)
    
    subject = db.relationship('Subject')

class Subject(db.Model):
    __tablename__ = "subjects"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True)
    name = db.Column(db.String(100), nullable=False)
    credit_hours = db.Column(db.Integer)
    difficulty_level = db.Column(db.Integer, default=3) # 1-5
    semester_tag = db.Column(db.String(20))
    level_of_study = db.Column(db.String(50))
    program = db.Column(db.String(100))      # legacy: kept for back-compat; new logic uses program_subjects
    semester = db.Column(db.String(50))
    country = db.Column(db.String(100), default="Nepal")
    curriculum = db.Column(db.String(100), default="National")
    is_active = db.Column(db.Boolean, nullable=False, default=True)  # Deactivate instead of deleting
    deleted_at = db.Column(db.DateTime, nullable=True)
    deleted_by = db.Column(db.Integer, nullable=True)

class Prediction(db.Model):
    __tablename__ = "predictions"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Input features (12)
    attendance_pct = db.Column(db.Float)
    assignment_completion_pct = db.Column(db.Float)
    weekly_study_hours = db.Column(db.Float)
    total_logged_study_hours = db.Column(db.Float)
    study_days_last_240 = db.Column(db.Integer)
    subject_difficulty = db.Column(db.Float)
    avg_exam_score_pct = db.Column(db.Float)
    midterm_score_pct = db.Column(db.Float)
    final_score_pct = db.Column(db.Float)
    assignment_avg_pct = db.Column(db.Float)
    year_of_study = db.Column(db.Integer)
    cumulative_gpa = db.Column(db.Float)
    
    # Dynamic fields
    level_of_study = db.Column(db.String(50))
    raw_inputs = db.Column(db.Text) # JSON string of raw level-specific metrics
    
    # Target outputs
    predicted_risk_level = db.Column(db.String(20)) # low, medium, high
    predicted_grade = db.Column(db.String(5)) # A, A-, B+, B, B-, C+, C, C-, F

class StudyLog(db.Model):
    __tablename__ = "study_logs"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    duration_hours = db.Column(db.Float, nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=True)
    notes = db.Column(db.Text)
    
    subject = db.relationship('Subject')

class Assignment(db.Model):
    __tablename__ = "assignments"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=True)
    name = db.Column(db.String(100), nullable=False)
    due_date = db.Column(db.Date)
    status = db.Column(db.String(20), default="pending") # pending, completed
    score_pct = db.Column(db.Float, nullable=True)

class Exam(db.Model):
    __tablename__ = "exams"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=True)
    name = db.Column(db.String(100), nullable=False) # e.g. Midterm, Final
    date = db.Column(db.Date)
    score_pct = db.Column(db.Float, nullable=True)

class Schedule(db.Model):
    __tablename__ = "schedules"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    day_of_week = db.Column(db.Integer) # 0=Monday, 6=Sunday
    start_time = db.Column(db.Time)
    end_time = db.Column(db.Time)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=True)
    description = db.Column(db.String(200))

class Recommendation(db.Model):
    __tablename__ = "recommendations"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    recommendation_text = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50)) # e.g., Study Habits, Time Management

class Goal(db.Model):
    __tablename__ = "goals"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    description = db.Column(db.String(200), nullable=False)
    target_date = db.Column(db.Date)
    achieved = db.Column(db.Boolean, default=False)

class Notification(db.Model):
    __tablename__ = "notifications"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    message = db.Column(db.String(255), nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)

class StudyResource(db.Model):
    __tablename__ = "study_resources"
    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=True)
    title = db.Column(db.String(100), nullable=False)
    url = db.Column(db.String(255))
    description = db.Column(db.Text)

class AssessmentQuestion(db.Model):
    __tablename__ = "assessment_questions"
    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False)
    chapter_id = db.Column(db.Integer, db.ForeignKey('chapters.id'), nullable=True)
    topic_id = db.Column(db.Integer, db.ForeignKey('topics.id'), nullable=True)
    question_text = db.Column(db.Text, nullable=False)
    option_a = db.Column(db.String(300), nullable=False)
    option_b = db.Column(db.String(300), nullable=False)
    option_c = db.Column(db.String(300), nullable=False)
    option_d = db.Column(db.String(300), nullable=False)
    correct_answer = db.Column(db.String(1), nullable=False) # A, B, C, D
    difficulty = db.Column(db.String(20), nullable=False) # beginner, intermediate, advanced
    question_type = db.Column(db.String(50), nullable=False)
    explanation = db.Column(db.Text, nullable=True)
    generated_at = db.Column(db.DateTime, default=datetime.utcnow)
    source = db.Column(db.String(50), default="ai_generated")

    # Relationships
    topic = db.relationship('Topic')
    chapter = db.relationship('Chapter')
    subject = db.relationship('Subject')

class StudentAssessment(db.Model):
    __tablename__ = "student_assessments"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False)
    total_score = db.Column(db.Float, default=0.0)
    max_score = db.Column(db.Float, default=100.0)
    weighted_score = db.Column(db.Float, default=0.0)
    knowledge_tier = db.Column(db.String(20)) # beginner, intermediate, advanced
    completed_at = db.Column(db.DateTime, default=datetime.utcnow)
    time_taken_seconds = db.Column(db.Integer)

class AssessmentResponse(db.Model):
    __tablename__ = "assessment_responses"
    id = db.Column(db.Integer, primary_key=True)
    assessment_id = db.Column(db.Integer, db.ForeignKey('student_assessments.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('assessment_questions.id'), nullable=False)
    selected_answer = db.Column(db.String(1)) # A, B, C, D
    is_correct = db.Column(db.Boolean, default=False)
    response_time_seconds = db.Column(db.Integer)

class StudentSeenQuestion(db.Model):
    __tablename__ = "student_seen_questions"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('assessment_questions.id'), nullable=False)
    seen_at = db.Column(db.DateTime, default=datetime.utcnow)
    was_correct = db.Column(db.Boolean, default=False)

class AcademicDocument(db.Model):
    __tablename__ = "academic_documents"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    document_type = db.Column(db.String(50))
    document_name = db.Column(db.String(200))
    file_path = db.Column(db.String(500))
    file_type = db.Column(db.String(10)) # pdf, jpg, png
    institution_name = db.Column(db.String(200))
    exam_year = db.Column(db.Integer)
    overall_percentage = db.Column(db.Float)
    overall_gpa = db.Column(db.Float)
    extraction_confidence = db.Column(db.Float)
    is_verified = db.Column(db.Boolean, default=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    processed_at = db.Column(db.DateTime)

class ExtractedMark(db.Model):
    __tablename__ = "extracted_marks"
    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey('academic_documents.id'), nullable=False)
    subject_name_original = db.Column(db.String(200))
    subject_name_mapped = db.Column(db.String(200))
    marks_obtained = db.Column(db.Float)
    full_marks = db.Column(db.Float)
    percentage = db.Column(db.Float)
    grade = db.Column(db.String(10), nullable=True)
    credit_hours = db.Column(db.Integer, default=1)

class AuditLog(db.Model):
    __tablename__ = "audit_logs"
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(50))
    email_attempted = db.Column(db.String(120))
    status = db.Column(db.String(20)) # success or failed
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


class AdminActivityLog(db.Model):
    """
    Records every admin action that changes data.
    Used by Section 6 (Access Control) and visible via /admin/activity-log.
    """
    __tablename__ = "admin_activity_logs"
    id           = db.Column(db.Integer, primary_key=True)
    admin_user_id= db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    action       = db.Column(db.String(100), nullable=False)  # e.g. "deactivate_university"
    entity_type  = db.Column(db.String(50), nullable=True)    # e.g. "University"
    entity_id    = db.Column(db.Integer, nullable=True)
    detail       = db.Column(db.Text, nullable=True)           # Human-readable summary
    timestamp    = db.Column(db.DateTime, default=datetime.utcnow)

    admin_user   = db.relationship('User', foreign_keys=[admin_user_id])


class AdminRegistrationRequest(db.Model):
    """
    Stores pending and processed Admin Registration Requests requiring Super Admin approval.
    """
    __tablename__ = "admin_registration_requests"
    id                 = db.Column(db.Integer, primary_key=True)
    full_name          = db.Column(db.String(100), nullable=False)
    email              = db.Column(db.String(120), nullable=False)
    password_hash      = db.Column(db.String(128), nullable=False)
    requested_role     = db.Column(db.String(20), nullable=False, default="admin")
    status             = db.Column(db.String(20), nullable=False, default="PENDING")  # PENDING, APPROVED, REJECTED
    verification_code  = db.Column(db.String(10), nullable=True)
    code_expires_at    = db.Column(db.DateTime, nullable=True)
    code_used          = db.Column(db.Boolean, default=False)
    created_at         = db.Column(db.DateTime, default=datetime.utcnow)
    actioned_at        = db.Column(db.DateTime, nullable=True)
    actioned_by_id     = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    actioned_by        = db.relationship('User', foreign_keys=[actioned_by_id])


class StudyPlan(db.Model):
    __tablename__ = "study_plans"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    plan_data = db.Column(db.Text, nullable=False) # JSON-serialized planner data
    generated_at = db.Column(db.DateTime, default=datetime.utcnow)

class Chapter(db.Model):
    __tablename__ = "chapters"
    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    chapter_number = db.Column(db.Integer, nullable=False)

    subject = db.relationship('Subject')

class Topic(db.Model):
    __tablename__ = "topics"
    id = db.Column(db.Integer, primary_key=True)
    chapter_id = db.Column(db.Integer, db.ForeignKey('chapters.id'), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    topic_number = db.Column(db.Integer, nullable=False)

    chapter = db.relationship('Chapter')

class Subtopic(db.Model):
    __tablename__ = "subtopics"
    id = db.Column(db.Integer, primary_key=True)
    topic_id = db.Column(db.Integer, db.ForeignKey('topics.id'), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    subtopic_number = db.Column(db.Integer, nullable=False)

class LearningMaterial(db.Model):
    __tablename__ = "learning_materials"
    id = db.Column(db.Integer, primary_key=True)
    topic_id = db.Column(db.Integer, db.ForeignKey('topics.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    learning_objectives = db.Column(db.Text)
    introduction = db.Column(db.Text)
    detailed_explanation = db.Column(db.Text)
    important_definitions = db.Column(db.Text)
    concepts = db.Column(db.Text)
    examples = db.Column(db.Text)
    worked_examples = db.Column(db.Text)
    real_life_applications = db.Column(db.Text)
    diagrams = db.Column(db.Text)
    key_points = db.Column(db.Text)
    important_facts = db.Column(db.Text)
    formulae = db.Column(db.Text)
    common_mistakes = db.Column(db.Text)
    mcqs_json = db.Column(db.Text) # JSON string of MCQs
    short_questions_json = db.Column(db.Text)
    long_questions_json = db.Column(db.Text)
    critical_thinking_questions_json = db.Column(db.Text)
    summary = db.Column(db.Text)
    revision_notes = db.Column(db.Text)
    estimated_reading_time = db.Column(db.Integer, default=15)
    difficulty_level = db.Column(db.String(20), default="intermediate")
    learning_outcomes = db.Column(db.Text)

class Flashcard(db.Model):
    __tablename__ = "flashcards"
    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False)
    chapter_id = db.Column(db.Integer, db.ForeignKey('chapters.id'), nullable=True)
    front = db.Column(db.Text, nullable=False)
    back = db.Column(db.Text, nullable=False)


class FlashcardReview(db.Model):
    __tablename__ = "flashcard_reviews"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    flashcard_id = db.Column(db.Integer, db.ForeignKey('flashcards.id', ondelete='CASCADE'), nullable=False)
    easiness_factor = db.Column(db.Float, default=2.5)
    interval_days = db.Column(db.Integer, default=0)
    repetitions = db.Column(db.Integer, default=0)
    next_review_date = db.Column(db.DateTime, default=datetime.utcnow)
    last_reviewed_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_quality_rating = db.Column(db.Integer, nullable=True)

class SubjectBook(db.Model):
    __tablename__ = "subject_books"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    author = db.Column(db.String(255), nullable=True)
    publisher = db.Column(db.String(255), nullable=True)
    edition = db.Column(db.String(100), nullable=True)
    isbn = db.Column(db.String(100), nullable=True)
    toc_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('subject_books', lazy=True, cascade="all, delete-orphan"))
    subject = db.relationship('Subject', backref=db.backref('books', lazy=True))

class QuizScore(db.Model):
    __tablename__ = "quiz_scores"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False)
    score = db.Column(db.Float)
    total_questions = db.Column(db.Integer)
    completed_at = db.Column(db.DateTime, default=datetime.utcnow)

class StudyLogAnalysis(db.Model):
    __tablename__ = "study_log_analyses"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    analyzed_at = db.Column(db.DateTime, default=datetime.utcnow)
    productivity_score = db.Column(db.Float)
    weak_subjects_json = db.Column(db.Text) # JSON list
    learning_speed = db.Column(db.String(50))
    recommendations = db.Column(db.Text)

class LearningProgress(db.Model):
    __tablename__ = "learning_progress"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    topic_id = db.Column(db.Integer, db.ForeignKey('topics.id'), nullable=False)
    is_completed = db.Column(db.Boolean, default=False)
    completed_at = db.Column(db.DateTime, default=datetime.utcnow)
    time_spent_minutes = db.Column(db.Integer, default=0)

class StudentNote(db.Model):
    __tablename__ = "student_notes"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False)
    chapter_id = db.Column(db.Integer, db.ForeignKey('chapters.id'), nullable=True)
    notes_content = db.Column(db.Text, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class AICache(db.Model):
    __tablename__ = "ai_caches"
    id = db.Column(db.Integer, primary_key=True)
    prompt_hash = db.Column(db.String(64), unique=True, index=True, nullable=False)
    prompt = db.Column(db.Text, nullable=False)
    response_text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class DailyAPIUsage(db.Model):
    """
    Tracks Gemini API call counts per feature and model per calendar day.

    feature     — 'mcq' (assessment generation) or 'assistant' (chat tutor)
    model_name  — the name of the Gemini model used (e.g. 'gemini-3.1-flash-lite', 'gemini-2.5-flash', etc.)
    usage_date  — the UTC date the calls were made
    call_count  — number of successful generate_content calls made today

    One row per (feature, model_name, usage_date).  The daily cap is enforced in
    AIService._check_quota() before any API call is attempted.
    """
    __tablename__ = "daily_api_usage"
    id         = db.Column(db.Integer, primary_key=True)
    feature    = db.Column(db.String(32), nullable=False, index=True)
    model_name = db.Column(db.String(64), nullable=True, index=True)
    usage_date = db.Column(db.Date, nullable=False, index=True)
    call_count = db.Column(db.Integer, nullable=False, default=0)
    __table_args__ = (
        db.UniqueConstraint("feature", "model_name", "usage_date", name="uq_daily_api_usage_feature_model_date"),
    )


class AvailabilitySlot(db.Model):
    __tablename__ = "availability_slots"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    day_of_week = db.Column(db.String(15), nullable=False) # 'Sunday', 'Monday', etc.
    start_time = db.Column(db.String(5), nullable=False) # '08:30'
    end_time = db.Column(db.String(5), nullable=False) # '11:00'
    # category: one of Sleep|Class/Academic|Sports|Social/Hangout|Entertainment|Personal/Chores|Other
    # slot_type kept for backward-compat; always set to 'Sleep' or 'Busy' (non-Study) by backend
    slot_type = db.Column(db.String(20), nullable=False, default='Busy')
    category = db.Column(db.String(30), nullable=True)   # e.g. 'Sleep', 'Sports', 'Other'
    custom_label = db.Column(db.String(80), nullable=True)  # only used when category='Other'
    is_overnight = db.Column(db.Boolean, default=False, nullable=True)


class SubjectPerformanceHistory(db.Model):
    """Stores end-of-week planned vs actual hours for the closed-loop feedback system."""
    __tablename__ = "subject_performance_history"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    week_start = db.Column(db.Date, nullable=False)
    subject_name = db.Column(db.String(100), nullable=False)
    grade = db.Column(db.Float, nullable=False)
    attendance = db.Column(db.Float, nullable=False)
    difficulty = db.Column(db.Float, nullable=False)
    study_hours = db.Column(db.Float, nullable=False)
    days_until_exam = db.Column(db.Integer, nullable=False, default=30)
    days_since_last_studied = db.Column(db.Integer, nullable=False, default=0)
    planned_hours = db.Column(db.Float, nullable=False, default=0.0)
    actual_hours = db.Column(db.Float, nullable=False, default=0.0)
    completion_rate = db.Column(db.Float, nullable=False, default=1.0)
    risk_score = db.Column(db.Float, nullable=False, default=0.5)
    logged_at = db.Column(db.DateTime, default=datetime.utcnow)


class AIStudyMaterial(db.Model):
    __tablename__ = "ai_study_materials"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False)
    class_level = db.Column(db.String(50), nullable=False)
    content_json = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('study_materials', lazy=True))
    subject = db.relationship('Subject', backref=db.backref('study_materials', lazy=True))


class ReviewedChapter(db.Model):
    __tablename__ = "reviewed_chapters"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    topic_id = db.Column(db.Integer, db.ForeignKey('topics.id'), nullable=False)
    status = db.Column(db.String(20), default="not started") # 'not started', 'in progress', 'completed'
    last_accessed_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    topic = db.relationship('Topic')


class ChapterQuizScore(db.Model):
    __tablename__ = "chapter_quiz_scores"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    topic_id = db.Column(db.Integer, db.ForeignKey('topics.id'), nullable=False)
    score = db.Column(db.Float, nullable=False)
    total_questions = db.Column(db.Integer, default=5)
    completed_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    topic = db.relationship('Topic')
    results = db.relationship('ChapterQuizResult', back_populates='quiz_score', cascade='all, delete-orphan')


class TopicSeenQuestion(db.Model):
    """Permanently stores question texts the student has seen for a topic.
    Used across sessions to prevent cross-attempt question repetition."""
    __tablename__ = "topic_seen_questions"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    topic_id = db.Column(db.Integer, db.ForeignKey('topics.id'), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    seen_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    topic = db.relationship('Topic')


class ChapterQuizResult(db.Model):
    """Per-question result row, linked to a ChapterQuizScore attempt.
    Enables weak-topic analysis at the question level, not just overall score."""
    __tablename__ = "chapter_quiz_results"
    id = db.Column(db.Integer, primary_key=True)
    quiz_score_id = db.Column(db.Integer, db.ForeignKey('chapter_quiz_scores.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    topic_id = db.Column(db.Integer, db.ForeignKey('topics.id'), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    selected_answer = db.Column(db.String(1), nullable=True)   # A / B / C / D
    correct_answer = db.Column(db.String(1), nullable=False)
    was_correct = db.Column(db.Boolean, nullable=False, default=False)
    answered_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    quiz_score = db.relationship('ChapterQuizScore', back_populates='results')
    topic = db.relationship('Topic')


class BookmarkedChapter(db.Model):
    __tablename__ = "bookmarked_chapters"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    topic_id = db.Column(db.Integer, db.ForeignKey('topics.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    topic = db.relationship('Topic')


class ChapterNote(db.Model):
    __tablename__ = "chapter_notes"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    topic_id = db.Column(db.Integer, db.ForeignKey('topics.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    topic = db.relationship('Topic')


class PastQuestion(db.Model):
    __tablename__ = "past_questions"
    id = db.Column(db.Integer, primary_key=True)
    topic_id = db.Column(db.Integer, db.ForeignKey('topics.id'), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    exam_year = db.Column(db.Integer, nullable=True)

    # Relationships
    topic = db.relationship('Topic')


class MaterialImportBatch(db.Model):
    """
    Tracks one zip upload by a student. Mirrors the ImportSession pattern
    already used for admin curriculum import, but scoped to a student's
    own study material rather than global curriculum data.

    Lifecycle: uploaded -> extracted -> reviewing -> committed -> failed
    """
    __tablename__ = "material_import_batches"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='uploaded')
    source_filename = db.Column(db.String(255), nullable=False)
    stored_zip_path = db.Column(db.String(500), nullable=False)
    total_files_found = db.Column(db.Integer, default=0)
    matched_files = db.Column(db.Integer, default=0)
    unmatched_files = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    committed_at = db.Column(db.DateTime, nullable=True)
    error_log = db.Column(db.Text, nullable=True)

    user = db.relationship('User', backref=db.backref('import_batches', lazy=True))
    unmatched_items = db.relationship('MaterialImportUnmatched', backref='batch', lazy=True, cascade='all, delete-orphan')


class MaterialImportUnmatched(db.Model):
    """
    A folder found in the zip whose name didn't confidently match any
    Subject the student is enrolled in. Student resolves these manually
    in the review screen before commit — never silently dropped.
    """
    __tablename__ = "material_import_unmatched"
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('material_import_batches.id', ondelete='CASCADE'), nullable=False)
    folder_path_in_zip = db.Column(db.String(500), nullable=False)
    detected_name = db.Column(db.String(200), nullable=True)
    suggested_subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=True)
    resolved_subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=True)
    file_count = db.Column(db.Integer, default=0)


class MaterialChunk(db.Model):
    """
    One retrievable chunk of text from an UploadedMaterial file.
    embedding_vector stored as JSON list of floats (SQLite has no native vector type).
    """
    __tablename__ = "material_chunks"
    id = db.Column(db.Integer, primary_key=True)
    material_id = db.Column(db.Integer, db.ForeignKey('uploaded_materials.id', ondelete='CASCADE'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    chunk_index = db.Column(db.Integer, nullable=False)
    chunk_text = db.Column(db.Text, nullable=False)
    token_count = db.Column(db.Integer, nullable=True)
    embedding_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    material = db.relationship('UploadedMaterial', backref=db.backref('chunks', lazy=True, cascade='all, delete-orphan'))
    subject = db.relationship('Subject')


class ModuleDescriptor(db.Model):
    """
    Structured fields extracted (via Gemini) from a Module Descriptor file.
    One per subject per student.
    """
    __tablename__ = "module_descriptors"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False)
    source_material_id = db.Column(db.Integer, db.ForeignKey('uploaded_materials.id'), nullable=True)

    has_final_exam = db.Column(db.Boolean, nullable=True)
    exam_weight_pct = db.Column(db.Float, nullable=True)
    coursework_weight_pct = db.Column(db.Float, nullable=True)
    has_presentation = db.Column(db.Boolean, nullable=True)
    topics_json = db.Column(db.Text, nullable=True)
    assessment_dates_json = db.Column(db.Text, nullable=True)
    raw_extraction_json = db.Column(db.Text, nullable=True)
    extracted_at = db.Column(db.DateTime, default=datetime.utcnow)
    extraction_confidence = db.Column(db.String(20), default='unverified')

    __table_args__ = (db.UniqueConstraint('user_id', 'subject_id', name='uq_module_descriptor_user_subject'),)

    user = db.relationship('User')
    subject = db.relationship('Subject')


class UploadedMaterial(db.Model):
    __tablename__ = "uploaded_materials"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False)
    chapter_id = db.Column(db.Integer, db.ForeignKey('chapters.id'), nullable=True)
    topic_id = db.Column(db.Integer, db.ForeignKey('topics.id'), nullable=True)
    filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    file_type = db.Column(db.String(10), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    extracted_text = db.Column(db.Text, nullable=True)
    summary = db.Column(db.Text, nullable=True)
    revision_notes = db.Column(db.Text, nullable=True)
    flashcards_json = db.Column(db.Text, nullable=True)
    mcqs_json = db.Column(db.Text, nullable=True)
    last_opened = db.Column(db.DateTime, nullable=True)

    # NEW — RAG & classification columns
    import_batch_id = db.Column(db.Integer, db.ForeignKey('material_import_batches.id'), nullable=True)
    category = db.Column(db.String(30), nullable=False, default='Other')
    file_size_bytes = db.Column(db.Integer, nullable=True)
    embedding_status = db.Column(db.String(20), nullable=False, default='pending')
    relative_folder_path = db.Column(db.String(500), nullable=True)

    # Relationships
    user = db.relationship('User', backref=db.backref('uploaded_materials', lazy=True))
    subject = db.relationship('Subject', backref=db.backref('uploaded_materials', lazy=True))
    chapter = db.relationship('Chapter', backref=db.backref('uploaded_materials', lazy=True))
    topic = db.relationship('Topic', backref=db.backref('uploaded_materials', lazy=True))
    import_batch = db.relationship('MaterialImportBatch', backref=db.backref('materials', lazy=True))



class AppSetting(db.Model):
    __tablename__ = "app_settings"
    key = db.Column(db.String(100), primary_key=True)
    value = db.Column(db.String(500), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class EmailVerificationCache(db.Model):
    __tablename__ = "email_verification_caches"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, index=True, nullable=False)
    verification_result = db.Column(db.Text, nullable=False)
    checked_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class EmailVerificationCode(db.Model):
    __tablename__ = "email_verification_codes"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), nullable=False)
    code = db.Column(db.String(6), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    verified = db.Column(db.Boolean, default=False, nullable=False)
    attempts = db.Column(db.Integer, default=0, nullable=False)


# ── Phase 4: Document Ingestion (staging area) ────────────────────────────────

class ImportSession(db.Model):
    """
    Tracks a single document-ingestion batch.

    Lifecycle:
        pending  -> Files uploaded, extraction not yet run.
        extracted -> Extraction complete, items ready for review.
        reviewing -> Admin reviewing the preview page.
        committed -> Ingestion confirmed and written to DB.
        cancelled -> Admin cancelled or an error occurred.

    No curriculum data is modified until status == 'committed'.
    """
    __tablename__ = "import_sessions"
    id            = db.Column(db.Integer, primary_key=True)
    admin_id      = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    status        = db.Column(db.String(20), nullable=False, default='pending')
    source_file   = db.Column(db.String(255), nullable=False)   # original filename
    stored_file   = db.Column(db.String(255), nullable=False)   # uuid-based safe name
    doc_type      = db.Column(db.String(10), nullable=False)    # docx / pdf / pptx
    file_size     = db.Column(db.Integer, nullable=True)        # bytes
    detected_program    = db.Column(db.String(200), nullable=True)
    detected_program_id = db.Column(db.Integer, db.ForeignKey('curriculum_programs.id'), nullable=True)
    ingestion_mode      = db.Column(db.String(20), nullable=False, default='append')  # append | replace
    notes         = db.Column(db.Text, nullable=True)           # admin notes
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    committed_at  = db.Column(db.DateTime, nullable=True)

    admin   = db.relationship('User', backref=db.backref('import_sessions', lazy='dynamic'))
    program = db.relationship('CurriculumProgram', backref=db.backref('import_sessions', lazy='dynamic'))
    items   = db.relationship('ImportItem', backref='session', lazy='dynamic', cascade='all, delete-orphan')


class ImportItem(db.Model):
    """
    A single detected subject row within an ImportSession.

    action values (admin-chosen):
        LINK_EXISTING  -> reuse matched_subject_id
        CREATE_NEW     -> create a new global Subject
        SKIP           -> ignore this row
        NEEDS_REVIEW   -> admin has not yet resolved ambiguity

    status values:
        pending    -> not yet committed
        committed  -> written to DB successfully
        skipped    -> skipped by admin
        failed     -> an error occurred during commit
    """
    __tablename__ = "import_items"
    id                  = db.Column(db.Integer, primary_key=True)
    session_id          = db.Column(db.Integer, db.ForeignKey('import_sessions.id', ondelete='CASCADE'), nullable=False)
    # Extracted raw values
    extracted_program   = db.Column(db.String(200), nullable=True)
    extracted_semester  = db.Column(db.String(50),  nullable=True)
    extracted_term      = db.Column(db.String(50),  nullable=True)
    extracted_code      = db.Column(db.String(30),  nullable=True)
    extracted_name      = db.Column(db.String(200), nullable=True)
    extracted_credits   = db.Column(db.Integer, nullable=True)
    # Matching result
    match_confidence    = db.Column(db.Float, nullable=True)   # 0.0 – 1.0
    matched_subject_id  = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=True)
    # Admin decision
    action              = db.Column(db.String(20), nullable=False, default='NEEDS_REVIEW')
    final_subject_id    = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=True)
    final_semester      = db.Column(db.String(50),  nullable=True)
    final_term          = db.Column(db.String(50),  nullable=True)
    final_code          = db.Column(db.String(30),  nullable=True)
    final_name          = db.Column(db.String(200), nullable=True)
    final_credits       = db.Column(db.Integer, nullable=True)
    sort_order          = db.Column(db.Integer, nullable=False, default=0)
    # Commit result
    status              = db.Column(db.String(20), nullable=False, default='pending')
    program_subject_id  = db.Column(db.Integer, db.ForeignKey('program_subjects.id'), nullable=True)

    matched_subject = db.relationship('Subject', foreign_keys=[matched_subject_id])
    final_subject   = db.relationship('Subject', foreign_keys=[final_subject_id])





