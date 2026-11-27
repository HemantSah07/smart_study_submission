import logging
logging.basicConfig(level=logging.WARNING)
from app import create_app, db
app = create_app()

results = []

with app.app_context():
    from app.routes.student import generate_assessment_questions_for_subject
    from app.models import AssessmentQuestion, Subject

    # Representative test matrix covering all required levels
    test_ids = [
        318,  # Science - Class 6
        325,  # Science - Class 7
        341,  # Science - Class 9
        228,  # Physics - Class 11 Science Stream
        229,  # Chemistry - Class 11 Science Stream
        246,  # Accountancy - Class 11 Management
        248,  # Economics - Class 11 Management
        261,  # Physics - Class 12 Science Stream
        262,  # Chemistry - Class 12 Science Stream
        268,  # Accountancy - Class 12 Management
        270,  # Economics - Class 12 Management
        332,  # BCA Core I - Bachelor's BCA
        333,  # BCA Core II - Bachelor's BCA
        278,  # OOP - University Year 1
        279,  # Database Systems - University Year 1
        308,  # Advanced ML - Master's Level
        309,  # Research Methodology - Master's Level
    ]

    # Also pick 2 Class 8 subjects dynamically
    cls8 = Subject.query.filter(Subject.level_of_study.like('%Class 8%')).limit(2).all()
    for s in cls8:
        test_ids.append(s.id)

    # Also pick 2 Class 10 subjects dynamically
    cls10 = Subject.query.filter(Subject.level_of_study.like('%Class 10%')).limit(2).all()
    for s in cls10:
        test_ids.append(s.id)

    for sid in test_ids:
        s = Subject.query.get(sid)
        if not s:
            results.append((sid, '???', '???', '???', 'SKIP (subject not found)'))
            continue
        before = AssessmentQuestion.query.filter_by(subject_id=sid).count()
        if before >= 15:
            results.append((sid, s.name, s.level_of_study, s.program or 'General', 'SKIP (already %d Qs)' % before))
            continue
        count = generate_assessment_questions_for_subject(sid)
        after = AssessmentQuestion.query.filter_by(subject_id=sid).count()
        if count > 0:
            status = 'OK (%d new, total %d)' % (count, after)
        else:
            status = 'FAIL (0 generated, total %d)' % after
        results.append((sid, s.name, s.level_of_study, s.program or 'General', status))
        print('DONE:', s.name, '|', s.level_of_study, '|', status)

print()
print('='*110)
print('FINAL RESULTS TABLE')
print('='*110)
print('%-5s %-35s %-30s %-22s %s' % ('ID', 'Subject', 'Level', 'Program', 'Result'))
print('-'*110)
for sid, name, level, prog, status in results:
    print('%-5s %-35s %-30s %-22s %s' % (sid, str(name)[:33], str(level)[:28], str(prog)[:20], status))
