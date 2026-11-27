# Intelligent Curriculum-Grounded Study Planner Generator
import json
import random

DAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']

# High-yield study strategies mapped by cognitive discipline
SUBJECT_DOMAIN_PATTERNS = {
    ("network", "networking", "cisco", "protocol"): {
        "domain": "Networking & Systems",
        "sample_topics": [
            "Network Topologies & OSI/TCP-IP Models",
            "Subnetting, CIDR & IP Addressing Schemes",
            "Routing Protocols (OSPF, BGP, RIP)",
            "Switching, VLANs & Trunking (802.1Q)",
            "Network Security, Firewalls & ACLs",
            "Automation with Python & Ansible"
        ],
        "tips": [
            "Draw packet flow diagrams and trace header encapsulations step-by-step.",
            "Practice 5 subnetting math calculations without a calculator to build speed.",
            "Configure virtual topologies in Packet Tracer/GNS3 and inspect route tables.",
            "Write down firewall ACL rule hierarchies and analyze traffic drop edge-cases."
        ]
    },
    ("database", "dbms", "sql", "data"): {
        "domain": "Databases & Data Systems",
        "sample_topics": [
            "Relational Modeling & Normalization (1NF to BCNF)",
            "SQL Query Optimization & Execution Plans",
            "Indexing Structures (B-Trees, Hash Indexes)",
            "Transaction Management & ACID Guarantees",
            "Concurrency Control & Two-Phase Locking",
            "NoSQL Data Stores & Distributed Architecture"
        ],
        "tips": [
            "Write out complex JOIN and GROUP BY queries by hand before executing.",
            "Analyze query EXPLAIN plans to identify full-table scans and missing indexes.",
            "Normalize an unnormalized schema down to 3NF/BCNF step-by-step on paper.",
            "Simulate concurrent transactions on paper to spot dirty reads and deadlocks."
        ]
    },
    ("software", "se", "engineering", "agile"): {
        "domain": "Software Engineering",
        "sample_topics": [
            "Software Architecture & Design Patterns (SOLID)",
            "Requirement Engineering & Agile Methodologies",
            "CI/CD Pipelines, Testing & Quality Assurance",
            "REST API Design & Microservices Architecture",
            "System Decomposition & UML Sequence Diagrams"
        ],
        "tips": [
            "Implement a Gang of Four design pattern (Factory/Observer/Singleton) from scratch.",
            "Draw a complete UML sequence diagram for an end-to-end user checkout flow.",
            "Review test coverage strategies: unit tests vs integration vs end-to-end.",
            "Create user stories with strict acceptance criteria and edge cases."
        ]
    },
    ("algorithm", "data structure", "dsa", "programming", "python", "java", "c++"): {
        "domain": "Algorithms & Programming",
        "sample_topics": [
            "Time & Space Complexity Analysis (Big-O)",
            "Arrays, Linked Lists, Stacks & Queues",
            "Tree Traversal (Binary Search Trees, AVL)",
            "Graph Algorithms (BFS, DFS, Dijkstra)",
            "Dynamic Programming & Memoization",
            "Sorting & Searching Algorithms"
        ],
        "tips": [
            "Trace Big-O complexity line-by-line for both time and auxiliary space.",
            "Implement search/sort algorithms from pseudocode without referencing documentation.",
            "Solve 2 LeetCode-style problems under a strict 20-minute timer.",
            "Dry-run tree traversals (In-order, Pre-order, Post-order) on a whiteboard."
        ]
    },
    ("math", "calculus", "algebra", "discrete", "statistics"): {
        "domain": "Mathematics & Statistics",
        "sample_topics": [
            "Differential & Integral Calculus",
            "Linear Algebra & Matrix Transformations",
            "Discrete Structures & Logic Proofs",
            "Probability Distributions & Hypothesis Testing",
            "Graph Theory & Combinatorics"
        ],
        "tips": [
            "Derive core theorems from first principles rather than memorizing formulas.",
            "Solve 10 mixed numerical problems without looking at answer keys.",
            "Identify pattern types in calculus substitution and integration by parts.",
            "Create a single-page formula memory cheat-sheet and recall it from memory."
        ]
    },
    ("operating", "os", "linux", "unix"): {
        "domain": "Operating Systems & Low Level",
        "sample_topics": [
            "Process Scheduling & Thread Management",
            "Memory Management, Virtual Memory & Paging",
            "Deadlock Prevention & Banker's Algorithm",
            "File System Implementation & Inodes",
            "Inter-Process Communication & Semaphores"
        ],
        "tips": [
            "Draw process state transition diagrams and trace page replacement algorithms (LRU, FIFO).",
            "Trace semaphores and mutex locks with producer-consumer pseudocode.",
            "Calculate virtual-to-physical address translation offsets manually."
        ]
    },
    ("english", "communication", "writing"): {
        "domain": "Languages & Communication",
        "sample_topics": [
            "Grammar Mechanics & Sentence Structuring",
            "Technical Report Writing & Documentation",
            "Critical Reading Comprehension & Analysis",
            "Vocabulary Enhancement & Academic Phrasing"
        ],
        "tips": [
            "Read one academic journal excerpt and write a concise 3-sentence executive summary.",
            "Analyze and rewrite passive voice paragraphs into punchy, clear active voice.",
            "Practice structuring thesis statements with opposing argument rebuttals."
        ]
    }
}


def _infer_subject_domain(subject_name):
    """Matches subject name against known domain patterns for intelligent recommendations."""
    sub_lower = subject_name.lower()
    for keywords, data in SUBJECT_DOMAIN_PATTERNS.items():
        if any(k in sub_lower for k in keywords):
            return data
    return None


def generate_study_planner(
    prediction_result,
    subjects,
    marks,
    study_hours_per_day,
    session_length=60,
    strategy='Weakest subjects first',
    revision_day='Saturday',
    free_slots_json=None,
    weak_topics=None,
    subject_chapters=None,
    peak_focus_time='Morning',
    preferred_language='English'
):
    """
    Generates a personalized, curriculum-grounded, cognitive-science-driven weekly study plan.

    Features:
    - Grounded in student's actual weak topics from assessments.
    - Topic and chapter level targets instead of generic subject repetitions.
    - Spaced repetition review blocks (Ebbinghaus forgetting curve).
    - Dynamic Pomodoro breakdown (focus time + recovery intervals).
    - Energy-curve alignment with student's Peak Focus Time.
    """
    weak_topics = weak_topics or []
    subject_chapters = subject_chapters or {}

    # Map weak topics by subject
    weak_topics_by_sub = {}
    for wt in weak_topics:
        if isinstance(wt, dict):
            sname = wt.get("subject_name", "")
            tname = wt.get("name") or wt.get("topic_name", "")
            cname = wt.get("chapter_name", "")
            if sname:
                weak_topics_by_sub.setdefault(sname.lower(), []).append({
                    "topic": tname,
                    "chapter": cname
                })

    # Step 1: Score & weight each subject
    subject_priorities = []
    for subject, mark in zip(subjects, marks):
        s_lower = subject.lower()
        has_diagnostic_weakness = bool(weak_topics_by_sub.get(s_lower))

        if mark < 40:
            priority = "Critical"
            base_weight = 3.5 if strategy == "Weakest subjects first" else 2.0
        elif mark < 60:
            priority = "Weak"
            base_weight = 2.5 if strategy == "Weakest subjects first" else 1.7
        elif mark < 75:
            priority = "Average"
            base_weight = 1.6 if strategy == "Weakest subjects first" else 1.4
        else:
            priority = "Strong"
            base_weight = 1.0

        # Boost weight if diagnostic tests revealed specific failed concepts
        if has_diagnostic_weakness:
            base_weight += 0.6

        # Fetch domain knowledge
        domain_info = _infer_subject_domain(subject)
        weak_list = weak_topics_by_sub.get(s_lower, [])

        # Curate focal topics for this subject
        focal_topics = []
        if weak_list:
            focal_topics = [f"{w['chapter']} - {w['topic']}" if w['chapter'] else w['topic'] for w in weak_list]
        elif subject in subject_chapters and subject_chapters[subject]:
            # Use real curriculum chapters
            ch_data = subject_chapters[subject]
            for ch in ch_data:
                if isinstance(ch, dict):
                    focal_topics.append(ch.get("title") or ch.get("name", ""))
                elif isinstance(ch, str):
                    focal_topics.append(ch)
        elif domain_info:
            focal_topics = list(domain_info["sample_topics"])

        if not focal_topics:
            focal_topics = [
                f"{subject}: Fundamental Core Concepts",
                f"{subject}: Advanced Problem Solving",
                f"{subject}: Past Exam Analysis & Active Recall",
                f"{subject}: Comprehensive Synthesis & Review"
            ]

        # Get customized tip
        focus_tip = ""
        if weak_list:
            focus_tip = f"Target diagnostic weak area: {weak_list[0]['topic']} using active recall & flashcards."
        elif domain_info and domain_info["tips"]:
            focus_tip = domain_info["tips"][0]
        else:
            focus_tip = f"Reinforce core principles and solve practice problems for {subject}."

        subject_priorities.append({
            "subject": subject,
            "mark": mark,
            "priority": priority,
            "weight": base_weight,
            "focal_topics": focal_topics,
            "focus_tip": focus_tip,
            "has_weak_topics": has_diagnostic_weakness,
            "weak_topic_count": len(weak_list)
        })

    # Sort: highest weight first
    subject_priorities.sort(key=lambda x: x["weight"], reverse=True)

    # Step 2: Adjust study hours based on ML prediction result
    if prediction_result == "Fail":
        boost_factor = 1.35
    elif prediction_result == "At Risk":
        boost_factor = 1.2
    else:
        boost_factor = 1.0

    adjusted_hours = min(max(study_hours_per_day * boost_factor, 1.5), 10.0)

    # Step 3: Parse free slots
    free_slots = {}
    if free_slots_json:
        try:
            free_slots = json.loads(free_slots_json)
        except Exception:
            pass

    day_free_hours = {day: [] for day in DAYS}
    for key, status in free_slots.items():
        if status == "free" and "-" in key:
            parts = key.split("-")
            day = parts[0]
            try:
                hour = int(parts[1])
                if day in day_free_hours:
                    day_free_hours[day].append(hour)
            except ValueError:
                pass

    for day in DAYS:
        day_free_hours[day].sort()

    # Fallback to smart daytime slots if user hasn't configured grid
    has_any_slots = any(len(h) > 0 for h in day_free_hours.values())
    if not has_any_slots:
        # Generate smart slots aligned with peak focus time
        if peak_focus_time.lower() == "morning":
            default_hours = [7, 8, 9, 10, 15, 16]
        elif peak_focus_time.lower() == "evening":
            default_hours = [17, 18, 19, 20, 21, 22]
        elif peak_focus_time.lower() == "night":
            default_hours = [20, 21, 22, 23, 0]
        else:  # Afternoon
            default_hours = [13, 14, 15, 16, 17, 18]

        # Calculate number of hours needed daily
        daily_count = max(2, min(int(round(adjusted_hours)), len(default_hours)))
        for day in DAYS:
            day_free_hours[day] = default_hours[:daily_count]

    # Step 4: Convert session length and compute Pomodoro parameters
    session_hr = round(session_length / 60.0, 1)
    if session_length <= 30:
        pomodoro = {"study": 25, "break": 5, "label": "25m Study · 5m Break"}
    elif session_length <= 45:
        pomodoro = {"study": 35, "break": 10, "label": "35m Deep Focus · 10m Break"}
    elif session_length <= 60:
        pomodoro = {"study": 50, "break": 10, "label": "50m Deep Focus · 10m Refresh"}
    elif session_length <= 90:
        pomodoro = {"study": 40, "break": 10, "cycles": 2, "label": "2x (40m Focus + 5m Micro-break)"}
    else:  # 120m
        pomodoro = {"study": 50, "break": 10, "cycles": 2, "label": "2x (50m Focus + 10m Rest)"}

    # Step 5: Distribute sessions across days with curriculum topics & spaced repetition
    total_weight = sum(s["weight"] for s in subject_priorities) if subject_priorities else 1.0
    schedule = {day: [] for day in DAYS}

    rev_day_str = revision_day.strip().capitalize()
    if rev_day_str not in DAYS:
        rev_day_str = 'Saturday'

    # Track topics studied on previous days to trigger Spaced Repetition Checkpoints
    recent_studied_topics = []
    subject_topic_counters = {sp["subject"]: 0 for sp in subject_priorities}

    for day_idx, day in enumerate(DAYS):
        hours_list = day_free_hours[day]
        if not hours_list:
            continue

        if day == rev_day_str:
            # Revision & Mock Assessment Day
            weak_subjects = [s for s in subject_priorities if s["priority"] in ["Critical", "Weak"]]
            if not weak_subjects:
                weak_subjects = subject_priorities[:2]

            for idx, hour in enumerate(hours_list):
                start_t = f"{hour:02d}:00"
                end_t = f"{(hour+1)%24:02d}:00"

                if idx == 0 and weak_subjects:
                    s_target = weak_subjects[0]
                    schedule[day].append({
                        "subject": s_target["subject"],
                        "hours": session_hr,
                        "start_time": start_t,
                        "end_time": end_t,
                        "priority": "Revision",
                        "session_type": "Diagnostic Weakness Drill",
                        "target_topic": s_target["focal_topics"][0] if s_target["focal_topics"] else "Weak Concepts Review",
                        "focus_tip": "Redo mistakes from previous quizzes and practice active recall.",
                        "pomodoro": pomodoro,
                        "badge_class": "bg-danger"
                    })
                elif idx == 1 and len(weak_subjects) > 1:
                    s_target = weak_subjects[1]
                    schedule[day].append({
                        "subject": s_target["subject"],
                        "hours": session_hr,
                        "start_time": start_t,
                        "end_time": end_t,
                        "priority": "Revision",
                        "session_type": "Spaced Active Recall",
                        "target_topic": s_target["focal_topics"][-1] if s_target["focal_topics"] else "Formula & Definition Drill",
                        "focus_tip": "Test yourself using flashcards without checking notes first.",
                        "pomodoro": pomodoro,
                        "badge_class": "bg-warning text-dark"
                    })
                else:
                    schedule[day].append({
                        "subject": "Full Diagnostic Mock Test",
                        "hours": session_hr,
                        "start_time": start_t,
                        "end_time": end_t,
                        "priority": "Test",
                        "session_type": "Exam Simulation",
                        "target_topic": "Timed Self-Assessment Across All Active Modules",
                        "focus_tip": "Simulate strict exam conditions: no distractions, timed answers.",
                        "pomodoro": pomodoro,
                        "badge_class": "bg-purple text-white"
                    })
        else:
            # Regular study day: distribute weighted subjects with interleaving & topics
            num_slots = len(hours_list)

            # Build balanced subject sequence for today
            day_subjects = []
            for sp in subject_priorities:
                count = max(1, int(round((sp["weight"] / total_weight) * num_slots)))
                day_subjects.extend([sp] * count)

            # Pad or trim to match slots
            while len(day_subjects) < num_slots:
                day_subjects.extend(subject_priorities)
            day_subjects = day_subjects[:num_slots]

            # Interleave to avoid same subject twice back-to-back if possible
            if len(day_subjects) > 2 and len(subject_priorities) > 1:
                interleaved = []
                for i in range(len(day_subjects)):
                    # Rotate selection to vary subjects
                    idx = (i * 2) % len(day_subjects)
                    interleaved.append(day_subjects[idx])
                day_subjects = interleaved

            for slot_idx, (hour, sp) in enumerate(zip(hours_list, day_subjects)):
                start_t = f"{hour:02d}:00"
                end_t = f"{(hour+1)%24:02d}:00"
                s_name = sp["subject"]

                # Rotate through actual focal topics
                t_list = sp["focal_topics"]
                t_idx = subject_topic_counters[s_name] % len(t_list)
                current_topic = t_list[t_idx]
                subject_topic_counters[s_name] += 1

                # Check if this should be a Spaced Repetition Checkpoint (e.g., slot 0 on Wed or Fri)
                is_spaced_review = (day_idx in (3, 5)) and slot_idx == 0 and len(recent_studied_topics) > 1

                if is_spaced_review:
                    review_item = recent_studied_topics[0]
                    session_type = "Spaced Repetition Checkpoint"
                    target_topic = f"Review: {review_item['topic']}"
                    badge_class = "bg-info text-dark"
                    custom_tip = f"Active recall checkpoint for {review_item['subject']}. Test key formulas & concepts."
                elif sp["priority"] == "Critical":
                    session_type = "High-Yield Mastery Drill"
                    target_topic = current_topic
                    badge_class = "bg-danger"
                    custom_tip = sp["focus_tip"]
                elif sp["priority"] == "Weak":
                    session_type = "Concept Deep-Dive & Exercises"
                    target_topic = current_topic
                    badge_class = "bg-warning text-dark"
                    custom_tip = sp["focus_tip"]
                else:
                    session_type = "Core Concept Mastery & Practice"
                    target_topic = current_topic
                    badge_class = "bg-primary"
                    domain_info = _infer_subject_domain(s_name)
                    if domain_info and domain_info["tips"]:
                        custom_tip = domain_info["tips"][(slot_idx + day_idx) % len(domain_info["tips"])]
                    else:
                        custom_tip = f"Review key sections of {current_topic} and attempt practice problems."

                schedule[day].append({
                    "subject": s_name,
                    "hours": session_hr,
                    "start_time": start_t,
                    "end_time": end_t,
                    "priority": sp["priority"],
                    "session_type": session_type,
                    "target_topic": target_topic,
                    "focus_tip": custom_tip,
                    "pomodoro": pomodoro,
                    "badge_class": badge_class
                })

                recent_studied_topics.append({"subject": s_name, "topic": current_topic})
                if len(recent_studied_topics) > 6:
                    recent_studied_topics.pop(0)

    # Calculate total weekly hours
    total_planned_sessions = sum(len(slots) for slots in schedule.values())
    total_planned_hours = round(total_planned_sessions * session_hr, 1)

    return {
        "schedule": schedule,
        "subject_priorities": subject_priorities,
        "recommended_daily_hours": round(adjusted_hours, 1),
        "total_planned_hours": total_planned_hours,
        "total_planned_sessions": total_planned_sessions,
        "prediction_result": prediction_result,
        "planner_message": get_planner_message(prediction_result),
        "strategy": strategy,
        "revision_day": revision_day,
        "peak_focus_time": peak_focus_time,
        "pomodoro": pomodoro
    }


def get_planner_message(prediction_result):
    messages = {
        "Pass": "Outstanding trajectory. This adaptive plan optimizes concept retention and high-yield mastery.",
        "At Risk": "Focused intervention required. Follow the spaced repetition blocks strictly to reverse risk indicators.",
        "Fail": "Urgent academic focus needed. Prioritize the designated diagnostic weakness sessions and consult your instructors."
    }
    return messages.get(prediction_result, "Follow this planner to achieve maximum academic performance.")
