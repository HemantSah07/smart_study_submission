"""
app/utils/doc_extractor.py

Phase 4C — Document Extraction Engine

Extracts text content from .docx, .pdf, and .pptx files.
Returns a consistent internal structure regardless of input type.

Design rules:
- Never executes uploaded content.
- Never silently claims OCR was done if OCR was not performed.
- Marks scanned/image-only PDFs as NEEDS_OCR.
- Uses only already-installed libraries (fitz/PyMuPDF, pdfplumber, docx, pptx).
"""

import os
import re
from typing import Any


# ── Extraction result schema ──────────────────────────────────────────────────

def _make_result(source_file: str, doc_type: str) -> dict:
    return {
        "source_file": source_file,
        "document_type": doc_type,       # docx | pdf | pptx
        "text_blocks": [],               # list of {"heading": bool, "text": str}
        "tables": [],                    # list of list[list[str]]
        "metadata": {},
        "warnings": [],                  # non-fatal issues
        "needs_ocr": False,              # True when scanned PDF detected
        "extraction_ok": True,
    }


def _clean(text: str) -> str:
    """Normalize whitespace, strip invisible chars."""
    if not text:
        return ""
    text = text.replace("\u00a0", " ").replace("\u200b", "")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# ── DOCX extraction ───────────────────────────────────────────────────────────

def extract_docx(file_path: str) -> dict:
    result = _make_result(os.path.basename(file_path), "docx")
    try:
        import docx as python_docx
        with open(file_path, "rb") as f:
            doc = python_docx.Document(f)

            for para in doc.paragraphs:
                text = _clean(para.text)
                if not text:
                    continue
                # Detect headings by style name
                style_name = (para.style.name or "").lower()
                is_heading = "heading" in style_name or para.runs and any(
                    r.bold for r in para.runs if r.text.strip()
                )
                result["text_blocks"].append({
                    "heading": is_heading,
                    "text": text,
                    "style": para.style.name,
                })

            for table in doc.tables:
                rows = []
                for row in table.rows:
                    row_data = [_clean(cell.text) for cell in row.cells]
                    rows.append(row_data)
                if rows:
                    result["tables"].append(rows)
                    if len(rows) > 0:
                        header = "| " + " | ".join(rows[0]) + " |"
                        separator = "| " + " | ".join(["---"] * len(rows[0])) + " |"
                        body = ["| " + " | ".join(r) + " |" for r in rows[1:]]
                        table_md = "\n".join([header, separator] + body)
                        result["text_blocks"].append({
                            "heading": False,
                            "text": f"\n{table_md}\n",
                            "is_table": True
                        })

            # Core properties
            try:
                cp = doc.core_properties
                result["metadata"] = {
                    "title": cp.title or "",
                    "author": cp.author or "",
                    "subject": cp.subject or "",
                }
            except Exception:
                pass

    except Exception as e:
        result["extraction_ok"] = False
        result["warnings"].append(f"DOCX extraction error: {e}")
    return result


# ── PDF extraction ─────────────────────────────────────────────────────────────

def extract_pdf(file_path: str) -> dict:
    result = _make_result(os.path.basename(file_path), "pdf")
    doc = None
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(file_path)
        total_char_count = 0

        for page_num, page in enumerate(doc):
            blocks = page.get_text("dict").get("blocks", [])
            for block in blocks:
                if block.get("type") != 0:  # 0 = text block
                    continue
                for line in block.get("lines", []):
                    line_text = " ".join(
                        _clean(span.get("text", ""))
                        for span in line.get("spans", [])
                    )
                    if not line_text:
                        continue
                    total_char_count += len(line_text)
                    # Estimate heading by font size
                    avg_size = max(
                        (span.get("size", 10) for span in line.get("spans", [])),
                        default=10
                    )
                    result["text_blocks"].append({
                        "heading": avg_size >= 14,
                        "text": line_text,
                        "page": page_num + 1,
                        "font_size": avg_size,
                    })

        # Detect scanned/image-only PDF
        if total_char_count < 50 and len(doc) > 0:
            result["needs_ocr"] = True
            result["warnings"].append(
                "Very little text extracted — this PDF may be scanned or image-based. "
                "Manual OCR or manual review is required."
            )

        result["metadata"]["page_count"] = len(doc)

    except Exception as e:
        result["extraction_ok"] = False
        result["warnings"].append(f"PDF extraction error: {e}")
    finally:
        if doc is not None:
            try:
                doc.close()
            except Exception:
                pass

    # Also attempt table extraction via pdfplumber as a supplement
    if result["extraction_ok"]:
        try:
            import pdfplumber
            with pdfplumber.open(file_path) as pdf:
                for page_num, page in enumerate(pdf.pages, start=1):
                    for table in (page.extract_tables() or []):
                        cleaned = [
                            [_clean(str(cell)) if cell else "" for cell in row]
                            for row in table
                        ]
                        if cleaned and len(cleaned) > 0:
                            result["tables"].append(cleaned)
                            header = "| " + " | ".join(cleaned[0]) + " |"
                            separator = "| " + " | ".join(["---"] * len(cleaned[0])) + " |"
                            body = ["| " + " | ".join(r) + " |" for r in cleaned[1:]]
                            table_md = "\n".join([header, separator] + body)
                            result["text_blocks"].append({
                                "heading": False,
                                "text": f"\n{table_md}\n",
                                "page": page_num,
                                "is_table": True
                            })
        except Exception as e:
            result["warnings"].append(f"pdfplumber table extraction warning: {e}")

    return result


# ── PPTX extraction ────────────────────────────────────────────────────────────

def extract_pptx(file_path: str) -> dict:
    result = _make_result(os.path.basename(file_path), "pptx")
    try:
        from pptx import Presentation
        from pptx.util import Pt

        with open(file_path, "rb") as f:
            prs = Presentation(f)
            result["metadata"]["slide_count"] = len(prs.slides)

            for slide_num, slide in enumerate(prs.slides, start=1):
                result["text_blocks"].append({
                    "heading": True,
                    "text": f"--- Slide {slide_num} ---",
                    "slide": slide_num,
                    "is_slide_header": True
                })
                for shape in slide.shapes:
                    if not shape.has_text_frame:
                        continue
                    for para in shape.text_frame.paragraphs:
                        text = _clean("".join(run.text for run in para.runs))
                        if not text:
                            continue
                        # Detect heading by font size or level
                        is_heading = para.level == 0 and any(
                            (run.font.size or 0) >= Pt(14) for run in para.runs if run.font.size
                        )
                        result["text_blocks"].append({
                            "heading": is_heading,
                            "text": text,
                            "slide": slide_num,
                        })

                    # Extract tables from shapes
                    if shape.shape_type == 19:  # TABLE
                        try:
                            rows = []
                            for row in shape.table.rows:
                                rows.append([_clean(cell.text) for cell in row.cells])
                            if rows:
                                result["tables"].append(rows)
                                if len(rows) > 0:
                                    header = "| " + " | ".join(rows[0]) + " |"
                                    separator = "| " + " | ".join(["---"] * len(rows[0])) + " |"
                                    body = ["| " + " | ".join(r) + " |" for r in rows[1:]]
                                    table_md = "\n".join([header, separator] + body)
                                    result["text_blocks"].append({
                                        "heading": False,
                                        "text": f"\n{table_md}\n",
                                        "slide": slide_num,
                                        "is_table": True
                                    })
                        except Exception:
                            pass

    except Exception as e:
        result["extraction_ok"] = False
        result["warnings"].append(f"PPTX extraction error: {e}")
    return result


# ── Dispatcher ─────────────────────────────────────────────────────────────────

ALLOWED_EXTENSIONS = {"docx", "pdf", "pptx"}
MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024   # 20 MB hard cap


def extract_document(file_path: str) -> dict:
    """
    Main entry point.  Detects file type and dispatches to the right extractor.
    Returns the standard extraction result dict.
    """
    ext = os.path.splitext(file_path)[1].lstrip(".").lower()
    if ext not in ALLOWED_EXTENSIONS:
        return {
            "source_file": os.path.basename(file_path),
            "document_type": ext,
            "text_blocks": [], "tables": [], "metadata": {},
            "warnings": [f"Unsupported file type: .{ext}"],
            "needs_ocr": False,
            "extraction_ok": False,
        }

    size = os.path.getsize(file_path)
    if size > MAX_FILE_SIZE_BYTES:
        return {
            "source_file": os.path.basename(file_path),
            "document_type": ext,
            "text_blocks": [], "tables": [], "metadata": {},
            "warnings": [f"File too large: {size:,} bytes (max {MAX_FILE_SIZE_BYTES:,})"],
            "needs_ocr": False,
            "extraction_ok": False,
        }

    if ext == "docx":
        return extract_docx(file_path)
    elif ext == "pdf":
        return extract_pdf(file_path)
    elif ext == "pptx":
        return extract_pptx(file_path)
