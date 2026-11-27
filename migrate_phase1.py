"""
migrate_phase1.py - Idempotent Phase 1 migration.

Adds:
  - soft-delete columns (deleted_at, deleted_by) to curriculum tables
  - program_subjects table
  - back-fills ProgramSubject from subjects.program string field

Safety:
  - Creates a timestamped backup before any changes
  - Checks every column/table before adding (safe to rerun multiple times)
  - Verifies baseline counts before and after
  - Stops with a report if any minimum count decreases
  - Logs all ambiguous/unmatched subjects for Admin review

Run: venv\\Scripts\\python.exe migrate_phase1.py
"""
import sqlite3
import shutil
import sys
import os
from datetime import datetime

DB_PATH = 'smart_study.db'
REAL_ADMIN_EMAIL = 'hemantsah123456789@gmail.com'

CURRICULUM_MINIMUMS = {
    'education_levels': 9,
    'universities': 10,
    'faculties': 14,
    'curriculum_programs': 14,
    'subjects': 193,
    'chapters': 60,
    'topics': 60,
    'learning_materials': 60,
    'assessment_questions': 181,
}


def get_counts(cursor):
    counts = {}
    for table in CURRICULUM_MINIMUMS:
        cursor.execute(f"SELECT COUNT(*) FROM [{table}];")
        counts[table] = cursor.fetchone()[0]
    return counts


def check_counts(counts, label):
    failed = []
    for table, minimum in CURRICULUM_MINIMUMS.items():
        cnt = counts.get(table, 0)
        if cnt < minimum:
            failed.append(f"  {table}: {cnt} < {minimum} MINIMUM")
    if failed:
        print(f"\n[FAIL] {label} — count check FAILED:")
        for f in failed:
            print(f)
        return False
    return True


def col_exists(cursor, table, column):
    cursor.execute(f"PRAGMA table_info({table});")
    return any(row[1] == column for row in cursor.fetchall())


def table_exists(cursor, table):
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?;", (table,))
    return cursor.fetchone() is not None


def main():
    print("=" * 60)
    print("PHASE 1 MIGRATION - Program-Subject Mapping")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 60)

    # ── Step 1: Backup ────────────────────────────────────────────────────────
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = f'smart_study_phase1_backup_{ts}.db'
    shutil.copy2(DB_PATH, backup_path)
    if not os.path.exists(backup_path):
        print(f"[FAIL] Backup failed: {backup_path}")
        sys.exit(1)
    backup_size = os.path.getsize(backup_path)
    print(f"\n[OK] Backup created: {backup_path} ({backup_size:,} bytes)")

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = OFF;")   # needed for ALTER TABLE on SQLite
    cursor = conn.cursor()

    # ── Step 2: Verify admin account ──────────────────────────────────────────
    cursor.execute("SELECT id, role FROM users WHERE email = ?;", (REAL_ADMIN_EMAIL,))
    admin = cursor.fetchone()
    if not admin:
        print(f"[FAIL] Real admin account not found: {REAL_ADMIN_EMAIL}")
        conn.close()
        sys.exit(1)
    print(f"[OK] Real admin account verified: ID={admin[0]}, role={admin[1]}")

    # ── Step 3: Baseline counts ───────────────────────────────────────────────
    baseline = get_counts(cursor)
    print("\n[BASELINE COUNTS]")
    for t, c in baseline.items():
        print(f"  {t:35s}: {c}")
    if not check_counts(baseline, "BASELINE"):
        conn.close()
        sys.exit(1)

    # ── Step 4: Add soft-delete columns to curriculum tables ──────────────────
    print("\n[STEP 4] Adding soft-delete columns...")
    soft_delete_targets = [
        ('education_levels', 'deleted_at', "DATETIME"),
        ('education_levels', 'deleted_by', "INTEGER"),
        ('universities', 'deleted_at', "DATETIME"),
        ('universities', 'deleted_by', "INTEGER"),
        ('faculties', 'deleted_at', "DATETIME"),
        ('faculties', 'deleted_by', "INTEGER"),
        ('curriculum_programs', 'deleted_at', "DATETIME"),
        ('curriculum_programs', 'deleted_by', "INTEGER"),
        ('subjects', 'deleted_at', "DATETIME"),
        ('subjects', 'deleted_by', "INTEGER"),
    ]
    for table, col, coltype in soft_delete_targets:
        if not col_exists(cursor, table, col):
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col} {coltype};")
            print(f"  Added column {col} to {table}")
        else:
            print(f"  Skipped {col} on {table} (already exists)")
    conn.commit()

    # ── Step 5: Create program_subjects table ─────────────────────────────────
    print("\n[STEP 5] Creating program_subjects table...")
    if not table_exists(cursor, 'program_subjects'):
        cursor.execute("""
            CREATE TABLE program_subjects (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                program_id INTEGER NOT NULL REFERENCES curriculum_programs(id) ON DELETE CASCADE,
                subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE RESTRICT,
                semester   VARCHAR(50),
                term       VARCHAR(50),
                sort_order INTEGER NOT NULL DEFAULT 0,
                is_active  BOOLEAN NOT NULL DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                deleted_at DATETIME,
                deleted_by INTEGER,
                CONSTRAINT uq_program_subject UNIQUE (program_id, subject_id)
            );
        """)
        conn.commit()
        print("  Created program_subjects table.")
    else:
        # Add any missing columns idempotently
        ps_cols_needed = [
            ('semester', 'VARCHAR(50)'),
            ('term', 'VARCHAR(50)'),
            ('sort_order', 'INTEGER NOT NULL DEFAULT 0'),
            ('is_active', 'BOOLEAN NOT NULL DEFAULT 1'),
            ('deleted_at', 'DATETIME'),
            ('deleted_by', 'INTEGER'),
        ]
        for col, coltype in ps_cols_needed:
            if not col_exists(cursor, 'program_subjects', col):
                cursor.execute(f"ALTER TABLE program_subjects ADD COLUMN {col} {coltype};")
                print(f"  Added column {col} to program_subjects")
        conn.commit()
        print("  program_subjects already exists — checked for missing columns.")

    # ── Step 6: Back-fill ProgramSubject from subjects.program ────────────────
    print("\n[STEP 6] Back-filling ProgramSubject mappings from subjects.program...")

    # Build program name → id map
    cursor.execute("SELECT id, name FROM curriculum_programs WHERE is_active = 1;")
    all_programs = {row[1].strip().lower(): row[0] for row in cursor.fetchall()}

    # Load all subjects with a program value
    cursor.execute("SELECT id, name, code, program, semester FROM subjects WHERE program IS NOT NULL AND program != '';")
    subjects_to_map = cursor.fetchall()

    matched = 0
    unmatched = []
    skipped_dup = 0

    for subj_id, subj_name, subj_code, prog_str, semester in subjects_to_map:
        prog_key = prog_str.strip().lower()

        # Exact match
        prog_id = all_programs.get(prog_key)

        if prog_id is None:
            # Try partial match: check if prog_str is a substring of any program name
            candidates = [(pname, pid) for pname, pid in all_programs.items() if prog_key in pname or pname in prog_key]
            if len(candidates) == 1:
                prog_id = candidates[0][1]
            elif len(candidates) > 1:
                unmatched.append((subj_id, subj_name, subj_code, prog_str, f"AMBIGUOUS: {candidates}"))
                continue
            else:
                unmatched.append((subj_id, subj_name, subj_code, prog_str, "NO MATCH"))
                continue

        # Check for duplicate
        cursor.execute(
            "SELECT id FROM program_subjects WHERE program_id = ? AND subject_id = ?;",
            (prog_id, subj_id)
        )
        if cursor.fetchone():
            skipped_dup += 1
            continue

        # Insert mapping
        cursor.execute(
            """INSERT INTO program_subjects (program_id, subject_id, semester, sort_order, is_active, created_at)
               VALUES (?, ?, ?, 0, 1, CURRENT_TIMESTAMP);""",
            (prog_id, subj_id, semester)
        )
        matched += 1

    conn.commit()

    print(f"  Mappings created: {matched}")
    print(f"  Duplicates skipped: {skipped_dup}")
    print(f"  Unmatched subjects: {len(unmatched)}")

    if unmatched:
        print("\n  [REVIEW REQUIRED] Unmatched subjects (not auto-mapped):")
        for row in unmatched:
            print(f"    Subject ID={row[0]}, Name={row[1]!r}, Code={row[2]!r}, program={row[3]!r} -> {row[4]}")

    # ── Step 7: Final count check ─────────────────────────────────────────────
    print("\n[STEP 7] Post-migration count check...")
    final = get_counts(cursor)
    all_ok = True
    for table in CURRICULUM_MINIMUMS:
        before = baseline.get(table, 0)
        after = final.get(table, 0)
        status = "[OK]" if after >= CURRICULUM_MINIMUMS[table] else "[FAIL]"
        change = f"(+{after-before})" if after > before else ("(UNCHANGED)" if after == before else f"[!!DECREASED by {before-after}]")
        print(f"  {table:35s}: {before} -> {after} {change} {status}")
        if after < before:
            all_ok = False

    if not all_ok:
        print("\n[FAIL] COUNT DECREASED — restoring backup automatically")
        conn.close()
        shutil.copy2(backup_path, DB_PATH)
        print(f"[RESTORED] Restored database from {backup_path}")
        sys.exit(1)

    # Verify program_subjects
    cursor.execute("SELECT COUNT(*) FROM program_subjects;")
    ps_count = cursor.fetchone()[0]
    print(f"\n  program_subjects rows: {ps_count}")

    conn.execute("PRAGMA foreign_keys = ON;")
    conn.close()

    print("\n" + "=" * 60)
    print("PHASE 1 MIGRATION COMPLETE")
    print(f"  Backup: {backup_path}")
    print(f"  ProgramSubject mappings created: {matched}")
    print(f"  Unmatched subjects requiring admin review: {len(unmatched)}")
    print("=" * 60)


if __name__ == '__main__':
    main()
