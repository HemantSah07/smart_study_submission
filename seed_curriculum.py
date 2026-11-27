"""
seed_curriculum.py
One-time seeding of curriculum taxonomy tables (Section 1).
- Normalizes existing subjects.level_of_study to canonical strings.
- Seeds EducationLevel, University, Faculty, CurriculumProgram from
  the hardcoded values previously in profile-fields.js and templates.
Run once: venv\Scripts\python.exe seed_curriculum.py
"""
import json
from app import create_app, db
from app.models import EducationLevel, University, Faculty, CurriculumProgram, Subject

app = create_app()

# ── Canonical level normalisation map ────────────────────────────────────────
LEVEL_MAP = {
    "Class 6":                                          "Class 6",
    "Class 7":                                          "Class 7",
    "Class 8":                                          "Class 8",
    "Class 9":                                          "Class 9",
    "Class 10 (Secondary Education Examination - SEE)": "Class 10",
    "Class 10 (SEE)":                                   "Class 10",
    "Class 10":                                         "Class 10",
    "Class 11 - Science Stream":                        "Class 11",
    "Class 11 - Management Stream":                     "Class 11",
    "Class 11 - Humanities Stream":                     "Class 11",
    "Class 11":                                         "Class 11",
    "Class 12 (National Examination Board - NEB)":      "Class 12",
    "Class 12 - Science Stream":                        "Class 12",
    "Class 12 - Management Stream":                     "Class 12",
    "Class 12 - Humanities Stream":                     "Class 12",
    "Class 12":                                         "Class 12",
    "Bachelor's":                                       "Bachelors",
    "Bachelors":                                        "Bachelors",
    "University Year 1":                                "Bachelors",
    "University Year 2":                                "Bachelors",
    "University Year 3":                                "Bachelors",
    "University Year 4":                                "Bachelors",
    "Master's":                                         "Masters",
    "Master's Level":                                   "Masters",
    "Masters":                                          "Masters",
}

EDUCATION_LEVELS = [
    {"name": "Class 6",   "country": "Nepal", "sort_order": 1},
    {"name": "Class 7",   "country": "Nepal", "sort_order": 2},
    {"name": "Class 8",   "country": "Nepal", "sort_order": 3},
    {"name": "Class 9",   "country": "Nepal", "sort_order": 4},
    {"name": "Class 10",  "country": "Nepal", "sort_order": 5},
    {"name": "Class 11",  "country": "Nepal", "sort_order": 6},
    {"name": "Class 12",  "country": "Nepal", "sort_order": 7},
    {"name": "Bachelors", "country": "Nepal", "sort_order": 8},
    {"name": "Masters",   "country": "Nepal", "sort_order": 9},
]

UNIVERSITIES = [
    {"name": "Tribhuvan University (TU)",                "abbreviation": "TU",   "country": "Nepal", "sort_order": 1},
    {"name": "Kathmandu University (KU)",                "abbreviation": "KU",   "country": "Nepal", "sort_order": 2},
    {"name": "Purbanchal University (PU)",               "abbreviation": "PU",   "country": "Nepal", "sort_order": 3},
    {"name": "Pokhara University (PokU)",                "abbreviation": "PokU", "country": "Nepal", "sort_order": 4},
    {"name": "Mid-Western University",                   "abbreviation": "MWU",  "country": "Nepal", "sort_order": 5},
    {"name": "Far-Western University",                   "abbreviation": "FWU",  "country": "Nepal", "sort_order": 6},
    {"name": "Agriculture and Forestry University (AFU)","abbreviation": "AFU",  "country": "Nepal", "sort_order": 7},
    {"name": "Nepal Sanskrit University",                "abbreviation": "NSU",  "country": "Nepal", "sort_order": 8},
    {"name": "Foreign-Affiliated",                       "abbreviation": None,   "country": "Nepal", "sort_order": 9},
    {"name": "Other",                                    "abbreviation": None,   "country": "Nepal", "sort_order": 10},
]

FACULTIES = [
    {"name": "Science Faculty",                               "level_name": None, "sort_order": 1},
    {"name": "Management Faculty (Commerce)",                 "level_name": None, "sort_order": 2},
    {"name": "Humanities and Social Sciences Faculty (Arts)", "level_name": None, "sort_order": 3},
    {"name": "Law Faculty",                                   "level_name": None, "sort_order": 4},
    {"name": "Education Faculty",                             "level_name": None, "sort_order": 5},
    {"name": "Computer Engineering",                          "level_name": None, "sort_order": 6},
    {"name": "Civil Engineering",                             "level_name": None, "sort_order": 7},
    {"name": "Electrical/Electronics Engineering",            "level_name": None, "sort_order": 8},
    {"name": "Agriculture and Animal Science",                "level_name": None, "sort_order": 9},
    {"name": "Forestry",                                      "level_name": None, "sort_order": 10},
    {"name": "Nursing (PCL Nursing)",                         "level_name": None, "sort_order": 11},
    {"name": "Pharmacy",                                      "level_name": None, "sort_order": 12},
    {"name": "Medical Lab Technology (CMLT)",                 "level_name": None, "sort_order": 13},
    {"name": "Hotel Management & Culinary Arts",              "level_name": None, "sort_order": 14},
]

BACHELORS_PROGRAMS = [
    {"name": "BBA",         "has_duration": False, "duration_options_json": None, "sort_order": 1},
    {"name": "BCA",         "has_duration": False, "duration_options_json": None, "sort_order": 2},
    {"name": "BE Computer", "has_duration": False, "duration_options_json": None, "sort_order": 3},
    {"name": "BE Civil",    "has_duration": False, "duration_options_json": None, "sort_order": 4},
    {"name": "BIT",         "has_duration": False, "duration_options_json": None, "sort_order": 5},
    {"name": "BSc IT",      "has_duration": True,  "duration_options_json": json.dumps([
        {"value": "3 Years", "label": "3 Years (International-affiliated, e.g. APU/LBEF)"},
        {"value": "4 Years", "label": "4 Years (TU-affiliated BSc CSIT)"},
    ]), "sort_order": 6},
    {"name": "BSc CSIT",    "has_duration": False, "duration_options_json": None, "sort_order": 7},
    {"name": "BSc Nursing", "has_duration": False, "duration_options_json": None, "sort_order": 8},
    {"name": "BTech",       "has_duration": False, "duration_options_json": None, "sort_order": 9},
    {"name": "MBBS",        "has_duration": False, "duration_options_json": None, "sort_order": 10},
]

MASTERS_PROGRAMS = [
    {"name": "MBA",                  "sort_order": 1},
    {"name": "MCA",                  "sort_order": 2},
    {"name": "MIT",                  "sort_order": 3},
    {"name": "MSc Computer Science", "sort_order": 4},
]


with app.app_context():
    print("=== Normalizing subject level_of_study strings ===")
    subjects = Subject.query.all()
    changed = 0
    for s in subjects:
        if s.level_of_study and s.level_of_study in LEVEL_MAP:
            canonical = LEVEL_MAP[s.level_of_study]
            if canonical != s.level_of_study:
                s.level_of_study = canonical
                changed += 1
    db.session.commit()
    print(f"  Normalized {changed} subject records.")

    print("\n=== Seeding EducationLevel ===")
    count = 0
    for row in EDUCATION_LEVELS:
        if not EducationLevel.query.filter_by(name=row["name"], country=row["country"]).first():
            db.session.add(EducationLevel(**row))
            count += 1
    db.session.commit()
    print(f"  Added {count} education levels (total: {EducationLevel.query.count()})")

    print("\n=== Seeding University ===")
    count = 0
    for row in UNIVERSITIES:
        if not University.query.filter_by(name=row["name"], country=row["country"]).first():
            db.session.add(University(**row))
            count += 1
    db.session.commit()
    print(f"  Added {count} universities (total: {University.query.count()})")

    print("\n=== Seeding Faculty ===")
    count = 0
    for row in FACULTIES:
        if not Faculty.query.filter_by(name=row["name"], country="Nepal").first():
            db.session.add(Faculty(country="Nepal", **row))
            count += 1
    db.session.commit()
    print(f"  Added {count} faculties (total: {Faculty.query.count()})")

    print("\n=== Seeding CurriculumProgram (Bachelors) ===")
    count = 0
    for row in BACHELORS_PROGRAMS:
        if not CurriculumProgram.query.filter_by(name=row["name"], level_name="Bachelors", country="Nepal").first():
            db.session.add(CurriculumProgram(level_name="Bachelors", country="Nepal", **row))
            count += 1
    db.session.commit()
    print(f"  Added {count} Bachelors programs (total: {CurriculumProgram.query.filter_by(level_name='Bachelors').count()})")

    print("\n=== Seeding CurriculumProgram (Masters) ===")
    count = 0
    for row in MASTERS_PROGRAMS:
        if not CurriculumProgram.query.filter_by(name=row["name"], level_name="Masters", country="Nepal").first():
            db.session.add(CurriculumProgram(
                level_name="Masters", country="Nepal",
                has_duration=False, duration_options_json=None, **row))
            count += 1
    db.session.commit()
    print(f"  Added {count} Masters programs (total: {CurriculumProgram.query.filter_by(level_name='Masters').count()})")

    print("\n=== Seeding complete! ===")
