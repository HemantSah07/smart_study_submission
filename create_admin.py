import getpass
from app import create_app, db, bcrypt
from app.models import User

app = create_app()

def main():
    print("=== Create Admin Account ===")
    
    # Prompt for email
    email = input("Enter admin email address: ").strip()
    if not email:
        print("Error: Email cannot be empty.")
        return

    with app.app_context():
        # Check if email is already in use
        existing_user = User.query.filter(db.func.lower(User.email) == email.lower()).first()
        if existing_user:
            print(f"Error: A user with email '{email}' already exists (role={existing_user.role}).")
            return
            
        # Prompt for password securely using getpass
        password = getpass.getpass("Enter admin password: ")
        confirm_password = getpass.getpass("Confirm admin password: ")
        
        if password != confirm_password:
            print("Error: Passwords do not match.")
            return
            
        if len(password) < 8:
            print("Error: Password must be at least 8 characters long.")
            return
            
        # Hash password and create admin User
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        
        admin_user = User(
            username=email.split('@')[0],
            full_name="Admin User",
            email=email,
            password_hash=hashed_password,
            role='admin'
        )
        
        db.session.add(admin_user)
        db.session.commit()
        print(f"\nSuccess: Admin account '{email}' created successfully!")

if __name__ == "__main__":
    main()

