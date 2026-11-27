"""
delete_bulk_seed_accounts.py
Safe deletion of 705 bulk-seeded fake accounts (700 students + 5 fake admins).

DELETION CRITERIA (accounts matching EITHER block are deleted):
  Block A — Fake students:
    role = 'student'
    date_registered = 2026-07-21
    email LIKE '%@student.apu.edu.my'

  Block B — Fake admins (same load_data.py batch, known shared password):
    role = 'admin'
    date_registered = 2026-07-21
    email LIKE 'admin[0-9]%@apu.edu.my'

EXPLICITLY PROTECTED (will NEVER be touched):
  - hemantsah123456789@gmail.com  (id=706, the real admin account)
  - Any account NOT matching the criteria above

DELETION ORDER (FK-safe, no cascade configured in SQLite):
  1. student_subjects  (FK user_id -> users.id)
  2. student_profiles  (FK user_id -> users.id)
  3. users

Usage:
  Preview:   venv\\Scripts\\python.exe delete_bulk_seed_accounts.py
  Execute:   venv\\Scripts\\python.exe delete_bulk_seed_accounts.py --execute
"""
import os, sys, json, argparse
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from app import create_app, db
from app.models import User, StudentProfile, StudentSubject
from sqlalchemy import func, text

SEED_DATE   = "2026-07-21"
BACKUP_FILE = os.path.join(os.path.dirname(__file__), "scratch", "deleted_accounts_backup.json")

PROTECTED_EMAILS = {"hemantsah123456789@gmail.com"}

app = create_app()


def get_candidates(session):
    """Return all bulk-seed User objects (students + fake admins), excluding protected accounts."""
    fake_students = session.query(User).filter(
        User.role == "student",
        func.date(User.date_registered) == SEED_DATE,
        User.email.like("%@student.apu.edu.my"),
        ~User.email.in_(PROTECTED_EMAILS),
    )
    fake_admins = session.query(User).filter(
        User.role == "admin",
        func.date(User.date_registered) == SEED_DATE,
        User.email.like("admin%@apu.edu.my"),
        ~User.email.in_(PROTECTED_EMAILS),
    )
    return fake_students.union(fake_admins).order_by(User.id).all()


def chunked_count(session, table, col, ids):
    """Count rows in table where col is in ids, using chunked IN queries."""
    total = 0
    for i in range(0, len(ids), 900):
        chunk = ids[i:i+900]
        ids_str = ",".join(str(x) for x in chunk)
        total += session.execute(
            text(f'SELECT COUNT(*) FROM "{table}" WHERE "{col}" IN ({ids_str})')
        ).scalar()
    return total


def chunked_delete(session, table, col, ids):
    """Delete rows in table where col is in ids, using chunked IN queries."""
    deleted = 0
    for i in range(0, len(ids), 900):
        chunk = ids[i:i+900]
        ids_str = ",".join(str(x) for x in chunk)
        result = session.execute(
            text(f'DELETE FROM "{table}" WHERE "{col}" IN ({ids_str})')
        )
        deleted += result.rowcount
    return deleted


def preview(session):
    candidates = get_candidates(session)
    ids = [u.id for u in candidates]
    students  = [u for u in candidates if u.role == "student"]
    fake_adms = [u for u in candidates if u.role == "admin"]

    print("=" * 70)
    print("BULK-SEED ACCOUNT DELETION -- PREVIEW (no changes made)")
    print("=" * 70)
    print(f"\nTotal accounts to delete: {len(candidates)}")
    print(f"  Fake students:  {len(students)}  (@student.apu.edu.my, registered {SEED_DATE})")
    print(f"  Fake admins:    {len(fake_adms)}  (admin[N]@apu.edu.my, registered {SEED_DATE})")

    print(f"\n--- Sample of first 10 student accounts to be deleted ---")
    for u in students[:10]:
        profile = StudentProfile.query.filter_by(user_id=u.id).first()
        level = profile.study_level if profile else "NO_PROFILE"
        print(f"  id={u.id:4d} | {str(u.date_registered)[:19]} | {u.email:45s} | level={level}")

    print(f"\n--- All 5 fake admin accounts to be deleted ---")
    for u in fake_adms:
        print(f"  id={u.id:4d} | {str(u.date_registered)[:19]} | {u.email:45s} | role={u.role}")

    print(f"\n--- Related data that will also be deleted ---")
    ss = chunked_count(session, "student_subjects", "user_id", ids)
    print(f"  student_subjects rows:  {ss}")
    print(f"  student_profiles rows:  {len(students)}  (fake admins have no profiles)")
    print(f"  users rows:             {len(candidates)}")

    print(f"\n--- Accounts that will NOT be touched ---")
    safe = session.query(User).filter(~User.id.in_(ids)).order_by(User.id).all()
    print(f"  {len(safe)} account(s) preserved:")
    for u in safe:
        print(f"    id={u.id:4d} | role={u.role:8s} | {u.email}")

    print("\n[DRY RUN COMPLETE -- nothing deleted. Run with --execute to proceed.]")


def execute_deletion(session):
    candidates = get_candidates(session)
    ids = [u.id for u in candidates]
    student_ids = [u.id for u in candidates if u.role == "student"]

    if not ids:
        print("No matching accounts found. Nothing to delete.")
        return

    # ── Step 0: Backup ─────────────────────────────────────────────────────
    backup = []
    for u in candidates:
        profile = StudentProfile.query.filter_by(user_id=u.id).first()
        backup.append({
            "id": u.id,
            "email": u.email,
            "full_name": u.full_name,
            "role": u.role,
            "date_registered": str(u.date_registered),
            "study_level": profile.study_level if profile else None,
            "program": profile.program if profile else None,
        })
    os.makedirs(os.path.dirname(BACKUP_FILE), exist_ok=True)
    with open(BACKUP_FILE, "w", encoding="utf-8") as f:
        json.dump(backup, f, indent=2)
    print(f"[1/5] Backup written: {BACKUP_FILE}  ({len(backup)} records)")

    # ── Step 1: Delete student_subjects ────────────────────────────────────
    ss_deleted = chunked_delete(session, "student_subjects", "user_id", ids)
    session.commit()
    print(f"[2/5] Deleted {ss_deleted} student_subjects rows")

    # ── Step 2: Delete student_profiles (students only — admins have none) ─
    sp_deleted = chunked_delete(session, "student_profiles", "user_id", student_ids)
    session.commit()
    print(f"[3/5] Deleted {sp_deleted} student_profiles rows")

    # ── Step 3: Delete users ───────────────────────────────────────────────
    u_deleted = chunked_delete(session, "users", "id", ids)
    session.commit()
    print(f"[4/5] Deleted {u_deleted} user rows")

    # ── Step 4: Post-deletion verification ────────────────────────────────
    print("\n[5/5] Post-deletion verification")

    remaining_bulk = session.query(User).filter(
        User.email.like("%@student.apu.edu.my")
    ).count() + session.query(User).filter(
        User.email.like("admin%@apu.edu.my"),
        func.date(User.date_registered) == SEED_DATE
    ).count()
    print(f"  Remaining bulk-seed accounts:  {remaining_bulk}  (expected: 0)")

    total_remaining = session.query(User).count()
    print(f"  Total users in DB:             {total_remaining}")

    # Orphan checks
    orphaned_profiles = session.execute(
        text('SELECT COUNT(*) FROM "student_profiles" sp '
             'WHERE NOT EXISTS (SELECT 1 FROM "users" u WHERE u.id = sp.user_id)')
    ).scalar()
    print(f"  Orphaned student_profiles:     {orphaned_profiles}  (expected: 0)")

    orphaned_subjects = session.execute(
        text('SELECT COUNT(*) FROM "student_subjects" ss '
             'WHERE NOT EXISTS (SELECT 1 FROM "users" u WHERE u.id = ss.user_id)')
    ).scalar()
    print(f"  Orphaned student_subjects:     {orphaned_subjects}  (expected: 0)")

    # Confirm real admin is intact
    print(f"\n  Accounts remaining in DB:")
    for u in session.query(User).order_by(User.id).all():
        print(f"    id={u.id} | role={u.role:8s} | is_active={u.is_active} | {u.email}")

    print(f"\nDeletion complete. Backup at: {BACKUP_FILE}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true",
                        help="Perform the deletion (default: dry-run preview only)")
    args = parser.parse_args()

    with app.app_context():
        if args.execute:
            print("*** EXECUTING DELETION -- IRREVERSIBLE ***\n")
            execute_deletion(db.session)
        else:
            preview(db.session)
