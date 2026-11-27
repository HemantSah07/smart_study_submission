"""
seed_subjects_full.py
Comprehensive seeding of all Subject records across all curriculum levels.
- Clears/updates the 12 old APU CSV subjects that have level_of_study=None
  (tags them as Bachelors/BSc IT so they appear in the admin panel)
- Seeds complete subjects for Class 6 through Masters
- Safe to re-run (idempotent: uses upsert by name+level+program)

Run: venv\Scripts\python.exe seed_subjects_full.py
"""
import json
from app import create_app, db
from app.models import Subject

app = create_app()

# ── Full subject catalogue ────────────────────────────────────────────────────

CLASS_6_SUBJECTS = [
    {"name": "Nepali",                "code": "NP-601",  "semester": "Class 6", "program": "General", "credit_hours": 4, "difficulty_level": 2},
    {"name": "English",               "code": "EN-601",  "semester": "Class 6", "program": "General", "credit_hours": 4, "difficulty_level": 2},
    {"name": "Mathematics",           "code": "MA-601",  "semester": "Class 6", "program": "General", "credit_hours": 4, "difficulty_level": 3},
    {"name": "Science and Technology","code": "SC-601",  "semester": "Class 6", "program": "General", "credit_hours": 4, "difficulty_level": 3},
    {"name": "Social Studies",        "code": "SS-601",  "semester": "Class 6", "program": "General", "credit_hours": 3, "difficulty_level": 2},
    {"name": "Health, Population and Environment", "code": "HP-601", "semester": "Class 6", "program": "General", "credit_hours": 3, "difficulty_level": 2},
]

CLASS_7_SUBJECTS = [
    {"name": "Nepali",                "code": "NP-701",  "semester": "Class 7", "program": "General", "credit_hours": 4, "difficulty_level": 2},
    {"name": "English",               "code": "EN-701",  "semester": "Class 7", "program": "General", "credit_hours": 4, "difficulty_level": 2},
    {"name": "Mathematics",           "code": "MA-701",  "semester": "Class 7", "program": "General", "credit_hours": 4, "difficulty_level": 3},
    {"name": "Science and Technology","code": "SC-701",  "semester": "Class 7", "program": "General", "credit_hours": 4, "difficulty_level": 3},
    {"name": "Social Studies",        "code": "SS-701",  "semester": "Class 7", "program": "General", "credit_hours": 3, "difficulty_level": 2},
    {"name": "Health, Population and Environment", "code": "HP-701", "semester": "Class 7", "program": "General", "credit_hours": 3, "difficulty_level": 2},
]

CLASS_8_SUBJECTS = [
    {"name": "Nepali",                "code": "NP-801",  "semester": "Class 8", "program": "General", "credit_hours": 4, "difficulty_level": 2},
    {"name": "English",               "code": "EN-801",  "semester": "Class 8", "program": "General", "credit_hours": 4, "difficulty_level": 2},
    {"name": "Mathematics",           "code": "MA-801",  "semester": "Class 8", "program": "General", "credit_hours": 4, "difficulty_level": 3},
    {"name": "Science and Technology","code": "SC-801",  "semester": "Class 8", "program": "General", "credit_hours": 4, "difficulty_level": 3},
    {"name": "Social Studies",        "code": "SS-801",  "semester": "Class 8", "program": "General", "credit_hours": 3, "difficulty_level": 2},
    {"name": "Health, Population and Environment", "code": "HP-801", "semester": "Class 8", "program": "General", "credit_hours": 3, "difficulty_level": 2},
    {"name": "Optional Mathematics",  "code": "OM-801",  "semester": "Class 8", "program": "General", "credit_hours": 3, "difficulty_level": 3},
]

CLASS_9_SUBJECTS = [
    # Already seeded (ids 13-20), skip to avoid duplication — handled by upsert logic
    {"name": "Nepali",                "code": "NP-901",  "semester": "Class 9", "program": "General", "credit_hours": 4, "difficulty_level": 2},
    {"name": "English",               "code": "EN-901",  "semester": "Class 9", "program": "General", "credit_hours": 4, "difficulty_level": 2},
    {"name": "Mathematics",           "code": "MA-901",  "semester": "Class 9", "program": "General", "credit_hours": 4, "difficulty_level": 3},
    {"name": "Science",               "code": "SC-901",  "semester": "Class 9", "program": "General", "credit_hours": 4, "difficulty_level": 3},
    {"name": "Social Studies",        "code": "SS-901",  "semester": "Class 9", "program": "General", "credit_hours": 3, "difficulty_level": 2},
    {"name": "Health and Population", "code": "HP-901",  "semester": "Class 9", "program": "General", "credit_hours": 3, "difficulty_level": 2},
    {"name": "Optional Mathematics",  "code": "OM-901",  "semester": "Class 9", "program": "General", "credit_hours": 3, "difficulty_level": 3},
    {"name": "Computer Science",      "code": "CS-901",  "semester": "Class 9", "program": "General", "credit_hours": 3, "difficulty_level": 3},
]

CLASS_10_SUBJECTS = [
    {"name": "Nepali",                "code": "NP-101",  "semester": "Class 10", "program": "General", "credit_hours": 4, "difficulty_level": 2},
    {"name": "English",               "code": "EN-101",  "semester": "Class 10", "program": "General", "credit_hours": 4, "difficulty_level": 2},
    {"name": "Mathematics",           "code": "MA-101",  "semester": "Class 10", "program": "General", "credit_hours": 4, "difficulty_level": 4},
    {"name": "Science",               "code": "SC-101",  "semester": "Class 10", "program": "General", "credit_hours": 4, "difficulty_level": 4},
    {"name": "Social Studies",        "code": "SS-101",  "semester": "Class 10", "program": "General", "credit_hours": 3, "difficulty_level": 2},
    {"name": "Health and Population", "code": "HP-101",  "semester": "Class 10", "program": "General", "credit_hours": 3, "difficulty_level": 2},
    {"name": "Optional Mathematics",  "code": "OM-101",  "semester": "Class 10", "program": "General", "credit_hours": 3, "difficulty_level": 4},
    {"name": "Computer Science",      "code": "CS-101",  "semester": "Class 10", "program": "General", "credit_hours": 3, "difficulty_level": 3},
]

# Class 11 — Science faculty
CLASS_11_SCIENCE = [
    {"name": "Physics",               "code": "PH-111",  "semester": "Class 11", "program": "Science Faculty", "credit_hours": 4, "difficulty_level": 4},
    {"name": "Chemistry",             "code": "CH-111",  "semester": "Class 11", "program": "Science Faculty", "credit_hours": 4, "difficulty_level": 4},
    {"name": "Mathematics",           "code": "MA-111",  "semester": "Class 11", "program": "Science Faculty", "credit_hours": 4, "difficulty_level": 5},
    {"name": "Biology",               "code": "BI-111",  "semester": "Class 11", "program": "Science Faculty", "credit_hours": 4, "difficulty_level": 4},
    {"name": "English",               "code": "EN-111",  "semester": "Class 11", "program": "Science Faculty", "credit_hours": 3, "difficulty_level": 2},
    {"name": "Computer Science",      "code": "CS-111",  "semester": "Class 11", "program": "Science Faculty", "credit_hours": 3, "difficulty_level": 3},
]

# Class 11 — Management faculty
CLASS_11_MANAGEMENT = [
    {"name": "Business Studies",      "code": "BS-111",  "semester": "Class 11", "program": "Management Faculty (Commerce)", "credit_hours": 4, "difficulty_level": 3},
    {"name": "Accountancy",           "code": "AC-111",  "semester": "Class 11", "program": "Management Faculty (Commerce)", "credit_hours": 4, "difficulty_level": 4},
    {"name": "Economics",             "code": "EC-111",  "semester": "Class 11", "program": "Management Faculty (Commerce)", "credit_hours": 4, "difficulty_level": 3},
    {"name": "Mathematics",           "code": "MA-111M", "semester": "Class 11", "program": "Management Faculty (Commerce)", "credit_hours": 4, "difficulty_level": 4},
    {"name": "English",               "code": "EN-111M", "semester": "Class 11", "program": "Management Faculty (Commerce)", "credit_hours": 3, "difficulty_level": 2},
    {"name": "Computer Application",  "code": "CA-111",  "semester": "Class 11", "program": "Management Faculty (Commerce)", "credit_hours": 3, "difficulty_level": 2},
]

# Class 11 — Humanities faculty
CLASS_11_HUMANITIES = [
    {"name": "Nepali Literature",     "code": "NL-111",  "semester": "Class 11", "program": "Humanities and Social Sciences Faculty (Arts)", "credit_hours": 4, "difficulty_level": 2},
    {"name": "English",               "code": "EN-111H", "semester": "Class 11", "program": "Humanities and Social Sciences Faculty (Arts)", "credit_hours": 4, "difficulty_level": 2},
    {"name": "History",               "code": "HI-111",  "semester": "Class 11", "program": "Humanities and Social Sciences Faculty (Arts)", "credit_hours": 4, "difficulty_level": 2},
    {"name": "Geography",             "code": "GE-111",  "semester": "Class 11", "program": "Humanities and Social Sciences Faculty (Arts)", "credit_hours": 4, "difficulty_level": 2},
    {"name": "Economics",             "code": "EC-111H", "semester": "Class 11", "program": "Humanities and Social Sciences Faculty (Arts)", "credit_hours": 3, "difficulty_level": 3},
    {"name": "Social Studies",        "code": "SS-111H", "semester": "Class 11", "program": "Humanities and Social Sciences Faculty (Arts)", "credit_hours": 3, "difficulty_level": 2},
]

# Class 12 — Science faculty
CLASS_12_SCIENCE = [
    {"name": "Physics",               "code": "PH-121",  "semester": "Class 12", "program": "Science Faculty", "credit_hours": 4, "difficulty_level": 5},
    {"name": "Chemistry",             "code": "CH-121",  "semester": "Class 12", "program": "Science Faculty", "credit_hours": 4, "difficulty_level": 5},
    {"name": "Mathematics",           "code": "MA-121",  "semester": "Class 12", "program": "Science Faculty", "credit_hours": 4, "difficulty_level": 5},
    {"name": "Biology",               "code": "BI-121",  "semester": "Class 12", "program": "Science Faculty", "credit_hours": 4, "difficulty_level": 4},
    {"name": "English",               "code": "EN-121",  "semester": "Class 12", "program": "Science Faculty", "credit_hours": 3, "difficulty_level": 2},
    {"name": "Computer Science",      "code": "CS-121",  "semester": "Class 12", "program": "Science Faculty", "credit_hours": 3, "difficulty_level": 3},
]

# Class 12 — Management faculty
CLASS_12_MANAGEMENT = [
    {"name": "Business Studies",      "code": "BS-121",  "semester": "Class 12", "program": "Management Faculty (Commerce)", "credit_hours": 4, "difficulty_level": 3},
    {"name": "Accountancy",           "code": "AC-121",  "semester": "Class 12", "program": "Management Faculty (Commerce)", "credit_hours": 4, "difficulty_level": 4},
    {"name": "Economics",             "code": "EC-121",  "semester": "Class 12", "program": "Management Faculty (Commerce)", "credit_hours": 4, "difficulty_level": 3},
    {"name": "Mathematics",           "code": "MA-121M", "semester": "Class 12", "program": "Management Faculty (Commerce)", "credit_hours": 4, "difficulty_level": 4},
    {"name": "English",               "code": "EN-121M", "semester": "Class 12", "program": "Management Faculty (Commerce)", "credit_hours": 3, "difficulty_level": 2},
    {"name": "Computer Application",  "code": "CA-121",  "semester": "Class 12", "program": "Management Faculty (Commerce)", "credit_hours": 3, "difficulty_level": 2},
]

# Class 12 — Humanities faculty
CLASS_12_HUMANITIES = [
    {"name": "Nepali Literature",     "code": "NL-121",  "semester": "Class 12", "program": "Humanities and Social Sciences Faculty (Arts)", "credit_hours": 4, "difficulty_level": 2},
    {"name": "English",               "code": "EN-121H", "semester": "Class 12", "program": "Humanities and Social Sciences Faculty (Arts)", "credit_hours": 4, "difficulty_level": 2},
    {"name": "History",               "code": "HI-121",  "semester": "Class 12", "program": "Humanities and Social Sciences Faculty (Arts)", "credit_hours": 4, "difficulty_level": 2},
    {"name": "Geography",             "code": "GE-121",  "semester": "Class 12", "program": "Humanities and Social Sciences Faculty (Arts)", "credit_hours": 4, "difficulty_level": 2},
    {"name": "Economics",             "code": "EC-121H", "semester": "Class 12", "program": "Humanities and Social Sciences Faculty (Arts)", "credit_hours": 3, "difficulty_level": 3},
    {"name": "Sociology",             "code": "SO-121",  "semester": "Class 12", "program": "Humanities and Social Sciences Faculty (Arts)", "credit_hours": 3, "difficulty_level": 2},
]

# Bachelors — BSc CSIT (TU, 4 years / 8 semesters)
BACHELORS_BSCCSIT = [
    {"name": "Introduction to Information Technology", "code": "CSIT-101", "semester": "Semester 1", "program": "BSc CSIT", "credit_hours": 3, "difficulty_level": 2},
    {"name": "Mathematics I",                         "code": "CSIT-102", "semester": "Semester 1", "program": "BSc CSIT", "credit_hours": 3, "difficulty_level": 4},
    {"name": "Physics",                               "code": "CSIT-103", "semester": "Semester 1", "program": "BSc CSIT", "credit_hours": 3, "difficulty_level": 3},
    {"name": "Digital Logic",                         "code": "CSIT-104", "semester": "Semester 1", "program": "BSc CSIT", "credit_hours": 3, "difficulty_level": 3},
    {"name": "Probability and Statistics",            "code": "CSIT-201", "semester": "Semester 2", "program": "BSc CSIT", "credit_hours": 3, "difficulty_level": 3},
    {"name": "C Programming",                        "code": "CSIT-202", "semester": "Semester 2", "program": "BSc CSIT", "credit_hours": 3, "difficulty_level": 3},
    {"name": "Data Structures and Algorithms",        "code": "CSIT-301", "semester": "Semester 3", "program": "BSc CSIT", "credit_hours": 3, "difficulty_level": 4},
    {"name": "Object-Oriented Programming",           "code": "CSIT-302", "semester": "Semester 3", "program": "BSc CSIT", "credit_hours": 3, "difficulty_level": 4},
    {"name": "Operating Systems",                     "code": "CSIT-401", "semester": "Semester 4", "program": "BSc CSIT", "credit_hours": 3, "difficulty_level": 4},
    {"name": "Computer Networks",                     "code": "CSIT-402", "semester": "Semester 4", "program": "BSc CSIT", "credit_hours": 3, "difficulty_level": 3},
    {"name": "Database Management Systems",           "code": "CSIT-501", "semester": "Semester 5", "program": "BSc CSIT", "credit_hours": 3, "difficulty_level": 4},
    {"name": "Web Technology",                        "code": "CSIT-502", "semester": "Semester 5", "program": "BSc CSIT", "credit_hours": 3, "difficulty_level": 3},
    {"name": "Artificial Intelligence",               "code": "CSIT-601", "semester": "Semester 6", "program": "BSc CSIT", "credit_hours": 3, "difficulty_level": 5},
    {"name": "Software Engineering",                  "code": "CSIT-602", "semester": "Semester 6", "program": "BSc CSIT", "credit_hours": 3, "difficulty_level": 3},
    {"name": "Distributed System",                    "code": "CSIT-701", "semester": "Semester 7", "program": "BSc CSIT", "credit_hours": 3, "difficulty_level": 4},
    {"name": "Information Security",                  "code": "CSIT-702", "semester": "Semester 7", "program": "BSc CSIT", "credit_hours": 3, "difficulty_level": 4},
    {"name": "Project Work",                          "code": "CSIT-801", "semester": "Semester 8", "program": "BSc CSIT", "credit_hours": 6, "difficulty_level": 5},
    {"name": "Advanced Topics in CS",                 "code": "CSIT-802", "semester": "Semester 8", "program": "BSc CSIT", "credit_hours": 3, "difficulty_level": 5},
]

# Bachelors — BBA (TU, 4 years / 8 semesters)
BACHELORS_BBA = [
    {"name": "Principles of Management",              "code": "BBA-101", "semester": "Semester 1", "program": "BBA", "credit_hours": 3, "difficulty_level": 2},
    {"name": "Business English",                      "code": "BBA-102", "semester": "Semester 1", "program": "BBA", "credit_hours": 3, "difficulty_level": 2},
    {"name": "Business Mathematics",                  "code": "BBA-103", "semester": "Semester 1", "program": "BBA", "credit_hours": 3, "difficulty_level": 3},
    {"name": "Microeconomics",                        "code": "BBA-201", "semester": "Semester 2", "program": "BBA", "credit_hours": 3, "difficulty_level": 3},
    {"name": "Business Communication",                "code": "BBA-202", "semester": "Semester 2", "program": "BBA", "credit_hours": 3, "difficulty_level": 2},
    {"name": "Financial Accounting",                  "code": "BBA-301", "semester": "Semester 3", "program": "BBA", "credit_hours": 3, "difficulty_level": 4},
    {"name": "Marketing Management",                  "code": "BBA-401", "semester": "Semester 4", "program": "BBA", "credit_hours": 3, "difficulty_level": 3},
    {"name": "Human Resource Management",             "code": "BBA-501", "semester": "Semester 5", "program": "BBA", "credit_hours": 3, "difficulty_level": 3},
    {"name": "Strategic Management",                  "code": "BBA-601", "semester": "Semester 6", "program": "BBA", "credit_hours": 3, "difficulty_level": 4},
    {"name": "Entrepreneurship",                      "code": "BBA-701", "semester": "Semester 7", "program": "BBA", "credit_hours": 3, "difficulty_level": 3},
    {"name": "Research Methods",                      "code": "BBA-801", "semester": "Semester 8", "program": "BBA", "credit_hours": 3, "difficulty_level": 4},
]

# Bachelors — BCA (TU, 3 years / 6 semesters)
BACHELORS_BCA = [
    {"name": "Introduction to Computer Science",      "code": "BCA-101", "semester": "Semester 1", "program": "BCA", "credit_hours": 3, "difficulty_level": 2},
    {"name": "Mathematics I",                         "code": "BCA-102", "semester": "Semester 1", "program": "BCA", "credit_hours": 3, "difficulty_level": 3},
    {"name": "Digital Logic",                         "code": "BCA-201", "semester": "Semester 2", "program": "BCA", "credit_hours": 3, "difficulty_level": 3},
    {"name": "Programming in C",                      "code": "BCA-202", "semester": "Semester 2", "program": "BCA", "credit_hours": 3, "difficulty_level": 3},
    {"name": "Data Structures",                       "code": "BCA-301", "semester": "Semester 3", "program": "BCA", "credit_hours": 3, "difficulty_level": 4},
    {"name": "Object-Oriented Programming with Java", "code": "BCA-302", "semester": "Semester 3", "program": "BCA", "credit_hours": 3, "difficulty_level": 4},
    {"name": "Database Systems",                      "code": "BCA-401", "semester": "Semester 4", "program": "BCA", "credit_hours": 3, "difficulty_level": 3},
    {"name": "Web Programming",                       "code": "BCA-402", "semester": "Semester 4", "program": "BCA", "credit_hours": 3, "difficulty_level": 3},
    {"name": "Software Engineering",                  "code": "BCA-501", "semester": "Semester 5", "program": "BCA", "credit_hours": 3, "difficulty_level": 3},
    {"name": "Computer Networks",                     "code": "BCA-502", "semester": "Semester 5", "program": "BCA", "credit_hours": 3, "difficulty_level": 3},
    {"name": "Project Work",                          "code": "BCA-601", "semester": "Semester 6", "program": "BCA", "credit_hours": 6, "difficulty_level": 4},
]

# Masters — MBA
MASTERS_MBA = [
    {"name": "Management Theory and Organizational Behaviour", "code": "MBA-501", "semester": "Semester 1", "program": "MBA", "credit_hours": 3, "difficulty_level": 3},
    {"name": "Managerial Economics",                           "code": "MBA-502", "semester": "Semester 1", "program": "MBA", "credit_hours": 3, "difficulty_level": 4},
    {"name": "Financial Reporting and Analysis",               "code": "MBA-503", "semester": "Semester 1", "program": "MBA", "credit_hours": 3, "difficulty_level": 4},
    {"name": "Marketing Management",                          "code": "MBA-601", "semester": "Semester 2", "program": "MBA", "credit_hours": 3, "difficulty_level": 3},
    {"name": "Research Methods for Management",               "code": "MBA-602", "semester": "Semester 2", "program": "MBA", "credit_hours": 3, "difficulty_level": 4},
    {"name": "Strategic Management",                          "code": "MBA-701", "semester": "Semester 3", "program": "MBA", "credit_hours": 3, "difficulty_level": 5},
    {"name": "Leadership and Change Management",              "code": "MBA-702", "semester": "Semester 3", "program": "MBA", "credit_hours": 3, "difficulty_level": 4},
    {"name": "Thesis",                                        "code": "MBA-801", "semester": "Semester 4", "program": "MBA", "credit_hours": 6, "difficulty_level": 5},
]

# Masters — MCA / MSc Computer Science
MASTERS_MCA = [
    {"name": "Advanced Algorithms",                           "code": "MCA-501", "semester": "Semester 1", "program": "MCA", "credit_hours": 3, "difficulty_level": 5},
    {"name": "Advanced Database Systems",                     "code": "MCA-502", "semester": "Semester 1", "program": "MCA", "credit_hours": 3, "difficulty_level": 4},
    {"name": "Machine Learning",                              "code": "MCA-601", "semester": "Semester 2", "program": "MCA", "credit_hours": 3, "difficulty_level": 5},
    {"name": "Cloud Computing",                               "code": "MCA-602", "semester": "Semester 2", "program": "MCA", "credit_hours": 3, "difficulty_level": 4},
    {"name": "Artificial Intelligence",                       "code": "MCA-701", "semester": "Semester 3", "program": "MCA", "credit_hours": 3, "difficulty_level": 5},
    {"name": "Cybersecurity",                                 "code": "MCA-702", "semester": "Semester 3", "program": "MCA", "credit_hours": 3, "difficulty_level": 5},
    {"name": "Dissertation",                                  "code": "MCA-801", "semester": "Semester 4", "program": "MCA", "credit_hours": 6, "difficulty_level": 5},
]


# ── Catalogue map: (level, subjects_list) ───────────────────────────────────
CATALOGUE = [
    ("Class 6",    CLASS_6_SUBJECTS),
    ("Class 7",    CLASS_7_SUBJECTS),
    ("Class 8",    CLASS_8_SUBJECTS),
    ("Class 9",    CLASS_9_SUBJECTS),
    ("Class 10",   CLASS_10_SUBJECTS),
    ("Class 11",   CLASS_11_SCIENCE + CLASS_11_MANAGEMENT + CLASS_11_HUMANITIES),
    ("Class 12",   CLASS_12_SCIENCE + CLASS_12_MANAGEMENT + CLASS_12_HUMANITIES),
    ("Bachelors",  BACHELORS_BSCCSIT + BACHELORS_BBA + BACHELORS_BCA),
    ("Masters",    MASTERS_MBA + MASTERS_MCA),
]


with app.app_context():
    # Step 1: Fix the 12 old APU CSV subjects (level_of_study=None) — tag them to Bachelors/BSc IT
    print("=== Step 1: Tagging old CSV subjects to Bachelors / BSc CSIT ===")
    old_subjects = Subject.query.filter(Subject.level_of_study == None).all()  # noqa
    for s in old_subjects:
        s.level_of_study = "Bachelors"
        s.program = "BSc CSIT"
        # semester_tag already has value like "1-1", convert to semester label
        if s.semester_tag:
            parts = s.semester_tag.split("-")
            try:
                s.semester = f"Semester {int(parts[1])}"
            except Exception:
                s.semester = s.semester_tag
        s.country = "Nepal"
        s.curriculum = "National"
    db.session.commit()
    print(f"  Tagged {len(old_subjects)} legacy subjects to Bachelors/BSc CSIT.")

    # Step 2: Seed new subjects by level
    print("\n=== Step 2: Seeding full subject catalogue ===")
    total_added = 0
    for level_name, subject_list in CATALOGUE:
        count = 0
        for row in subject_list:
            existing = Subject.query.filter_by(
                name=row["name"],
                level_of_study=level_name,
                program=row.get("program")
            ).first()
            if not existing:
                db.session.add(Subject(
                    name=row["name"],
                    code=row.get("code"),
                    level_of_study=level_name,
                    semester=row.get("semester"),
                    program=row.get("program"),
                    credit_hours=row.get("credit_hours", 3),
                    difficulty_level=row.get("difficulty_level", 3),
                    country="Nepal",
                    curriculum="NEB/CTEVT" if level_name in ("Class 11", "Class 12") else
                               "Primary" if level_name in ("Class 6", "Class 7", "Class 8") else
                               "Lower Secondary" if level_name in ("Class 9", "Class 10") else
                               "National",
                    is_active=True,
                ))
                count += 1
        db.session.commit()
        print(f"  {level_name}: added {count} new subjects")
        total_added += count

    print(f"\n=== Done! Total new subjects added: {total_added} ===")
    print(f"Total subjects now in DB: {Subject.query.count()}")
    
    # Summary by level
    print("\n=== Subject counts by level ===")
    from sqlalchemy import func
    rows = db.session.query(Subject.level_of_study, func.count(Subject.id))\
                     .group_by(Subject.level_of_study)\
                     .order_by(Subject.level_of_study)\
                     .all()
    for level, cnt in rows:
        print(f"  {str(level):12s}: {cnt} subjects")
