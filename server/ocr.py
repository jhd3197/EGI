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


def _extraction_prompt(ocr_text: str) -> str:
    return f"""Extract structured information from this emergency report OCR text.
The text may be in Spanish or English and may be messy. It describes a person
reported during a disaster (missing, found, safe, under care, sighted, etc.).

Return the fields as accurately as possible. Use null when information is missing.

OCR text:
---
{ocr_text}
---"""


def extract_with_llm(ocr_text: str) -> Optional[dict]:
    """Extract structured fields from OCR text.

    Order of preference:
      1. If ``LLM_MODEL`` is set, use Prompture against that provider/model.
      2. Otherwise fall back to a local-first ``BaseExtractor`` (Ollama by
         default, no API key) when one is available.
      3. If nothing is configured/reachable, return None and let the record keep
         raw OCR text only (extraction is always optional).
    """
    prompt = _extraction_prompt(ocr_text)

    if LLM_MODEL:
        try:
            from prompture import extract_with_model
        except ImportError as exc:
            print("Prompture not installed; skipping LLM extraction:", exc)
            return None
        try:
            extracted = extract_with_model(ExtractedPaperReport, prompt, model_name=LLM_MODEL)
            return extracted.model_dump(exclude_none=True)
        except Exception as exc:
            print("LLM extraction failed:", exc)
            return None

    # Local-first fallback (Ollama via BaseExtractor). Degrades to None silently
    # so the OCR draft is still created with raw text for manual completion.
    try:
        from ai import BaseExtractor
    except Exception:
        return None
    extractor = BaseExtractor()
    if not extractor.available():
        return None
    data = extractor.extract(prompt)
    if not isinstance(data, dict):
        return None
    try:
        known = {k: v for k, v in data.items() if k in ExtractedPaperReport.model_fields}
        return ExtractedPaperReport(**known).model_dump(exclude_none=True)
    except Exception:
        return data


def strip_exif(image_path: Path) -> bool:
    """Re-save an image without EXIF metadata (drops GPS, camera, timestamps).

    Privacy (plan-07 §7.3): a crisis photo's EXIF can leak the exact location and
    time it was taken. We re-encode pixel data into a fresh image so no metadata
    survives. Best-effort: non-image uploads (or unreadable files) are left as-is
    and the function returns False — it never raises, so it can't break an upload.
    """
    try:
        with Image.open(image_path) as img:
            data = list(img.getdata())
            clean = Image.new(img.mode, img.size)
            clean.putdata(data)
            clean.save(image_path)
        return True
    except Exception:
        return False


def _ratio_to_float(value) -> float:
    """Coerce an EXIF rational (PIL IFDRational / tuple / number) to float."""
    try:
        # IFDRational and plain numbers both support float(); a (num, den) tuple
        # is handled explicitly.
        if isinstance(value, tuple) and len(value) == 2:
            return float(value[0]) / float(value[1])
        return float(value)
    except Exception:
        return 0.0


def _dms_to_decimal(dms, ref) -> Optional[float]:
    """Convert an EXIF (degrees, minutes, seconds) triple + N/S/E/W ref to a
    signed decimal degree. Returns None on any malformed input."""
    try:
        deg = _ratio_to_float(dms[0])
        minutes = _ratio_to_float(dms[1])
        seconds = _ratio_to_float(dms[2])
        decimal = deg + minutes / 60.0 + seconds / 3600.0
        if str(ref).upper() in ("S", "W"):
            decimal = -decimal
        return decimal
    except Exception:
        return None


def extract_gps(image_path: Path) -> Optional[tuple[float, float]]:
    """Read EXIF GPS tags and return ``(lat, lon)`` in signed decimal degrees.

    Privacy note: this is called *before* the image is EXIF-stripped, so the
    coordinates can be lifted into structured ``lat``/``lon`` columns while the
    stored file itself carries no metadata. Best-effort: any missing tag or
    malformed value yields ``None`` and this never raises.
    """
    try:
        with Image.open(image_path) as img:
            exif = img.getexif()
            # 0x8825 = GPSInfo IFD pointer.
            gps = exif.get_ifd(0x8825)
        if not gps:
            return None
        # GPS IFD tags: 1=LatRef 2=Lat 3=LonRef 4=Lon.
        lat = _dms_to_decimal(gps.get(2), gps.get(1))
        lon = _dms_to_decimal(gps.get(4), gps.get(3))
        if lat is None or lon is None:
            return None
        return (lat, lon)
    except Exception:
        return None


def extract_taken_at(image_path: Path) -> Optional[str]:
    """Read the EXIF capture timestamp (DateTimeOriginal, tag 0x9003).

    Returns an ISO-ish string (EXIF stores ``YYYY:MM:DD HH:MM:SS``; we rewrite
    the date separators to dashes) or ``None`` when absent/unreadable. Like
    ``extract_gps`` this is best-effort and never raises.
    """
    try:
        with Image.open(image_path) as img:
            exif = img.getexif()
            # DateTimeOriginal lives in the Exif sub-IFD (0x8769); fall back to
            # the top-level DateTime (0x0132) when the sub-IFD is absent.
            raw = None
            try:
                sub = exif.get_ifd(0x8769)
                raw = sub.get(0x9003)
            except Exception:
                raw = None
            if not raw:
                raw = exif.get(0x0132)
        if not raw:
            return None
        raw = str(raw).strip()
        # EXIF date part uses colons (YYYY:MM:DD HH:MM:SS); rewrite only the date
        # separators to dashes so the result is closer to ISO-8601.
        if len(raw) >= 10 and raw[4] == ":" and raw[7] == ":":
            raw = raw[:4] + "-" + raw[5:7] + "-" + raw[8:]
        return raw or None
    except Exception:
        return None


def sanitize_filename(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]", "_", name)
