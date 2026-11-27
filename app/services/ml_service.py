import os
import joblib
from datetime import datetime
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split

MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "models")

def retrain_level_models():
    """
    Retrains level-specific Random Forest models (class8, see, class11, class12, bachelors, masters)
    by combining synthetic baseline datasets with real student logs from the database.
    Overwrites the corresponding .pkl files in the models/ directory.
    """
    from models.train_level_models import LEVELS_CONFIG
    from app.models import SubjectPerformanceHistory, StudentProfile, Prediction

    results = {}
    retrained_at = datetime.utcnow().isoformat()

    for level_slug, cfg in LEVELS_CONFIG.items():
        try:
            # 1. Baseline synthetic dataset
            df_baseline = cfg["generator"](1200)

            # 2. Collect real student logs if available
            real_rows = []
            try:
                profiles = StudentProfile.query.filter(StudentProfile.study_level.ilike(f"%{level_slug}%")).all()
                for prof in profiles:
                    history = SubjectPerformanceHistory.query.filter_by(user_id=prof.user_id).all()
                    for h in history:
                        risk_num = 2 if h.risk_score >= 0.7 else (1 if h.risk_score >= 0.3 else 0)
                        # Build dictionary matching feature names
                        row = {}
                        for feat in cfg["features"]:
                            if hasattr(h, feat):
                                row[feat] = getattr(h, feat)
                            elif feat in ["daily_study_hours", "weekly_study_hours", "study_hours"]:
                                row[feat] = h.actual_hours if h.actual_hours > 0 else h.study_hours
                            elif feat in ["previous_gpa", "current_cgpa", "previous_semester_gpa"]:
                                row[feat] = prof.cumulative_gpa or 3.0
                            elif feat == "attendance":
                                row[feat] = h.attendance
                            else:
                                row[feat] = 75.0  # default fallback
                        row["risk_numeric"] = risk_num
                        real_rows.append(row)
            except Exception as e:
                print(f"[ML Retrain] Note: Could not query real rows for {level_slug}: {e}")

            if real_rows:
                df_real = pd.DataFrame(real_rows)
                df_combined = pd.concat([df_baseline, df_real], ignore_index=True)
            else:
                df_combined = df_baseline

            # 3. Train/Test split & Scaling
            X = df_combined[cfg["features"]]
            y = df_combined["risk_numeric"]

            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)

            # 4. Train RandomForest
            clf = RandomForestClassifier(n_estimators=100, max_depth=12, random_state=42, n_jobs=-1)
            clf.fit(X_train_scaled, y_train)

            test_acc = float(clf.score(X_test_scaled, y_test))

            # 5. Overwrite .pkl files
            rf_path = os.path.join(MODEL_DIR, f"rf_{level_slug}.pkl")
            scaler_path = os.path.join(MODEL_DIR, f"scaler_{level_slug}.pkl")

            joblib.dump(clf, rf_path)
            joblib.dump(scaler, scaler_path)

            results[level_slug] = {
                "status": "success",
                "samples": int(len(df_combined)),
                "test_accuracy": round(test_acc, 4),
                "rf_file": f"rf_{level_slug}.pkl",
                "scaler_file": f"scaler_{level_slug}.pkl"
            }
        except Exception as err:
            results[level_slug] = {
                "status": "error",
                "error": str(err)
            }

    return {
        "status": "completed",
        "retrained_at": retrained_at,
        "models": results
    }
