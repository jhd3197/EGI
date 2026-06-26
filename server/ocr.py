import os
import re
import json
import tempfile
from pathlib import Path
from typing import Optional
from PIL import Image, ImageEnhance, ImageFilter
from pydantic import BaseModel, Field

TESSERACT_CMD = os.environ.get("TESSERACT_CMD", "tesseract")
LLM_MODEL = os.environ.get("LLM_MODEL", "")


class ExtractedPaperReport(BaseModel):
    """Structured fields extracted from a paper report photo."""

    name: Optional[str] = Field(None, description="Full name of the person")
    given_name: Optional[str] = Field(None, description="First / given name")
    family_name: Optional[str] = Field(None, description="Last / family name")
    cedula: Optional[str] = Field(None, description="National ID / cédula number")
    status: Optional[str] = Field(
        None,
        description="One of: missing, found, safe, deceased, sighted, care",
    )
    gender: Optional[str] = Field(None, description="M, F, or null")
    age: Optional[int] = Field(None, description="Age in years")
    location: Optional[str] = Field(
        None, description="Last known location or place last seen"
    )
    last_seen_date: Optional[str] = Field(
        None, description="Approximate date the person was last seen"
    )
    clothes: Optional[str] = Field(
        None, description="Clothing or distinguishing marks"
    )
    notes: Optional[str] = Field(
        None, description="Any other relevant details, circumstances, description"
    )
    reporter_name: Optional[str] = Field(None, description="Name of who reports")
    reporter_relation: Optional[str] = Field(
        None, description="Relationship to the person"
    )
    reporter_country: Optional[str] = Field(
        None, description="Country from which the report is made"
    )
    contact: Optional[str] = Field(
        None, description="Phone, WhatsApp, or email contact"
    )


def _preprocess_image(image_path: Path) -> Path:
    """Grayscale, contrast boost, resize for better OCR. Returns path to temp file."""
    img = Image.open(image_path)
    if img.mode != "L":
        img = img.convert("L")
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.5)
    img = img.filter(ImageFilter.MedianFilter(size=3))
    # Resize if very small (Tesseract likes ~300 DPI; this is a heuristic)
    w, h = img.size
    if w < 1000:
        scale = 1000 / max(w, 1)
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    tmp = Path(tempfile.gettempdir()) / f"egi_ocr_{image_path.stem}.png"
    img.save(tmp)
    return tmp


def ocr_image(image_path: Path) -> tuple[str, float]:
    """Run OCR. Returns (text, confidence_0_to_1).

    Tries pytesseract first, then falls back to easyocr if available.
    """
    try:
        import pytesseract

        pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
        processed = _preprocess_image(image_path)
        data = pytesseract.image_to_data(
            Image.open(processed), output_type=pytesseract.Output.DICT
        )
        confidences = [int(c) for c in data["conf"] if int(c) > 0]
        avg_conf = (
            sum(confidences) / len(confidences) / 100.0 if confidences else 0.5
        )
        text = pytesseract.image_to_string(Image.open(processed)).strip()
        return text, min(avg_conf, 1.0)
    except Exception as e:
        # Fallback to easyocr if installed
        try:
            import easyocr  # type: ignore

            reader = easyocr.Reader(["es", "en"], gpu=False)
            result = reader.readtext(str(image_path), detail=0, paragraph=True)
            text = "\n".join(result)
            # easyocr does not give simple avg confidence; use neutral value
            return text, 0.6
        except Exception:
            raise RuntimeError(
                "OCR failed. Install Tesseract (https://tesseract-ocr.github.io/tessdoc/Installation.html) "
                "or install easyocr (`pip install easyocr`)."
            ) from e


def extract_with_llm(ocr_text: str) -> Optional[dict]:
    """Use Prompture to extract structured fields from OCR text.

    Returns None if no LLM model is configured.
    """
    if not LLM_MODEL:
        return None

    try:
        from prompture import extract_with_model
    except ImportError as exc:
        print("Prompture not installed; skipping LLM extraction:", exc)
        return None

    prompt = f"""Extract structured information from this emergency report OCR text.
The text may be in Spanish or English and may be messy. It describes a person
reported during a disaster (missing, found, safe, under care, sighted, etc.).

Return the fields as accurately as possible. Use null when information is missing.

OCR text:
---
{ocr_text}
---"""

    try:
        extracted = extract_with_model(ExtractedPaperReport, prompt, model_name=LLM_MODEL)
        return extracted.model_dump(exclude_none=True)
    except Exception as exc:
        print("LLM extraction failed:", exc)
        return None


def sanitize_filename(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]", "_", name)
