"""One-shot project setup: tables, seed data, assessment questions, ML models."""
import subprocess
import sys
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable

STEPS = [
    ("Creating database tables", [PY, os.path.join(ROOT, "init_db.py")]),
    ("Loading seed data", [PY, os.path.join(ROOT, "load_data.py"), "--fresh"]),
    ("Seeding assessment questions", [PY, os.path.join(ROOT, "questions_seed.py")]),
    ("Training ML models", [PY, os.path.join(ROOT, "models", "train_models.py")]),
]


def main():
    for label, cmd in STEPS:
        print(f"\n=== {label} ===")
        result = subprocess.run(cmd, cwd=ROOT)
        if result.returncode != 0:
            print(f"Setup failed during: {label}")
            sys.exit(result.returncode)
    print("\nSetup complete. Run: python run.py")
    print("Demo login: amit.maharjan1@student.apu.edu.my / Student@123")
    print("Admin login: admin701@apu.edu.my / Student@123")


if __name__ == "__main__":
    main()
