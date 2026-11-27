import re

import pdfplumber
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

GRADE_TO_PCT = {
    "A+": 95, "A": 85, "B+": 75, "B": 65,
    "C+": 55, "C": 45, "D+": 40, "D": 35, "NG": 30,
    "A*": 95, "E": 45,
}

GPA_TO_PCT = {
    4.0: 95, 3.6: 85, 3.2: 75, 2.8: 65,
    2.4: 55, 2.0: 45, 1.6: 38, 1.2: 30,
}

HEADER_WORDS = {
    "school", "college", "campus", "student", "name", "roll", "symbol",
    "registration", "regd", "dob", "date", "year", "exam", "examination",
    "marksheet", "grade-sheet", "gradesheet", "ledger", "statement",
    "subject", "subjects", "grade", "obtained", "credit", "hour", "hours",
    "point", "average", "practical", "theory", "appeared", "supplementary",
    "equals", "clock", "remarks",
    "board", "municipality", "address", "father", "mother", "principal",
    "signature", "total", "grand", "percentage", "gpa", "sgpa", "cgpa",
    "division", "rank", "result", "passed", "failed",
}

SUBJECT_HINTS = {
    "english", "nepali", "mathematics", "math", "science", "social",
    "studies", "computer", "physics", "chemistry", "biology", "economics",
    "account", "accountancy", "business", "optional", "health", "population",
    "environment", "moral", "education", "grammar", "literature", "statistics",
    "history", "geography", "civics", "commerce", "finance", "marketing",
    "sociology", "psychology", "law", "political", "opt",
}

SEE_SUBJECT_PATTERNS = [
    ("English", [r"\beng(?:lish)?\b"]),
    ("Nepali", [r"\bnepali\b"]),
    ("Computer Science", [r"computer\s+science", r"conputer\s+science"]),
    ("Optional Mathematics", [r"additional\s+(?:mathematics|nathematics)", r"opt\.?\s*i?.*(?:math|nath)"]),
    ("Mathematics", [r"mathematics", r"nathematics", r"mathenatics", r"aathenatics", r"hathenatics", r"fathenatics"]),
    ("Science", [r"\bscience\b"]),
    ("Social Studies", [r"social\s+stud", r"sor\w+\s+stu", r"sac\w+\s+stu"]),
    ("Health and Population", [r"health", r"\bpup\b", r"population", r"env(?:ironment)?"]),
]


class MarksheetProcessor:
    def process_file(self, filepath, file_type):
        if file_type == "pdf":
            return self.process_pdf(filepath)
        return self.process_image(filepath)

    def process_pdf(self, filepath):
        rows = []
        text_parts = []
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                rows.extend(self._table_rows_from_pdf_page(page))
                text_parts.append(page.extract_text() or "")
        text_rows = [line.strip() for line in "\n".join(text_parts).splitlines() if line.strip()]
        marks = self.extract_marks_from_rows(rows + text_rows)
        return marks, self._overall_confidence(marks)

    def process_image(self, filepath):
        img = Image.open(filepath).convert("L")
        img = ImageEnhance.Contrast(img).enhance(2.0)
        img = img.filter(ImageFilter.SHARPEN)
        table_crop = self._marks_table_crop(img)
        rows = self._ocr_string_rows_from_image(table_crop)
        rows.extend(self._ocr_rows_from_image(table_crop))
        rows.extend(self._ocr_rows_from_image(img))
        marks = self.extract_marks_from_rows(rows)
        if not marks:
            text = "\n".join(self._row_text(row) for row in rows)
            marks = self.extract_marks(text)
        return marks, self._overall_confidence(marks)

    def _marks_table_crop(self, img):
        width, height = img.size
        box = (
            int(width * 0.10),
            int(height * 0.32),
            int(width * 0.88),
            int(height * 0.64),
        )
        crop = img.crop(box)
        crop = ImageOps.autocontrast(crop)
        crop = crop.resize((crop.width * 2, crop.height * 2))
        crop = ImageEnhance.Contrast(crop).enhance(2.5)
        return crop.filter(ImageFilter.SHARPEN)

    def _table_rows_from_pdf_page(self, page):
        rows = []
        table_settings = {
            "vertical_strategy": "text",
            "horizontal_strategy": "text",
            "snap_tolerance": 4,
            "join_tolerance": 4,
            "intersection_tolerance": 6,
            "text_tolerance": 3,
        }
        try:
            tables = page.extract_tables(table_settings=table_settings) or []
        except Exception:
            tables = []
        for table in tables:
            for row in table or []:
                cells = [str(cell or "").strip() for cell in row]
                if any(cells):
                    rows.append(" | ".join(cells))
        return rows

    def _ocr_rows_from_image(self, img):
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT, config="--psm 6")
        lines = {}
        count = len(data.get("text", []))
        for i in range(count):
            word = (data["text"][i] or "").strip()
            if not word:
                continue
            try:
                conf = float(data["conf"][i])
            except Exception:
                conf = -1
            if conf < 0:
                continue
            key = (data.get("block_num", [0])[i], data.get("par_num", [0])[i], data.get("line_num", [0])[i])
            lines.setdefault(key, []).append((data.get("left", [0])[i], word, conf))
        ordered = []
        for key in sorted(lines):
            line_words = sorted(lines[key], key=lambda item: item[0])
            words = [word for _, word, _ in line_words]
            avg_conf = sum(conf for _, _, conf in line_words) / len(line_words)
            ordered.append({"text": " ".join(words), "confidence": round(avg_conf / 100.0, 2)})
        return ordered

    def _ocr_string_rows_from_image(self, img):
        try:
            text = pytesseract.image_to_string(img, config="--psm 6")
        except Exception:
            return []
        return [
            {"text": line.strip(), "confidence": 0.45}
            for line in text.splitlines()
            if line.strip()
        ]

    def extract_marks(self, text):
        rows = [line.strip() for line in (text or "").splitlines() if line.strip()]
        return self.extract_marks_from_rows(rows)

    def extract_marks_from_rows(self, rows):
        marks = []
        by_key = {}
        for row in rows:
            row_text = self._row_text(row)
            row_confidence = self._row_confidence(row)
            parsed = self._parse_mark_row(row_text, row_confidence)
            if not parsed:
                continue
            key = re.sub(r"[^a-z0-9]+", "", parsed["subject"].lower())
            if key in by_key:
                existing_index = by_key[key]
                if self._candidate_rank(parsed) > self._candidate_rank(marks[existing_index]):
                    marks[existing_index] = parsed
                continue
            by_key[key] = len(marks)
            marks.append(parsed)
        return marks

    def _candidate_rank(self, parsed):
        try:
            confidence = float(parsed.get("confidence", 0))
        except (TypeError, ValueError):
            confidence = 0
        value = str(parsed.get("value") or "").upper()
        raw_row = str(parsed.get("raw_row") or "")
        rank = confidence
        if value in GRADE_TO_PCT:
            rank += 0.08
        if "+" in value:
            rank += 0.12
        if self._grade_point_from_row(raw_row) is not None:
            rank += 0.05
        return rank

    def _row_text(self, row):
        if isinstance(row, dict):
            return str(row.get("text") or row.get("raw_row") or "")
        if isinstance(row, (tuple, list)) and row:
            return str(row[0])
        return str(row or "")

    def _row_confidence(self, row):
        if isinstance(row, dict):
            try:
                return float(row.get("confidence"))
            except (TypeError, ValueError):
                return None
        if isinstance(row, (tuple, list)) and len(row) > 1:
            try:
                return float(row[1])
            except (TypeError, ValueError):
                return None
        return None

    def _parse_mark_row(self, row, row_confidence=None):
        clean = re.sub(r"\s+", " ", (row or "").replace("|", " ")).strip()
        if not clean or len(clean) < 6:
            return None
        if self._is_noise_row(clean):
            return None
        confidence_cap = self._confidence_cap(row_confidence)

        grade_row = self._parse_see_grade_row(clean, confidence_cap)
        if grade_row:
            return grade_row

        slash_match = re.search(r"(.+?)\s+(\d{1,3}(?:\.\d{1,2})?)\s*/\s*(\d{1,3}(?:\.\d{1,2})?)\b", clean)
        if slash_match:
            return self._build_row(slash_match.group(1), slash_match.group(2), slash_match.group(3), clean, min(0.9, confidence_cap))

        tokens = clean.split()
        numeric_positions = []
        for idx, token in enumerate(tokens):
            stripped = token.strip("(),:")
            if re.fullmatch(r"\d{1,3}(?:\.\d{1,2})?", stripped):
                val = float(stripped)
                if 0 <= val <= 100:
                    numeric_positions.append((idx, stripped))

        grade_positions = []
        for idx, token in enumerate(tokens):
            stripped = token.strip("(),:").upper()
            if stripped in GRADE_TO_PCT:
                grade_positions.append((idx, stripped))

        if numeric_positions:
            first_idx = numeric_positions[0][0]
            subject = " ".join(tokens[:first_idx])
            mark_value = numeric_positions[-1][1]
            full_marks = "100"
            if len(numeric_positions) >= 2:
                first_value = float(numeric_positions[0][1])
                second_value = float(numeric_positions[1][1])
                if first_value in (25, 50, 75, 100) and second_value <= first_value:
                    full_marks = numeric_positions[0][1]
                    mark_value = numeric_positions[1][1]
                elif second_value in (25, 50, 75, 100) and first_value <= second_value:
                    full_marks = numeric_positions[1][1]
                    mark_value = numeric_positions[0][1]
            return self._build_row(subject, mark_value, full_marks, clean, min(0.85, confidence_cap))

        if grade_positions:
            grade_idx, grade_value = grade_positions[-1]
            subject = " ".join(tokens[:grade_idx])
            return self._build_row(subject, grade_value, "100", clean, min(0.75, confidence_cap))

        return None

    def _parse_see_grade_row(self, clean, confidence_cap):
        subject = self._see_subject_from_row(clean)
        if not subject:
            return None

        grade = self._final_grade_from_row(clean)
        if grade:
            return self._build_row(subject, grade, "100", clean, min(0.82, confidence_cap))

        point = self._grade_point_from_row(clean)
        if point is not None:
            return self._build_row(subject, point, "4", clean, min(0.7, confidence_cap))

        return None

    def _see_subject_from_row(self, clean):
        lower = clean.lower()
        if not re.search(r"\b(?:0?[1-9]|comp|conf|opt|gpt|cgmf|eomp|conp|comf)\b", lower):
            return None
        for subject, patterns in SEE_SUBJECT_PATTERNS:
            if any(re.search(pattern, lower) for pattern in patterns):
                return subject
        return None

    def _final_grade_from_row(self, clean):
        tokens = re.findall(r"[A-Za-z][A-Za-z+*]*|\d+(?:\.\d+)?", clean)
        grades = []
        for token in tokens:
            grade = self._normalize_grade_token(token)
            if grade:
                grades.append(grade)
        return grades[-1] if grades else None

    def _normalize_grade_token(self, token):
        value = (token or "").strip().upper().replace("*", "+")
        replacements = {
            "AT": "A+", "A+": "A+", "A": "A", "AE": "A", "PA": "A",
            "BT": "B+", "BE": "B+", "BR": "B+", "B+": "B+", "B": "B",
            "CT": "C+", "C+": "C+", "C": "C",
            "DT": "D+", "D+": "D+", "D": "D",
            "PE": "B+", "PES": "B+", "PEES": "B+",
            "NG": "NG",
        }
        return replacements.get(value)

    def _grade_point_from_row(self, clean):
        candidates = []
        for raw in re.findall(r"(?<!\d)([234]\s*[\.\]\[]?\s*\d{1,2})(?!\d)", clean):
            normalized = re.sub(r"[^0-9]", "", raw)
            if len(normalized) == 2:
                value = float(f"{normalized[0]}.{normalized[1]}")
                if 0 <= value <= 4:
                    candidates.append(value)
            elif len(normalized) == 3:
                value = float(f"{normalized[0]}.{normalized[1:]}")
                if 0 <= value <= 4:
                    candidates.append(value)
        return str(candidates[-1]) if candidates else None

    def _confidence_cap(self, row_confidence):
        if row_confidence is None:
            return 1.0
        try:
            confidence = float(row_confidence)
        except (TypeError, ValueError):
            return 1.0
        if confidence > 1:
            confidence = confidence / 100.0
        return max(0.25, min(confidence, 1.0))

    def _build_row(self, subject, value, full_marks, raw_row, confidence):
        subject = self._clean_subject(subject)
        subject_quality = self._subject_quality(subject)
        if subject_quality <= 0:
            return None
        return {
            "subject": subject,
            "value": value,
            "full_marks": full_marks,
            "raw_row": raw_row,
            "confidence": round(max(0.25, min(confidence, subject_quality)), 2),
        }

    def _clean_subject(self, subject):
        subject = re.sub(r"^\d+[\).:-]?\s*", "", subject or "")
        subject = re.sub(r"\b(subject|sub|code|th|pr|credit|grade|marks?|obtained|full)\b", "", subject, flags=re.I)
        subject = re.sub(r"[^A-Za-z&/().\-\s]", " ", subject)
        return re.sub(r"\s+", " ", subject).strip(" -:|")

    def _looks_like_subject(self, subject):
        return self._subject_quality(subject) > 0

    def _subject_quality(self, subject):
        if not subject or len(subject) < 3 or len(subject) > 60:
            return 0.0
        words = [w.lower().strip(".()") for w in subject.split()]
        words = [w for w in words if w]
        if not words or len(words) > 6:
            return 0.0
        if any(word in HEADER_WORDS for word in words):
            return 0.0
        alpha_chars = sum(ch.isalpha() for ch in subject)
        if alpha_chars < 3:
            return 0.0
        joined = " ".join(words)
        if any(hint in joined for hint in SUBJECT_HINTS):
            return 0.95
        if len(words) <= 4 and re.fullmatch(r"[A-Za-z&/().\-\s]+", subject):
            return 0.45
        return 0.0

    def _is_noise_row(self, row):
        lower = row.lower()
        if sum(1 for word in HEADER_WORDS if word in lower) >= 2:
            return True
        if re.search(r"\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b", lower):
            return True
        if re.search(r"\b(phone|email|www|http|street|ward)\b", lower):
            return True
        return False

    def _overall_confidence(self, marks):
        if not marks:
            return 0.0
        avg = sum(float(m.get("confidence", 0.5)) for m in marks) / len(marks)
        coverage = min(len(marks) / 5.0, 1.0)
        return round(min(1.0, avg * 0.7 + coverage * 0.3), 2)

    def convert_to_percentage(self, value, full_marks="100"):
        value = str(value).strip()
        try:
            val = float(value)
            full = float(full_marks) if full_marks else 100
            if full > 0 and val <= full:
                return round(val / full * 100, 2)
        except Exception:
            pass
        if value.upper() in GRADE_TO_PCT:
            return GRADE_TO_PCT[value.upper()]
        try:
            gpa = float(value)
            closest = min(GPA_TO_PCT.keys(), key=lambda k: abs(k - gpa))
            return GPA_TO_PCT[closest]
        except Exception:
            return None
