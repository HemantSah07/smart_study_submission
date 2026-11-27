import sqlite3
import pyodbc
import json
import os
from dotenv import load_dotenv

# Load environment configurations
load_dotenv()
server = os.getenv('DB_SERVER', 'localhost')

# Find the best SQL Server driver
driver = 'SQL Server'
for d in pyodbc.drivers():
    if 'SQL Server' in d:
        driver = d
        if '17' in d or '18' in d:
            break

print(f"Using ODBC Driver: {driver}")
print(f"Connecting to SQL Server: {server}")

# 1. Connect to SQLite source database
sqlite_path = 'smart_study.db'
if not os.path.exists(sqlite_path):
    raise FileNotFoundError(f"SQLite database not found at {sqlite_path}")

src_conn = sqlite3.connect(sqlite_path)
src_conn.row_factory = sqlite3.Row
src_cursor = src_conn.cursor()

# 2. Extract Data from SQLite
print("Extracting data from SQLite source...")

# Extract Subjects
src_cursor.execute("SELECT id, code, name, level_of_study, program, semester, credit_hours FROM subjects")
subjects = [dict(row) for row in src_cursor.fetchall()]
print(f"Extracted {len(subjects)} subjects.")

# Extract Study Materials (joined with Chapter and Topic)
materials_query = """
SELECT 
    s.id AS subject_id,
    ch.chapter_number,
    ch.name AS chapter_name,
    t.topic_number,
    t.name AS topic_name,
    lm.introduction,
    lm.concepts,
    lm.detailed_explanation,
    lm.mcqs_json
FROM learning_materials lm
JOIN topics t ON lm.topic_id = t.id
JOIN chapters ch ON t.chapter_id = ch.id
JOIN subjects s ON ch.subject_id = s.id
"""
src_cursor.execute(materials_query)
learning_materials = [dict(row) for row in src_cursor.fetchall()]
print(f"Extracted {len(learning_materials)} learning materials.")

# Extract Standalone Assessment Questions
questions_query = """
SELECT 
    aq.subject_id,
    ch.chapter_number,
    ch.name AS chapter_name,
    aq.question_text AS question,
    aq.option_a,
    aq.option_b,
    aq.option_c,
    aq.option_d,
    aq.correct_answer,
    'Assessment Question' AS explanation
FROM assessment_questions aq
JOIN subjects s ON aq.subject_id = s.id
LEFT JOIN chapters ch ON aq.chapter_id = ch.id
"""
src_cursor.execute(questions_query)
assessment_questions = [dict(row) for row in src_cursor.fetchall()]
print(f"Extracted {len(assessment_questions)} assessment questions.")

src_conn.close()

# 3. Process MCQs (combine standalone questions and JSON-based MCQs)
all_mcqs = []

# Add standalone questions
for q in assessment_questions:
    all_mcqs.append({
        'subject_id': q['subject_id'],
        'chapter_number': q['chapter_number'],
        'chapter_name': q['chapter_name'],
        'question': q['question'],
        'option_a': q['option_a'],
        'option_b': q['option_b'],
        'option_c': q['option_c'],
        'option_d': q['option_d'],
        'correct_answer': q['correct_answer'],
        'explanation': q['explanation'] or 'Practice Question'
    })

# Extract and parse inline JSON MCQs from learning materials
for lm in learning_materials:
    mcqs_json_str = lm['mcqs_json']
    if mcqs_json_str:
        try:
            mcqs_list = json.loads(mcqs_json_str)
            if isinstance(mcqs_list, list):
                for m in mcqs_list:
                    all_mcqs.append({
                        'subject_id': lm['subject_id'],
                        'chapter_number': lm['chapter_number'],
                        'chapter_name': lm['chapter_name'],
                        'question': m.get('q', m.get('question', '')),
                        'option_a': m.get('a', m.get('option_a', '')),
                        'option_b': m.get('b', m.get('option_b', '')),
                        'option_c': m.get('c', m.get('option_c', '')),
                        'option_d': m.get('d', m.get('option_d', '')),
                        'correct_answer': m.get('ans', m.get('correct_answer', '')),
                        'explanation': m.get('exp', m.get('explanation', 'Inline Course MCQ'))
                    })
        except Exception as e:
            print(f"Error parsing MCQs JSON for subject {lm['subject_id']}, chapter {lm['chapter_name']}: {e}")

print(f"Total compiled MCQs: {len(all_mcqs)}")

# 4. Connect to SQL Server and Create/Recreate Database 'Syallbus_Contents'
sys_conn_str = f"DRIVER={{{driver}}};SERVER={server};Trusted_Connection=yes;"
db_name = "Syallbus_Contents"

try:
    print("Connecting to SQL Server master database to prepare target database...")
    server_conn = pyodbc.connect(sys_conn_str, autocommit=True)
    server_cursor = server_conn.cursor()
    
    # Recreate Database
    print(f"Checking if database '{db_name}' exists...")
    server_cursor.execute(f"IF EXISTS (SELECT name FROM master.dbo.sysdatabases WHERE name = N'{db_name}') DROP DATABASE {db_name}")
    print(f"Creating database '{db_name}'...")
    server_cursor.execute(f"CREATE DATABASE {db_name}")
    server_conn.close()
    
except Exception as e:
    print(f"Failed to prepare database on SQL Server: {e}")
    raise e

# 5. Connect to the newly created 'Syallbus_Contents' Database
db_conn_str = f"DRIVER={{{driver}}};SERVER={server};DATABASE={db_name};Trusted_Connection=yes;"
db_conn = pyodbc.connect(db_conn_str, autocommit=True)
db_cursor = db_conn.cursor()

# 6. Create Tables in SQL Server
print("Creating tables in SQL Server...")
db_cursor.execute("""
CREATE TABLE Subjects (
    subject_id INT PRIMARY KEY,
    code NVARCHAR(50),
    name NVARCHAR(250) NOT NULL,
    level_of_study NVARCHAR(100),
    program NVARCHAR(150),
    semester NVARCHAR(100),
    credit_hours INT
)
""")

db_cursor.execute("""
CREATE TABLE StudyMaterials (
    material_id INT IDENTITY(1,1) PRIMARY KEY,
    subject_id INT FOREIGN KEY REFERENCES Subjects(subject_id) ON DELETE CASCADE,
    chapter_number INT,
    chapter_name NVARCHAR(250),
    topic_number INT,
    topic_name NVARCHAR(250),
    introduction NVARCHAR(MAX),
    basic_concept NVARCHAR(MAX)
)
""")

db_cursor.execute("""
CREATE TABLE MCQs (
    mcq_id INT IDENTITY(1,1) PRIMARY KEY,
    subject_id INT FOREIGN KEY REFERENCES Subjects(subject_id) ON DELETE CASCADE,
    chapter_number INT,
    chapter_name NVARCHAR(250),
    question NVARCHAR(MAX) NOT NULL,
    option_a NVARCHAR(1000) NOT NULL,
    option_b NVARCHAR(1000) NOT NULL,
    option_c NVARCHAR(1000) NOT NULL,
    option_d NVARCHAR(1000) NOT NULL,
    correct_answer NVARCHAR(10) NOT NULL,
    explanation NVARCHAR(MAX)
)
""")
print("Tables created successfully.")

# 7. Seed data into SQL Server using parameterized queries
print("Inserting data into SQL Server...")

# Insert Subjects
print("Seeding Subjects table...")
subject_insert = """
INSERT INTO Subjects (subject_id, code, name, level_of_study, program, semester, credit_hours)
VALUES (?, ?, ?, ?, ?, ?, ?)
"""
for sub in subjects:
    db_cursor.execute(
        subject_insert, 
        sub['id'], 
        sub['code'], 
        sub['name'], 
        sub['level_of_study'], 
        sub['program'], 
        sub['semester'], 
        sub['credit_hours']
    )

# Insert StudyMaterials
print("Seeding StudyMaterials table...")
material_insert = """
INSERT INTO StudyMaterials (subject_id, chapter_number, chapter_name, topic_number, topic_name, introduction, basic_concept)
VALUES (?, ?, ?, ?, ?, ?, ?)
"""
for lm in learning_materials:
    # Build basic concept by combining concepts and detailed explanation
    concept_parts = []
    if lm['concepts']:
        concept_parts.append(lm['concepts'])
    if lm['detailed_explanation']:
        concept_parts.append(lm['detailed_explanation'])
    basic_concept = "\n\n".join(concept_parts) if concept_parts else ""
    
    db_cursor.execute(
        material_insert,
        lm['subject_id'],
        lm['chapter_number'],
        lm['chapter_name'],
        lm['topic_number'],
        lm['topic_name'],
        lm['introduction'],
        basic_concept
    )

# Insert MCQs
print("Seeding MCQs table...")
mcq_insert = """
INSERT INTO MCQs (subject_id, chapter_number, chapter_name, question, option_a, option_b, option_c, option_d, correct_answer, explanation)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""
for m in all_mcqs:
    db_cursor.execute(
        mcq_insert,
        m['subject_id'],
        m['chapter_number'],
        m['chapter_name'],
        m['question'],
        m['option_a'],
        m['option_b'],
        m['option_c'],
        m['option_d'],
        m['correct_answer'],
        m['explanation']
    )

print("SQL Server Database seeding completed successfully!")

# 8. Generate portable SQL file for export / backup
print("Generating portable SQL script 'Syallbus_Contents.sql'...")

def sql_val(val):
    if val is None:
        return "NULL"
    if isinstance(val, (int, float)):
        return str(val)
    escaped = str(val).replace("'", "''")
    return f"N'{escaped}'"

sql_file_path = 'Syallbus_Contents.sql'
with open(sql_file_path, 'w', encoding='utf-8') as f:
    f.write("/*\n")
    f.write("  Syallbus_Contents SQL Server Database Dump\n")
    f.write(f"  Generated on: 2026-07-10\n")
    f.write("*/\n\n")
    
    f.write("USE master;\nGO\n\n")
    f.write("IF EXISTS (SELECT name FROM master.dbo.sysdatabases WHERE name = N'Syallbus_Contents')\n")
    f.write("    DROP DATABASE Syallbus_Contents;\nGO\n\n")
    f.write("CREATE DATABASE Syallbus_Contents;\nGO\n\n")
    f.write("USE Syallbus_Contents;\nGO\n\n")
    
    # Write Tables Schema
    f.write("CREATE TABLE Subjects (\n")
    f.write("    subject_id INT PRIMARY KEY,\n")
    f.write("    code NVARCHAR(50),\n")
    f.write("    name NVARCHAR(250) NOT NULL,\n")
    f.write("    level_of_study NVARCHAR(100),\n")
    f.write("    program NVARCHAR(150),\n")
    f.write("    semester NVARCHAR(100),\n")
    f.write("    credit_hours INT\n")
    f.write(");\nGO\n\n")
    
    f.write("CREATE TABLE StudyMaterials (\n")
    f.write("    material_id INT IDENTITY(1,1) PRIMARY KEY,\n")
    f.write("    subject_id INT FOREIGN KEY REFERENCES Subjects(subject_id) ON DELETE CASCADE,\n")
    f.write("    chapter_number INT,\n")
    f.write("    chapter_name NVARCHAR(250),\n")
    f.write("    topic_number INT,\n")
    f.write("    topic_name NVARCHAR(250),\n")
    f.write("    introduction NVARCHAR(MAX),\n")
    f.write("    basic_concept NVARCHAR(MAX)\n")
    f.write(");\nGO\n\n")
    
    f.write("CREATE TABLE MCQs (\n")
    f.write("    mcq_id INT IDENTITY(1,1) PRIMARY KEY,\n")
    f.write("    subject_id INT FOREIGN KEY REFERENCES Subjects(subject_id) ON DELETE CASCADE,\n")
    f.write("    chapter_number INT,\n")
    f.write("    chapter_name NVARCHAR(250),\n")
    f.write("    question NVARCHAR(MAX) NOT NULL,\n")
    f.write("    option_a NVARCHAR(1000) NOT NULL,\n")
    f.write("    option_b NVARCHAR(1000) NOT NULL,\n")
    f.write("    option_c NVARCHAR(1000) NOT NULL,\n")
    f.write("    option_d NVARCHAR(1000) NOT NULL,\n")
    f.write("    correct_answer NVARCHAR(10) NOT NULL,\n")
    f.write("    explanation NVARCHAR(MAX)\n")
    f.write(");\nGO\n\n")
    
    # Write Subjects Insert statements
    f.write("-- Seeding Subjects\n")
    for sub in subjects:
        f.write(f"INSERT INTO Subjects (subject_id, code, name, level_of_study, program, semester, credit_hours) VALUES ")
        f.write(f"({sql_val(sub['id'])}, {sql_val(sub['code'])}, {sql_val(sub['name'])}, {sql_val(sub['level_of_study'])}, {sql_val(sub['program'])}, {sql_val(sub['semester'])}, {sql_val(sub['credit_hours'])});\n")
    f.write("GO\n\n")
    
    # Write StudyMaterials Insert statements
    f.write("-- Seeding StudyMaterials\n")
    for lm in learning_materials:
        concept_parts = []
        if lm['concepts']:
            concept_parts.append(lm['concepts'])
        if lm['detailed_explanation']:
            concept_parts.append(lm['detailed_explanation'])
        basic_concept = "\n\n".join(concept_parts) if concept_parts else ""
        
        f.write(f"INSERT INTO StudyMaterials (subject_id, chapter_number, chapter_name, topic_number, topic_name, introduction, basic_concept) VALUES ")
        f.write(f"({sql_val(lm['subject_id'])}, {sql_val(lm['chapter_number'])}, {sql_val(lm['chapter_name'])}, {sql_val(lm['topic_number'])}, {sql_val(lm['topic_name'])}, {sql_val(lm['introduction'])}, {sql_val(basic_concept)});\n")
    f.write("GO\n\n")
    
    # Write MCQs Insert statements
    f.write("-- Seeding MCQs\n")
    for m in all_mcqs:
        f.write(f"INSERT INTO MCQs (subject_id, chapter_number, chapter_name, question, option_a, option_b, option_c, option_d, correct_answer, explanation) VALUES ")
        f.write(f"({sql_val(m['subject_id'])}, {sql_val(m['chapter_number'])}, {sql_val(m['chapter_name'])}, {sql_val(m['question'])}, {sql_val(m['option_a'])}, {sql_val(m['option_b'])}, {sql_val(m['option_c'])}, {sql_val(m['option_d'])}, {sql_val(m['correct_answer'])}, {sql_val(m['explanation'])});\n")
    f.write("GO\n\n")

print(f"Successfully generated portable SQL script at '{sql_file_path}'!")

db_conn.close()
