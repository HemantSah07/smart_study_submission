import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split, RandomizedSearchCV
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
import joblib
import os
import time

# ── Feature columns (7-feature expanded set) ─────────────────────────────────
FEATURE_COLS = [
    'previous_grade',           # 0-100 recent grade / exam score
    'attendance',               # 0-100 attendance percentage
    'difficulty',               # 1-5 subject difficulty rating
    'study_hours',              # weekly study hours
    'days_until_exam',          # days remaining to next exam (0-90)
    'days_since_last_studied',  # days since any study session (0-60)
    'completion_rate',          # prior-week plan completion ratio (0.0-1.0)
]

def generate_training_data(num_samples=15000):
    """Generate synthetic 7-feature training data for three risk archetypes."""
    np.random.seed(42)

    def archetype(n, grade_mu, att_mu, study_mu, exam_days_mu, last_mu, cr_mu, risk_val):
        grade    = np.clip(np.random.normal(grade_mu, 12, n), 0, 100)
        att      = np.clip(np.random.normal(att_mu, 10, n), 0, 100)
        diff     = np.clip(np.random.uniform(1, 5, n), 1, 5)
        study    = np.clip(np.random.normal(study_mu, 5, n), 0, 60)
        exam_d   = np.clip(np.random.normal(exam_days_mu, 15, n), 0, 90).astype(int)
        last_d   = np.clip(np.random.normal(last_mu, 10, n), 0, 60).astype(int)
        cr       = np.clip(np.random.normal(cr_mu, 0.15, n), 0.0, 1.0)
        return pd.DataFrame({
            'previous_grade':           grade,
            'attendance':               att,
            'difficulty':               diff,
            'study_hours':              study,
            'days_until_exam':          exam_d,
            'days_since_last_studied':  last_d,
            'completion_rate':          cr,
            'risk_numeric':             np.full(n, risk_val),
        })

    n_low  = int(num_samples * 0.35)  # Low risk  -> 0
    n_med  = int(num_samples * 0.45)  # Medium    -> 1
    n_high = num_samples - n_low - n_med  # High      -> 2

    low_df  = archetype(n_low,  grade_mu=85, att_mu=92, study_mu=22, exam_days_mu=60, last_mu=2,  cr_mu=0.90, risk_val=0)
    med_df  = archetype(n_med,  grade_mu=68, att_mu=75, study_mu=12, exam_days_mu=30, last_mu=10, cr_mu=0.68, risk_val=1)
    high_df = archetype(n_high, grade_mu=45, att_mu=52, study_mu=5,  exam_days_mu=10, last_mu=25, cr_mu=0.38, risk_val=2)

    df = pd.concat([low_df, med_df, high_df]).sample(frac=1, random_state=42).reset_index(drop=True)
    return df


def train_and_save_models():
    print("Generating 7-feature synthetic training data...")
    model_dir = os.path.dirname(os.path.abspath(__file__))
    df = generate_training_data(15000)

    # Persist generated CSV for reference
    csv_path = os.path.join(model_dir, 'ML_training_dataset.csv')
    df.to_csv(csv_path, index=False)
    print(f"  Dataset saved: {csv_path}  ({len(df)} rows)")

    X = df[FEATURE_COLS]
    y = df['risk_numeric']

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    print("Scaling features...")
    scaler = StandardScaler()
    X_train_sc = scaler.fit_transform(X_train)
    X_test_sc  = scaler.transform(X_test)

    print("Training Random Forest with RandomizedSearchCV...")
    param_grid = {
        'n_estimators':     [100, 200, 300],
        'max_depth':        [10, 20, None],
        'min_samples_split':[2, 5, 10],
        'min_samples_leaf': [1, 2, 4],
    }
    rf_search = RandomizedSearchCV(
        RandomForestClassifier(random_state=42),
        param_grid, n_iter=10, cv=5, random_state=42, n_jobs=-1, verbose=1
    )
    rf_search.fit(X_train_sc, y_train)
    best_rf = rf_search.best_estimator_
    print(f"  Best params: {rf_search.best_params_}")

    preds = best_rf.predict(X_test_sc)
    acc   = accuracy_score(y_test, preds)
    print(f"\n{'='*40}")
    print(f"RANDOM FOREST EVALUATION")
    print(f"{'='*40}")
    print(f"Accuracy: {acc:.4f}")
    print("\nClassification Report:")
    print(classification_report(y_test, preds, target_names=['Low', 'Medium', 'High']))
    print("\nConfusion Matrix:")
    print(confusion_matrix(y_test, preds))

    # Save artefacts
    joblib.dump(best_rf, os.path.join(model_dir, 'random_forest.pkl'))
    joblib.dump(scaler,  os.path.join(model_dir, 'scaler.pkl'))
    print("\nrandom_forest.pkl and scaler.pkl saved successfully.")


if __name__ == "__main__":
    t0 = time.time()
    train_and_save_models()
    print(f"\nTotal time: {time.time() - t0:.1f}s")


