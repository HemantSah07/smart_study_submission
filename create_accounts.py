from app import create_app, db
from app.models import User, StudentProfile
from flask_bcrypt import Bcrypt

app = create_app()
bcrypt = Bcrypt(app)

with app.app_context():
    db.create_all()
    
    # Create test student
    if not User.query.filter_by(email='hemant@student.apu.edu.my').first():
        hashed = bcrypt.generate_password_hash('Student@123').decode('utf-8')
        student = User(
            full_name='Hemant Kumar Sah',
            email='hemant@student.apu.edu.my',
            password_hash=hashed,
            role='student',
            is_active=True
        )
        db.session.add(student)
        db.session.flush()
        
        profile = StudentProfile(
            user_id=student.id,
            student_number='NP069826',
            program='BSc (Hons) Computer Science',
            year_of_study=3,
            cumulative_gpa=3.2
        )
        db.session.add(profile)
    
    # Create admin account
    if not User.query.filter_by(email='admin@gmail.com').first():
        hashed_admin = bcrypt.generate_password_hash('Admin@5916').decode('utf-8')
        admin = User(
            full_name='Admin User',
            email='admin@gmail.com',
            password_hash=hashed_admin,
            role='admin',
            is_active=True
        )
        db.session.add(admin)
        
    db.session.commit()
    print('Accounts created successfully!')
    print('Student: hemant@student.apu.edu.my / Student@123')
    print('Admin: admin@gmail.com / Admin@5916')

