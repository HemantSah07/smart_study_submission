from app import create_app, db
from sqlalchemy import text, inspect

app = create_app()

with app.app_context():
    print("Creating any missing tables (like AuditLog)...")
    db.create_all()
    
    print("Running migrations to add missing columns...")
    
    inspector = inspect(db.engine)
    columns = [c['name'] for c in inspector.get_columns('student_profiles')]
    
    queries = [
        "ALTER TABLE student_profiles ADD study_level VARCHAR(50) DEFAULT 'Class 9'",
        "ALTER TABLE student_profiles ADD has_completed_assessment BOOLEAN DEFAULT 0",
        "ALTER TABLE student_profiles ADD prior_academic_score FLOAT DEFAULT 0.0",
        "ALTER TABLE student_profiles ADD documents_uploaded INTEGER DEFAULT 0",
        "ALTER TABLE student_profiles ADD academic_level VARCHAR(20) DEFAULT 'average'",
        "ALTER TABLE student_profiles ADD level_of_study VARCHAR(50)",
        "ALTER TABLE student_profiles ADD semester VARCHAR(50)",
        "ALTER TABLE student_profiles ADD country VARCHAR(100) DEFAULT 'Nepal'",
        "ALTER TABLE student_profiles ADD timezone VARCHAR(64) DEFAULT 'Asia/Kathmandu'",
        "ALTER TABLE student_profiles ADD curriculum VARCHAR(100) DEFAULT 'National'",
        "ALTER TABLE student_profiles ADD learning_style VARCHAR(50) DEFAULT 'Mixed'",
        "ALTER TABLE student_profiles ADD explanation_level VARCHAR(50) DEFAULT 'Intermediate'",
        "ALTER TABLE student_profiles ADD response_length VARCHAR(50) DEFAULT 'Medium'",
        "ALTER TABLE student_profiles ADD quiz_difficulty VARCHAR(50) DEFAULT 'Medium'",
        "ALTER TABLE student_profiles ADD study_goal VARCHAR(100) DEFAULT 'Improve Grades'",
        "ALTER TABLE student_profiles ADD preferred_language VARCHAR(50) DEFAULT 'English'",
        "ALTER TABLE student_profiles ADD profile_pic VARCHAR(200)",
        "ALTER TABLE student_profiles ADD target_weekly_hours FLOAT DEFAULT 20.0",
        "ALTER TABLE student_profiles ADD commute_buffer_minutes INTEGER DEFAULT 0",
        "ALTER TABLE subjects ADD level_of_study VARCHAR(50)",
        "ALTER TABLE subjects ADD program VARCHAR(100)",
        "ALTER TABLE subjects ADD semester VARCHAR(50)",
        "ALTER TABLE subjects ADD country VARCHAR(100) DEFAULT 'Nepal'",
        "ALTER TABLE subjects ADD curriculum VARCHAR(100) DEFAULT 'National'",
        "ALTER TABLE predictions ADD level_of_study VARCHAR(50)",
        "ALTER TABLE predictions ADD raw_inputs TEXT",
        "ALTER TABLE assessment_questions ADD chapter_id INTEGER",
        "ALTER TABLE student_profiles ADD university VARCHAR(100)",
        "ALTER TABLE student_profiles ADD program_duration VARCHAR(20) DEFAULT NULL",
        "ALTER TABLE users ADD email_verified_status VARCHAR(32) DEFAULT 'unknown'"
    ]
    
    if 'university_type' not in columns:
        queries.append("ALTER TABLE student_profiles ADD university_type VARCHAR(50) DEFAULT NULL")
    if 'university_country' not in columns:
        queries.append("ALTER TABLE student_profiles ADD university_country VARCHAR(100) DEFAULT NULL")
        
    for q in queries:
        try:
            db.session.execute(text(q))
            print(f"Executed: {q}")
        except Exception as e:
            # Column likely already exists
            print(f"Skipped: {q}")
            
    db.session.commit()
    print("Migration complete!")
