# app/services/text_extraction.py
import os
from PIL import Image
import pytesseract
from app.utils.doc_extractor import extract_document

def extract_text_from_file(file_path: str, file_type: str) -> str:
    """
    Central shared text extraction dispatcher.
    Reuses existing doc_extractor engine for pdf/docx/pptx and PyTesseract OCR for images.
    Returns concatenated extracted text string. Zero duplication of extraction logic.
    """
    ext = file_type.lstrip('.').lower()
    
    if ext in ('pdf', 'docx', 'pptx'):
        res = extract_document(file_path)
        if res and res.get('extraction_ok'):
            text_blocks = [b.get('text', '') for b in res.get('text_blocks', []) if b.get('text')]
            if not any(b.get('is_table') for b in res.get('text_blocks', [])):
                for table in res.get('tables', []):
                    for row in table:
                        text_blocks.append(' | '.join(str(cell) for cell in row if cell))
            return '\n'.join(text_blocks).strip()
        return ''
    elif ext == 'txt':
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read().strip()
        except Exception:
            return ''
    elif ext in ('png', 'jpg', 'jpeg'):
        try:
            with Image.open(file_path) as img:
                return pytesseract.image_to_string(img).strip()
        except Exception:
            return ''
    return ''
