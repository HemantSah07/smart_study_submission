"""
load_data.py — Seed script for Smart Study demo/test data.

SECURITY RULES — READ BEFORE MODIFYING:
==========================================================================
1. NEVER assign role='admin' from this script or from CSV data.
   Admin accounts must ONLY be created via the interactive create_admin.py
   script, which prompts for email and password via getpass (never stored
   or printed). If this script encounters a row with role='admin' in the
   CSV, it SKIPS that row silently.

2. Running with --fresh drops ALL tables, including the users table.
   After any --fresh run you MUST recreate your admin account:
       venv\\Scripts\\python.exe create_admin.py

3. Seeded student accounts are flagged with is_seed_account=True and are
   NOT loginable — authentication is blocked for seed accounts regardless
   of password. This prevents bulk-seeded accounts from being used to log
   in to the system, even if an attacker knows the internal hash.
==========================================================================
"""
import argparse
import os
import secrets
import pandas as pd
from app import create_app, db, bcrypt
from app.models import User, Subject, StudentProfile

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, "instance", "data")

app = create_app()


def load_seed_data(fresh=False):
    with app.app_context():
        if fresh:
            db.drop_all()
            db.create_all()
            print("Database reset (drop_all + create_all).")
            print("REMINDER: Run 'venv\\Scripts\\python.exe create_admin.py' to recreate your admin account.")
        else:
            db.create_all()

        # ── Subjects ──────────────────────────────────────────────────────
        subjects_df = pd.read_csv(os.path.join(DATA_DIR, "03_subjects.csv"))
        for _, row in subjects_df.iterrows():
            if Subject.query.filter_by(code=row["code"]).first():
                continue
            db.session.add(
                Subject(
                    id=int(row["id"]),
                    code=row["code"],
                    name=row["name"],
                    credit_hours=int(row["credit_hours"]),
                    difficulty_level=int(row["difficulty_level"]),
                    semester_tag=row["semester_tag"],
                )
            )
        db.session.commit()
        print(f"Subjects loaded: {Subject.query.count()}")

        # ── Users — STUDENTS ONLY, no admin role ever ─────────────────────
        skipped_admins = 0
        users_df = pd.read_csv(os.path.join(DATA_DIR, "01_users.csv"))
        for _, row in users_df.iterrows():
            # SECURITY: block any CSV row trying to assign admin role
            if str(row.get("role", "student")).strip().lower() != "student":
                skipped_admins += 1
                continue

            if User.query.filter_by(email=row["email"]).first():
                continue

            # Give each seed account a unique random password hash.
            # These accounts have is_seed_account=True which blocks login
            # in auth.py — the password itself is irrelevant and is never
            # printed, logged, or stored anywhere accessible.
            random_pw = secrets.token_urlsafe(32)
            hashed_pw = bcrypt.generate_password_hash(random_pw).decode("utf-8")

            db.session.add(
                User(
                    id=int(row["id"]),
                    username=row["email"].lower(),
                    full_name=row["full_name"],
                    email=row["email"],
                    password_hash=hashed_pw,
                    role="student",          # always forced to student
                    is_active=bool(int(row["is_active"])),
                    is_seed_account=True,    # blocks login in auth.py
                )
            )
        db.session.commit()
        if skipped_admins:
            print(f"SECURITY: Skipped {skipped_admins} CSV row(s) with role != 'student'.")
        print(f"Users loaded: {User.query.count()}")

        # ── Student profiles ───────────────────────────────────────────────
        profiles_df = pd.read_csv(os.path.join(DATA_DIR, "02_student_profiles.csv"))
        for _, row in profiles_df.iterrows():
            if StudentProfile.query.filter_by(user_id=int(row["user_id"])).first():
                continue
            db.session.add(
                StudentProfile(
                    id=int(row["id"]),
                    user_id=int(row["user_id"]),
                    student_number=row["student_number"],
                    program=row["program"],
                    year_of_study=int(row["year_of_study"]),
                    cumulative_gpa=float(row["cumulative_gpa"]),
                )
            )
        db.session.commit()
        print(f"Student profiles loaded: {StudentProfile.query.count()}")
        print("Data loading complete.")
        print("NOTE: Seeded student accounts cannot log in (is_seed_account=True).")
        print("      To enable login for specific test accounts, use create_admin.py")
        print("      or manually set is_seed_account=False for that user in the DB.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load Smart Study seed data")
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Drop and recreate all tables before loading (DESTRUCTIVE — recreate admin after).",
    )
    args = parser.parse_args()
    if args.fresh:
        print("WARNING: Running with --fresh will drop ALL database tables, deleting all admin accounts and custom data!")
        try:
            confirm = input("Type 'YES DELETE EVERYTHING' to confirm: ")
        except (KeyboardInterrupt, EOFError):
            print("\nAborted.")
            sys.exit(0)
        if confirm.strip() != "YES DELETE EVERYTHING":
            print("Aborted. No changes made.")
            sys.exit(0)
    load_seed_data(fresh=args.fresh)
