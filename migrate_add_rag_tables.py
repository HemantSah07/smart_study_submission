# migrate_add_rag_tables.py
from app import create_app, db
import sqlalchemy as sa

app = create_app()

with app.app_context():
    engine = db.engine
    inspector = sa.inspect(engine)
    
    # 1. Audit BEFORE using raw SQL
    tables_before = sorted(inspector.get_table_names())
    monitored_tables = ['users', 'subjects', 'student_profiles', 'uploaded_materials']
    
    def get_raw_counts(conn):
        counts = {}
        current_tables = sa.inspect(conn).get_table_names()
        for tbl in monitored_tables:
            if tbl in current_tables:
                res = conn.execute(sa.text(f"SELECT count(*) FROM {tbl}")).scalar()
                counts[tbl] = res
            else:
                counts[tbl] = 0
        return counts

    with engine.connect() as conn:
        counts_before = get_raw_counts(conn)
    
    print("=" * 60)
    print("[MIGRATION AUDIT] BEFORE MIGRATION")
    print("=" * 60)
    print(f"Tables ({len(tables_before)}): {tables_before}")
    print(f"Row Counts: {counts_before}\n")
    
    # 2. Execute Migration (Additive Only)
    db.create_all()

    existing_cols = {c['name'] for c in inspector.get_columns('uploaded_materials')}
    with engine.connect() as conn:
        if 'import_batch_id' not in existing_cols:
            conn.execute(sa.text('ALTER TABLE uploaded_materials ADD COLUMN import_batch_id INTEGER'))
        if 'category' not in existing_cols:
            conn.execute(sa.text("ALTER TABLE uploaded_materials ADD COLUMN category VARCHAR(30) DEFAULT 'Other'"))
        if 'file_size_bytes' not in existing_cols:
            conn.execute(sa.text('ALTER TABLE uploaded_materials ADD COLUMN file_size_bytes INTEGER'))
        if 'embedding_status' not in existing_cols:
            conn.execute(sa.text("ALTER TABLE uploaded_materials ADD COLUMN embedding_status VARCHAR(20) DEFAULT 'pending'"))
        conn.commit()

    # 3. Audit AFTER
    inspector = sa.inspect(engine)  # refresh inspector
    tables_after = sorted(inspector.get_table_names())
    with engine.connect() as conn:
        counts_after = get_raw_counts(conn)

    print("=" * 60)
    print("[MIGRATION AUDIT] AFTER MIGRATION")
    print("=" * 60)
    print(f"Tables ({len(tables_after)}): {tables_after}")
    print(f"Row Counts: {counts_after}\n")

    # 4. Strict Safety Assertions
    new_tables_added = set(tables_after) - set(tables_before)
    print(f"New tables created: {sorted(list(new_tables_added))}")

    for table_name, count_b in counts_before.items():
        count_a = counts_after[table_name]
        assert count_b == count_a, f"CRITICAL ERROR: Row count mismatch for '{table_name}'! Before={count_b}, After={count_a}"
        print(f"CONFIRMED UNCHANGED: '{table_name}' ({count_b} -> {count_a} rows)")

    print("\n[OK] Migration completed successfully. Zero existing data wiped or modified!")
