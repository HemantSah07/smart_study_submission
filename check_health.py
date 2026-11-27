import os
import sys
from dotenv import load_dotenv

load_dotenv()

print("=" * 60)
print("       SMART STUDY SYSTEM HEALTH CHECK       ")
print("=" * 60)

# 1. Check Database
print("\n[1/5] Checking Database...")
try:
    from app import create_app, db
    from app.models import User, Subject, StudentProfile
    app = create_app()
    with app.app_context():
        user_count = User.query.count()
        subj_count = Subject.query.count()
        db_uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
        print(f"  [OK] Database connected! URI: {db_uri}")
        print(f"  [OK] Users count: {user_count}, Subjects count: {subj_count}")
except Exception as e:
    print(f"  [FAIL] Database error: {e}")

# 2. Check ML Models
print("\n[2/5] Checking ML Model artifacts...")
models_dir = os.path.join(os.path.dirname(__file__), "models")
expected_models = [
    "random_forest.pkl", "scaler.pkl",
    "rf_bachelors.pkl", "scaler_bachelors.pkl",
    "rf_class11.pkl", "scaler_class11.pkl",
    "rf_class12.pkl", "scaler_class12.pkl",
    "rf_class8.pkl", "scaler_class8.pkl",
    "rf_masters.pkl", "scaler_masters.pkl",
    "rf_see.pkl", "scaler_see.pkl"
]
missing_models = [m for m in expected_models if not os.path.isfile(os.path.join(models_dir, m))]
if not missing_models:
    print(f"  [OK] All {len(expected_models)} ML models and scalers are present!")
else:
    print(f"  [WARNING] Missing models: {missing_models}")

# 3. Check AI Provider & Gemini API
print("\n[3/5] Checking Gemini API...")
gemini_key = os.getenv("GEMINI_API_KEY_FREE") or os.getenv("GEMINI_API_KEY")
if not gemini_key or gemini_key.strip() == "":
    print("  [FAIL] GEMINI_API_KEY_FREE is empty in .env!")
elif not gemini_key.startswith("AIzaSy"):
    print(f"  [WARNING] API key starts with '{gemini_key[:7]}...'. Standard Google AI Studio keys start with 'AIzaSy'.")
    print("  Testing connection anyway...")

try:
    import google.generativeai as genai
    genai.configure(api_key=gemini_key)
    model_name = os.getenv("GEMINI_MODEL_ASSISTANT_PRIMARY", "gemini-3.6-flash")
    model = genai.GenerativeModel(model_name)
    res = model.generate_content("Say hello in one word.")
    print(f"  [OK] Gemini API responded successfully: '{res.text.strip()}' (Model: {model_name})")
except Exception as e:
    print(f"  [FAIL] Gemini API call failed: {e}")
    print("  --> Please get a free API key from https://aistudio.google.com/app/apikey and put it in .env")

# 4. Check Tesseract OCR
print("\n[4/5] Checking Tesseract OCR...")
try:
    import pytesseract
    ver = pytesseract.get_tesseract_version()
    print(f"  [OK] Tesseract OCR is installed! Version: {ver}")
except Exception as e:
    print(f"  [WARNING] Tesseract OCR not detected: {e}")
    print("  (Only needed for extracting text from scanned images/PDFs)")

# 5. Check Template & Static counts
print("\n[5/5] Checking UI Assets...")
tpl_count = 0
for root, _, files in os.walk(os.path.join(os.path.dirname(__file__), "app", "templates")):
    tpl_count += len([f for f in files if f.endswith(".html")])
static_count = 0
for root, _, files in os.walk(os.path.join(os.path.dirname(__file__), "app", "static")):
    static_count += len(files)
print(f"  [OK] HTML Templates: {tpl_count} found")
print(f"  [OK] Static files: {static_count} found")

print("\n" + "=" * 60)
print("Diagnostic Complete!")
print("=" * 60)
