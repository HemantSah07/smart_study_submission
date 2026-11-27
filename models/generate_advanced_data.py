import pandas as pd
import numpy as np
import os

def generate_advanced_data(num_samples=50000):
    print(f"Generating {num_samples} advanced synthetic student profiles...")
    np.random.seed(42)
    
    # Archetype distribution
    # 30% High Achievers, 50% Average, 20% Struggling
    n_high = int(num_samples * 0.3)
    n_avg = int(num_samples * 0.5)
    n_struggling = num_samples - n_high - n_avg
    
    def generate_archetype(n, attendance_mu, study_hr_mu, exam_mu, risk_val):
        attendance = np.clip(np.random.normal(attendance_mu, 10, n), 10, 100)
        assign_comp = np.clip(attendance + np.random.normal(0, 10, n), 10, 100)
        
        weekly_study = np.clip(np.random.normal(study_hr_mu, 5, n), 0, 60)
        total_study = np.clip(weekly_study * np.random.uniform(10, 15, n), 0, 1000)
        study_days = np.clip(np.random.normal(study_hr_mu * 5, 20, n), 10, 240)
        
        difficulty = np.random.uniform(1, 5, n)
        
        # Exam scores correlate with study hours and attendance
        midterm = np.clip(np.random.normal(exam_mu, 12, n) - (difficulty * 2), 0, 100)
        final = np.clip(midterm + np.random.normal(5, 10, n), 0, 100)
        avg_exam = (midterm + final) / 2
        
        assign_avg = np.clip(assign_comp - np.random.normal(5, 5, n), 0, 100)
        
        year = np.random.randint(1, 5, n)
        
        # GPA highly correlated with avg exam
        gpa = np.clip((avg_exam / 100) * 4.0 + np.random.normal(0, 0.2, n), 0, 4.0)
        
        return pd.DataFrame({
            'attendance_pct': attendance,
            'assignment_completion_pct': assign_comp,
            'weekly_study_hours': weekly_study,
            'total_logged_study_hours': total_study,
            'study_days_last_240': study_days,
            'subject_difficulty': difficulty,
            'avg_exam_score_pct': avg_exam,
            'midterm_score_pct': midterm,
            'final_score_pct': final,
            'assignment_avg_pct': assign_avg,
            'year_of_study': year,
            'cumulative_gpa': gpa,
            'risk_numeric': np.full(n, risk_val)
        })

    high_df = generate_archetype(n_high, attendance_mu=92, study_hr_mu=25, exam_mu=88, risk_val=0)
    avg_df = generate_archetype(n_avg, attendance_mu=75, study_hr_mu=14, exam_mu=65, risk_val=1)
    strug_df = generate_archetype(n_struggling, attendance_mu=45, study_hr_mu=5, exam_mu=40, risk_val=2)
    
    final_df = pd.concat([high_df, avg_df, strug_df]).sample(frac=1).reset_index(drop=True)
    
    # Save to CSV
    output_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(output_dir, 'ML_advanced_synthetic_data.csv')
    final_df.to_csv(output_path, index=False)
    print(f"Data saved to {output_path}")

if __name__ == "__main__":
    generate_advanced_data()
