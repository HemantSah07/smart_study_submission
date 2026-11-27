# app/services/knowledge_graph.py
from app.models import Subject, Chapter, Topic, LearningProgress, QuizScore
from app import db


def build_subject_graph(user_id: int, subject_id: int) -> dict:
    """
    Builds a hierarchical, mastery-aware graph structure (nodes & edges)
    for a given subject, formatted for visualization tools like D3.js or Vis.js.
    """
    subject = Subject.query.get(subject_id)
    if not subject:
        return {"nodes": [], "edges": [], "error": "Subject not found"}

    nodes = []
    edges = []

    # 1. Root Subject Node
    root_node_id = f"subj_{subject.id}"
    nodes.append({
        "id": root_node_id,
        "label": subject.name,
        "type": "subject",
        "code": getattr(subject, 'code', ''),
        "color": "#6366f1", # Indigo accent
        "size": 30
    })

    # Order chapters by chapter_number if available, else id
    try:
        chapters = Chapter.query.filter_by(subject_id=subject.id).order_by(Chapter.chapter_number, Chapter.id).all()
    except Exception:
        chapters = Chapter.query.filter_by(subject_id=subject.id).order_by(Chapter.id).all()

    # Pre-fetch user's topic progress & quiz scores
    user_progress = {
        lp.topic_id: lp.is_completed
        for lp in LearningProgress.query.filter_by(user_id=user_id).all()
    }
    
    # Calculate average quiz score for subject
    subject_quizzes = QuizScore.query.filter_by(user_id=user_id, subject_id=subject.id).all()
    avg_quiz_score = (sum(q.score for q in subject_quizzes if q.score is not None) / len(subject_quizzes)) if subject_quizzes else None

    for ch in chapters:
        ch_node_id = f"ch_{ch.id}"
        ch_num = getattr(ch, 'chapter_number', getattr(ch, 'order_index', 1))
        ch_title = getattr(ch, 'name', getattr(ch, 'title', f"Chapter {ch.id}"))

        # Node color based on average quiz mastery
        ch_color = "#3b82f6" # Default blue
        if avg_quiz_score is not None:
            if avg_quiz_score >= 80:
                ch_color = "#10b981" # Green (High Mastery)
            elif avg_quiz_score >= 60:
                ch_color = "#f59e0b" # Amber (Moderate)
            else:
                ch_color = "#ef4444" # Red (Low Mastery)

        nodes.append({
            "id": ch_node_id,
            "label": f"Ch {ch_num}: {ch_title}",
            "type": "chapter",
            "chapter_id": ch.id,
            "quiz_score": avg_quiz_score,
            "color": ch_color,
            "size": 22
        })

        # Connect Subject -> Chapter
        edges.append({
            "id": f"e_{root_node_id}_{ch_node_id}",
            "source": root_node_id,
            "target": ch_node_id,
            "relationship": "contains"
        })

        # Topics in Chapter
        try:
            topics = Topic.query.filter_by(chapter_id=ch.id).order_by(Topic.topic_number, Topic.id).all()
        except Exception:
            topics = Topic.query.filter_by(chapter_id=ch.id).order_by(Topic.id).all()

        prev_topic_node_id = None

        for top in topics:
            top_node_id = f"top_{top.id}"
            is_completed = user_progress.get(top.id, False)
            top_title = getattr(top, 'name', getattr(top, 'title', f"Topic {top.id}"))

            nodes.append({
                "id": top_node_id,
                "label": top_title,
                "type": "topic",
                "topic_id": top.id,
                "is_completed": is_completed,
                "color": "#10b981" if is_completed else "#94a3b8",
                "size": 15
            })

            # Connect Chapter -> Topic
            edges.append({
                "id": f"e_{ch_node_id}_{top_node_id}",
                "source": ch_node_id,
                "target": top_node_id,
                "relationship": "contains"
            })

            # Sequential prerequisite edge between adjacent topics
            if prev_topic_node_id:
                edges.append({
                    "id": f"e_prereq_{prev_topic_node_id}_{top_node_id}",
                    "source": prev_topic_node_id,
                    "target": top_node_id,
                    "relationship": "prerequisite",
                    "style": "dashed"
                })

            prev_topic_node_id = top_node_id

    return {
        "status": "success",
        "subject_id": subject.id,
        "subject_name": subject.name,
        "summary": {
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "chapters_count": len(chapters)
        },
        "nodes": nodes,
        "edges": edges
    }
