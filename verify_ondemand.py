import time
from app import create_app, db
app = create_app()

print("Smart Study On-Demand Generation Test started.")
print("Spaced 75 seconds apart to respect rate limits.")
print("-" * 60)

with app.app_context():
    from app.routes.student import generate_assessment_questions_for_subject
    from app.models import Subject, AssessmentQuestion

    # Subject IDs to test
    test_cases = [
        (342, "Social Studies - Class 9"),
        (230, "Biology - Class 11 Science"),
        (334, "BCA Core III - Bachelor's BCA")
    ]

    results = []

    for i, (sid, label) in enumerate(test_cases):
        if i > 0:
            print("Sleeping for 75 seconds to avoid 429 rate limit...")
            time.sleep(75)

        s = Subject.query.get(sid)
        if not s:
            print(f"Error: Subject ID {sid} not found in database.")
            results.append((sid, label, "FAIL (Subject not found)"))
            continue

        before = AssessmentQuestion.query.filter_by(subject_id=sid).count()
        print(f"Generating questions for '{s.name}' ({s.level_of_study})...")
        
        try:
            count = generate_assessment_questions_for_subject(sid)
            after = AssessmentQuestion.query.filter_by(subject_id=sid).count()
            if count > 0 and after >= 15:
                status = "Yes (Generated %d questions)" % count
            else:
                status = "No (Generated %d questions)" % count
        except Exception as e:
            status = f"No (Exception: {str(e)[:30]})"

        print(f"Result: {status}")
        results.append((s.level_of_study, s.program or "General", s.name, status))

print("\n" + "="*80)
print("ON-DEMAND VERIFICATION RESULTS TABLE")
print("="*80)
print("%-25s | %-18s | %-20s | %s" % ("Class Level", "Faculty/Program", "Subject Tested", "Loaded Successfully?"))
print("-" * 80)
for level, prog, name, status in results:
    print("%-25s | %-18s | %-20s | %s" % (
        str(level)[:25], str(prog)[:18], str(name)[:20], status
    ))
