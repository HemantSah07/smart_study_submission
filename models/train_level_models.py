import os
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split

MODEL_DIR = os.path.dirname(os.path.abspath(__file__))

LEVELS_CONFIG = {
    "class8": {
        "features": [
            "attendance_pct", "homework_completion_pct", "classwork_completion_pct",
            "daily_study_hours", "weekly_study_hours", "first_terminal_marks",
            "second_terminal_marks", "third_terminal_marks", "final_examination_marks",
            "participation", "discipline", "extra_tuition", "sleep_hours"
        ],
        "generator": lambda size: generate_class8_data(size)
    },
    "see": {
        "features": [
            "attendance", "internal_assessment", "unit_test_marks",
            "pre_see_marks", "mock_exam_marks", "practical_marks",
            "daily_study_hours", "homework", "previous_gpa"
        ],
        "generator": lambda size: generate_see_data(size)
    },
    "class11": {
        "features": [
            "attendance", "assignments", "first_terminal",
            "mid_term", "practical_marks", "study_hours",
            "previous_gpa", "coaching", "homework"
        ],
        "generator": lambda size: generate_class11_data(size)
    },
    "class12": {
        "features": [
            "attendance", "assignments", "pre_board",
            "board_preparation", "practical_marks", "study_hours",
            "previous_gpa", "homework"
        ],
        "generator": lambda size: generate_class12_data(size)
    },
    "bachelors": {
        "features": [
            "attendance", "assignment_scores", "internal_assessment",
            "quiz_scores", "lab_marks", "presentation_marks",
            "project_marks", "mid_term", "final_exam",
            "previous_semester_gpa", "current_cgpa", "backlogs",
            "credits_completed", "daily_study_hours", "weekly_study_hours"
        ],
        "generator": lambda size: generate_bachelors_data(size)
    },
    "masters": {
        "features": [
            "attendance", "research_proposal", "seminar_performance",
            "assignments", "presentations", "literature_review",
            "lab_work", "dissertation_progress", "supervisor_feedback",
            "research_hours", "publications", "conference_participation",
            "previous_gpa", "current_cgpa"
        ],
        "generator": lambda size: generate_masters_data(size)
    }
}

# Generators implementing custom feature dependencies
def generate_class8_data(size):
    np.random.seed(42)
    att = np.random.uniform(60, 100, size)
    hw = np.random.uniform(50, 100, size)
    cw = np.random.uniform(50, 100, size)
    daily = np.random.uniform(0.5, 6, size)
    weekly = daily * 7 + np.random.uniform(-2, 2, size)
    t1 = np.random.uniform(35, 100, size)
    t2 = t1 + np.random.uniform(-10, 15, size)
    t3 = t2 + np.random.uniform(-10, 15, size)
    final = (t1 + t2 + t3) / 3 + np.random.uniform(-5, 10, size)
    
    # Clip marks
    t2 = np.clip(t2, 0, 100)
    t3 = np.clip(t3, 0, 100)
    final = np.clip(final, 0, 100)
    
    part = np.random.uniform(1, 5, size)
    disc = np.random.uniform(1, 5, size)
    tuition = np.random.randint(0, 2, size) # 0 = no, 1 = yes
    sleep = np.random.uniform(5, 9, size)

    # Compute risk score
    # Higher score = poor behavior
    score = (
        (100 - att) * 0.2 +
        (100 - final) * 0.35 +
        (100 - hw) * 0.15 +
        (6 - daily) * 10 * 0.15 +
        (5 - disc) * 5 * 0.15
    )
    
    risk = np.where(score > 25, 2, np.where(score > 12, 1, 0)) # 2=high, 1=medium, 0=low
    
    df = pd.DataFrame({
        "attendance_pct": att, "homework_completion_pct": hw, "classwork_completion_pct": cw,
        "daily_study_hours": daily, "weekly_study_hours": weekly, "first_terminal_marks": t1,
        "second_terminal_marks": t2, "third_terminal_marks": t3, "final_examination_marks": final,
        "participation": part, "discipline": disc, "extra_tuition": tuition, "sleep_hours": sleep,
        "risk_numeric": risk
    })
    return df

def generate_see_data(size):
    np.random.seed(43)
    att = np.random.uniform(60, 100, size)
    internal = np.random.uniform(50, 100, size)
    unit = np.random.uniform(40, 100, size)
    pre_see = unit * 0.9 + np.random.uniform(-10, 15, size)
    pre_see = np.clip(pre_see, 0, 100)
    mock = pre_see + np.random.uniform(-5, 10, size)
    mock = np.clip(mock, 0, 100)
    prac = np.random.uniform(15, 25, size) # Practical out of 25 usually
    daily = np.random.uniform(1, 8, size)
    hw = np.random.uniform(50, 100, size)
    prev_gpa = np.random.uniform(1.6, 4.0, size)

    score = (
        (100 - att) * 0.15 +
        (100 - pre_see) * 0.4 +
        (100 - internal) * 0.15 +
        (8 - daily) * 6 * 0.15 +
        (4.0 - prev_gpa) * 12.5 * 0.15
    )
    risk = np.where(score > 24, 2, np.where(score > 11, 1, 0))

    return pd.DataFrame({
        "attendance": att, "internal_assessment": internal, "unit_test_marks": unit,
        "pre_see_marks": pre_see, "mock_exam_marks": mock, "practical_marks": prac,
        "daily_study_hours": daily, "homework": hw, "previous_gpa": prev_gpa,
        "risk_numeric": risk
    })

def generate_class11_data(size):
    np.random.seed(44)
    att = np.random.uniform(60, 100, size)
    assign = np.random.uniform(50, 100, size)
    t1 = np.random.uniform(35, 100, size)
    mid = t1 + np.random.uniform(-10, 15, size)
    mid = np.clip(mid, 0, 100)
    prac = np.random.uniform(15, 25, size)
    study = np.random.uniform(10, 45, size) # weekly hours
    prev_gpa = np.random.uniform(1.6, 4.0, size)
    coaching = np.random.randint(0, 2, size)
    hw = np.random.uniform(50, 100, size)

    score = (
        (100 - att) * 0.15 +
        (100 - mid) * 0.4 +
        (100 - assign) * 0.15 +
        (45 - study) * 0.3 * 0.15 +
        (4.0 - prev_gpa) * 12.5 * 0.15
    )
    risk = np.where(score > 25, 2, np.where(score > 12, 1, 0))

    return pd.DataFrame({
        "attendance": att, "assignments": assign, "first_terminal": t1,
        "mid_term": mid, "practical_marks": prac, "study_hours": study,
        "previous_gpa": prev_gpa, "coaching": coaching, "homework": hw,
        "risk_numeric": risk
    })

def generate_class12_data(size):
    np.random.seed(45)
    att = np.random.uniform(60, 100, size)
    assign = np.random.uniform(50, 100, size)
    pre_board = np.random.uniform(35, 100, size)
    board_prep = pre_board + np.random.uniform(-5, 15, size)
    board_prep = np.clip(board_prep, 0, 100)
    prac = np.random.uniform(15, 25, size)
    study = np.random.uniform(10, 50, size)
    prev_gpa = np.random.uniform(1.6, 4.0, size)
    hw = np.random.uniform(50, 100, size)

    score = (
        (100 - att) * 0.15 +
        (100 - board_prep) * 0.4 +
        (100 - assign) * 0.15 +
        (50 - study) * 0.3 * 0.15 +
        (4.0 - prev_gpa) * 12.5 * 0.15
    )
    risk = np.where(score > 25, 2, np.where(score > 12, 1, 0))

    return pd.DataFrame({
        "attendance": att, "assignments": assign, "pre_board": pre_board,
        "board_preparation": board_prep, "practical_marks": prac, "study_hours": study,
        "previous_gpa": prev_gpa, "homework": hw,
        "risk_numeric": risk
    })

def generate_bachelors_data(size):
    np.random.seed(46)
    att = np.random.uniform(60, 100, size)
    assign = np.random.uniform(50, 100, size)
    internal = np.random.uniform(50, 100, size)
    quiz = np.random.uniform(40, 100, size)
    lab = np.random.uniform(60, 100, size)
    pres = np.random.uniform(60, 100, size)
    proj = np.random.uniform(60, 100, size)
    mid = np.random.uniform(40, 100, size)
    final = mid * 0.95 + np.random.uniform(-10, 15, size)
    final = np.clip(final, 0, 100)
    prev_gpa = np.random.uniform(2.0, 4.0, size)
    current_cgpa = prev_gpa * 0.98 + np.random.uniform(-0.3, 0.3, size)
    current_cgpa = np.clip(current_cgpa, 0.0, 4.0)
    backlogs = np.random.choice([0, 1, 2, 3], size, p=[0.7, 0.18, 0.08, 0.04])
    credits = np.random.uniform(12, 21, size)
    daily = np.random.uniform(1, 8, size)
    weekly = daily * 7 + np.random.uniform(-2, 2, size)

    score = (
        (100 - att) * 0.1 +
        (100 - final) * 0.3 +
        (100 - assign) * 0.1 +
        (4.0 - current_cgpa) * 12.5 * 0.2 +
        backlogs * 10 * 0.2 +
        (8 - daily) * 6 * 0.1
    )
    risk = np.where(score > 23, 2, np.where(score > 11, 1, 0))

    return pd.DataFrame({
        "attendance": att, "assignment_scores": assign, "internal_assessment": internal,
        "quiz_scores": quiz, "lab_marks": lab, "presentation_marks": pres,
        "project_marks": proj, "mid_term": mid, "final_exam": final,
        "previous_semester_gpa": prev_gpa, "current_cgpa": current_cgpa, "backlogs": backlogs,
        "credits_completed": credits, "daily_study_hours": daily, "weekly_study_hours": weekly,
        "risk_numeric": risk
    })

def generate_masters_data(size):
    np.random.seed(47)
    att = np.random.uniform(60, 100, size)
    proposal = np.random.uniform(60, 100, size)
    seminar = np.random.uniform(60, 100, size)
    assign = np.random.uniform(60, 100, size)
    pres = np.random.uniform(60, 100, size)
    lit = np.random.uniform(60, 100, size)
    lab = np.random.uniform(60, 100, size)
    diss = np.random.uniform(50, 100, size)
    superv = np.random.uniform(1, 5, size) # supervisor rating 1-5
    hours = np.random.uniform(5, 30, size) # weekly research hours
    pubs = np.random.randint(0, 3, size)
    conf = np.random.randint(0, 3, size)
    prev_gpa = np.random.uniform(2.5, 4.0, size)
    current_cgpa = prev_gpa * 0.98 + np.random.uniform(-0.2, 0.2, size)
    current_cgpa = np.clip(current_cgpa, 0.0, 4.0)

    score = (
        (100 - att) * 0.1 +
        (100 - diss) * 0.25 +
        (100 - assign) * 0.1 +
        (4.0 - current_cgpa) * 12.5 * 0.25 +
        (5 - superv) * 10 * 0.15 +
        (30 - hours) * 0.3 * 0.15
    )
    risk = np.where(score > 23, 2, np.where(score > 11, 1, 0))

    return pd.DataFrame({
        "attendance": att, "research_proposal": proposal, "seminar_performance": seminar,
        "assignments": assign, "presentations": pres, "literature_review": lit,
        "lab_work": lab, "dissertation_progress": diss, "supervisor_feedback": superv,
        "research_hours": hours, "publications": pubs, "conference_participation": conf,
        "previous_gpa": prev_gpa, "current_cgpa": current_cgpa,
        "risk_numeric": risk
    })

def train_all():
    print("Training Level-Specific Random Forest Predictors...")
    for level_slug, cfg in LEVELS_CONFIG.items():
        print(f"\nTraining model for study level: {level_slug.upper()}")
        
        # Generate data
        df = cfg["generator"](1200)
        
        # Split features & labels
        X = df[cfg["features"]]
        y = df["risk_numeric"]
        
        # Train / Test split
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        # Fit scaler
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
        
        # Train classifier
        clf = RandomForestClassifier(n_estimators=100, max_depth=12, random_state=42, n_jobs=-1)
        clf.fit(X_train_scaled, y_train)
        
        # Check accuracy
        train_acc = clf.score(X_train_scaled, y_train)
        test_acc = clf.score(X_test_scaled, y_test)
        print(f"  Training Accuracy: {train_acc:.4f}")
        print(f"  Testing Accuracy:  {test_acc:.4f}")
        
        # Save models
        joblib.dump(clf, os.path.join(MODEL_DIR, f"rf_{level_slug}.pkl"))
        joblib.dump(scaler, os.path.join(MODEL_DIR, f"scaler_{level_slug}.pkl"))
        print(f"  Saved rf_{level_slug}.pkl and scaler_{level_slug}.pkl successfully.")

if __name__ == "__main__":
    train_all()
