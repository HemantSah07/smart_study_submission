# seed_all_curriculums.py
import sys
import os
import json
from datetime import datetime

# Insert root path to find app context
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app import create_app, db
from app.models import University, CurriculumProgram, Subject, Chapter, Topic, LearningMaterial, AssessmentQuestion

def seed_data():
    app = create_app()
    with app.app_context():
        print("=== Seeding Real-Life LBEF (APU) Curriculum ===")
        
        # ── 1. Seed Universities ─────────────────────────────────────────────
        unis_to_seed = [
            {"name": "Asia Pacific University (APU)", "abbreviation": "APU", "country": "Malaysia", "sort_order": 20},
            {"name": "Lord Buddha Education Foundation (LBEF)", "abbreviation": "LBEF", "country": "Nepal", "sort_order": 21}
        ]
        
        for u_data in unis_to_seed:
            existing = University.query.filter_by(name=u_data["name"]).first()
            if not existing:
                db.session.add(University(
                    name=u_data["name"],
                    abbreviation=u_data["abbreviation"],
                    country=u_data["country"],
                    is_active=True,
                    sort_order=u_data["sort_order"]
                ))
                print(f"Added University: {u_data['name']}")
        db.session.commit()

        # ── 2. Seed Programs ─────────────────────────────────────────────────
        programs_to_seed = [
            {
                "name": "B.Sc. (Hons) in Information Technology (Core IT)",
                "level_name": "Bachelors",
                "country": "Nepal",
                "has_duration": True,
                "duration_options_json": json.dumps([{"value": "3 Years", "label": "3 Years"}]),
                "sort_order": 30
            },
            {
                "name": "B.Sc. (Hons) in Information Technology (Cloud Engineering)",
                "level_name": "Bachelors",
                "country": "Nepal",
                "has_duration": True,
                "duration_options_json": json.dumps([{"value": "3 Years", "label": "3 Years"}]),
                "sort_order": 31
            },
            {
                "name": "M.Sc. Information Technology Management (M.Sc. ITM)",
                "level_name": "Masters",
                "country": "Nepal",
                "has_duration": True,
                "duration_options_json": json.dumps([{"value": "2 Years", "label": "2 Years"}]),
                "sort_order": 32
            }
        ]
        
        for p_data in programs_to_seed:
            existing = CurriculumProgram.query.filter_by(name=p_data["name"]).first()
            if not existing:
                db.session.add(CurriculumProgram(
                    name=p_data["name"],
                    level_name=p_data["level_name"],
                    country=p_data["country"],
                    has_duration=p_data["has_duration"],
                    duration_options_json=p_data["duration_options_json"],
                    is_active=True,
                    sort_order=p_data["sort_order"]
                ))
                print(f"Added Program: {p_data['name']}")
        db.session.commit()

        # ── 3. Seed Subjects ─────────────────────────────────────────────────
        subjects_data = []

        # Common Level 1 Subjects (Semester 1 & 2)
        l1_common = [
            ("Python Programming", "PYP", 3, "Semester 1"),
            ("Introduction to Databases", "IDB", 3, "Semester 1"),
            ("Introduction to Networking", "INW", 3, "Semester 1"),
            ("System Software and Computing Concepts", "SSCC", 3, "Semester 1"),
            ("Systems Analysis and Design", "SAD", 3, "Semester 1"),
            ("Mathematical Concepts for Computing", "MCF", 3, "Semester 1"),
            ("Digital Thinking and Innovation", "DTI", 3, "Semester 2"),
            ("Integrated Computer Systems", "ICS", 3, "Semester 2"),
            ("Introduction to Security and Forensic Technologies", "ISFT", 3, "Semester 2"),
            ("Fundamentals of Entrepreneurship", "FOE", 3, "Semester 2"),
            ("Fundamentals of Web Design and Development", "FWD", 3, "Semester 2")
        ]

        # BSC IT Core Track Level 2 & 3
        bsc_core = [
            # Semester 3
            ("Object-Oriented Development with Java", "OOD", 4, "Semester 3"),
            ("Mobile and Wireless Technology", "MWT", 3, "Semester 3"),
            ("Concurrent Programming", "CPR", 3, "Semester 3"),
            ("System Development Methods", "SDM", 3, "Semester 3"),
            # Semester 4
            ("Human-Computer Interaction", "HCI", 3, "Semester 4"),
            ("Research Methods for Computing", "RMC", 3, "Semester 4"),
            ("Innovation Process", "INP", 3, "Semester 4"),
            ("Web Applications", "WAP", 3, "Semester 4"),
            # Semester 5
            ("Project Management", "PJM", 3, "Semester 5"),
            ("Advanced Database", "ADB", 3, "Semester 5"),
            ("Cloud Infrastructure and Services", "CIS", 4, "Semester 5"),
            # Semester 6
            ("Information Technology Project", "FYP", 6, "Semester 6"),
            ("Venture Building", "VBL", 3, "Semester 6")
        ]

        # BSC IT Cloud Track Level 2 & 3
        bsc_cloud = [
            # Semester 3
            ("Object-Oriented Development with Java", "OOD", 4, "Semester 3"),
            ("Mobile and Wireless Technology", "MWT", 3, "Semester 3"),
            ("Concurrent Programming", "CPR", 3, "Semester 3"),
            ("Network Security Essentials", "NSE", 3, "Semester 3"),
            # Semester 4
            ("Human-Computer Interaction", "HCI", 3, "Semester 4"),
            ("Research Methods for Computing", "RMC", 3, "Semester 4"),
            ("Innovation Process", "INP", 3, "Semester 4"),
            ("Virtualization & System Administration", "VSA", 3, "Semester 4"),
            # Semester 5
            ("Project Management", "PJM", 3, "Semester 5"),
            ("Advanced Database", "ADB", 3, "Semester 5"),
            ("Cloud Architecture & Design", "CAD", 4, "Semester 5"),
            # Semester 6
            ("Information Technology Project", "FYP", 6, "Semester 6"),
            ("Venture Building", "VBL", 3, "Semester 6"),
            ("Designing & Developing Applications on Cloud", "DDAC", 3, "Semester 6")
        ]

        # MSC ITM Subjects
        msc_itm = [
            ("Managing Software Development Projects", "MSDP", 4, "Core"),
            ("Technology Management", "TMG", 4, "Core"),
            ("Digital Execution", "DEX", 4, "Core"),
            ("Strategic Planning and Systems Development", "SPSD", 4, "Core"),
            ("Business Intelligence Systems", "BIS", 4, "Core"),
            ("Research Methodology in Computing", "RMC", 4, "Core"),
            ("Managing Organisations", "MOG", 4, "Core"),
            ("Dissertation: Project Paper", "PRJ", 12, "Dissertation")
        ]

        # Compile all subject insertions
        # Core IT: Append "-Core" to avoid UNIQUE constraints on code
        for name, code, credits, sem in l1_common + bsc_core:
            subjects_data.append((name, f"{code}-Core", credits, sem, "Bachelors", "B.Sc. (Hons) in Information Technology (Core IT)"))
        # Cloud Engineering: Append "-Cloud"
        for name, code, credits, sem in l1_common + bsc_cloud:
            subjects_data.append((name, f"{code}-Cloud", credits, sem, "Bachelors", "B.Sc. (Hons) in Information Technology (Cloud Engineering)"))
        # MSC ITM: Append "-MSc"
        for name, code, credits, sem in msc_itm:
            subjects_data.append((name, f"{code}-MSc", credits, sem, "Masters", "M.Sc. Information Technology Management (M.Sc. ITM)"))

        subjects_count = 0
        chapters_count = 0
        topics_count = 0
        mcqs_count = 0
        materials_count = 0

        for name, code, credits, sem, level, prog in subjects_data:
            # Check if subject already exists
            subject = Subject.query.filter_by(name=name, code=code, program=prog, level_of_study=level).first()
            if not subject:
                subject = Subject(
                    name=name,
                    code=code,
                    credit_hours=credits,
                    difficulty_level=3,
                    semester_tag=sem,
                    level_of_study=level,
                    program=prog,
                    semester=sem,
                    country="Nepal",
                    curriculum="LBEF (APU)",
                    is_active=True
                )
                db.session.add(subject)
                db.session.flush() # Populate subject.id
                subjects_count += 1
                
                # ── 4. Automatically Create Chapters, Topics & Baseline MCQs ─────────
                chapters = [
                    (1, f"Chapter 1: Fundamentals of {name}"),
                    (2, f"Chapter 2: Advanced Concepts in {name}")
                ]
                
                for ch_num, ch_name in chapters:
                    chapter = Chapter(
                        subject_id=subject.id,
                        name=ch_name,
                        chapter_number=ch_num
                    )
                    db.session.add(chapter)
                    db.session.flush()
                    chapters_count += 1
                    
                    # Create 1 Topic per Chapter
                    topic = Topic(
                        chapter_id=chapter.id,
                        name=f"Introduction to {name}" if ch_num == 1 else f"Advanced {name} Applications",
                        topic_number=1
                    )
                    db.session.add(topic)
                    db.session.flush()
                    topics_count += 1
                    
                    # Create 1 baseline Learning Material
                    intro = f"This module covers the core introductory context and principles of {name}."
                    concepts = f"Understand the fundamental building blocks, workflow, and operations of {name}."
                    material = LearningMaterial(
                        topic_id=topic.id,
                        title=topic.name,
                        learning_objectives=f"Understand fundamentals of {name}",
                        introduction=intro,
                        concepts=concepts,
                        detailed_explanation=f"Detailed academic guidelines for study module {name}.",
                        common_mistakes="Confusing fundamental terminology.",
                        mcqs_json="[]",
                        estimated_reading_time=10,
                        difficulty_level="Medium"
                    )
                    db.session.add(material)
                    materials_count += 1
                    
                    # Create 3 baseline MCQs per Chapter
                    if ch_num == 1:
                        mcqs = [
                            (
                                f"What is the primary goal of studying {name}?",
                                "To understand basic principles and foundations",
                                "To memorize all facts",
                                "To avoid practical applications",
                                "To replace all human efforts",
                                "A",
                                f"Understanding the basic principles is the foundation of {name}."
                            ),
                            (
                                f"Which of the following is a core concept of {name}?",
                                "Random execution",
                                "Structured methodologies and design",
                                "Ignoring errors",
                                "Hardcoding values",
                                "B",
                                f"Structured methodologies are essential in {name}."
                            ),
                            (
                                f"What is a common tool or technique used in {name}?",
                                "Manual guess work",
                                "Standard analysis and analytical modeling",
                                "Ignoring user requirements",
                                "Siloed programming",
                                "B",
                                f"Analytical modeling and analysis are standard techniques used in {name}."
                            )
                        ]
                    else:
                        mcqs = [
                            (
                                f"What does advanced {name} typically involve?",
                                "Scaling, optimization, and system integration",
                                "Writing less documentation",
                                "Slower processing times",
                                "Decreasing reliability",
                                "A",
                                f"Advanced concepts focus on system scaling, performance optimization, and integration."
                            ),
                            (
                                f"How is security and integrity maintained in advanced {name}?",
                                "By ignoring validation checks",
                                "By implementing robust validation, encryption, and access controls",
                                "By exposing sensitive endpoints",
                                "By disabling error logs",
                                "B",
                                f"Access control, validation, and encryption are key to security."
                            ),
                            (
                                f"What is a main challenge when scaling {name} systems?",
                                "Too much documentation",
                                "Concurrency, resource management, and state consistency",
                                "Low memory usage",
                                "Simple code structures",
                                "B",
                                f"Concurrency and resource management are key challenges in distributed/scaled systems."
                            )
                        ]
                        
                    for q_text, oa, ob, oc, od, ans, exp in mcqs:
                        q_record = AssessmentQuestion(
                            subject_id=subject.id,
                            chapter_id=chapter.id,
                            topic_id=topic.id,
                            question_text=q_text,
                            option_a=oa,
                            option_b=ob,
                            option_c=oc,
                            option_d=od,
                            correct_answer=ans,
                            difficulty="Medium",
                            question_type="multiple_choice",
                            explanation=exp,
                            generated_at=datetime.now(),
                            source="seed"
                        )
                        db.session.add(q_record)
                        mcqs_count += 1
                        
        db.session.commit()
        print(f"Seeding completed successfully!")
        print(f"  Added {subjects_count} subjects.")
        print(f"  Added {chapters_count} chapters.")
        print(f"  Added {topics_count} topics.")
        print(f"  Added {materials_count} learning materials.")
        print(f"  Added {mcqs_count} assessment questions.")

if __name__ == "__main__":
    seed_data()
