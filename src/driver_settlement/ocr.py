from __future__ import annotations

import io
import os
import sys
from pathlib import Path

import fitz
import pytesseract
from PIL import Image


class OCRUnavailable(RuntimeError):
    pass


def _configure_tesseract() -> None:
    """Use bundled Tesseract inside a PyInstaller executable when present."""
    candidates: list[Path] = []
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        candidates.append(Path(bundle_root) / "tesseract" / "tesseract.exe")
    if os.name == "nt":
        candidates.extend(
            [
                Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Tesseract-OCR" / "tesseract.exe",
                Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Tesseract-OCR" / "tesseract.exe",
            ]
        )
    for candidate in candidates:
        if candidate.exists():
            pytesseract.pytesseract.tesseract_cmd = str(candidate)
            tessdata = candidate.parent / "tessdata"
            if tessdata.exists():
                os.environ.setdefault("TESSDATA_PREFIX", str(tessdata))
            return


_configure_tesseract()


def _ocr_image(image: Image.Image) -> str:
    try:
        return pytesseract.image_to_string(image.convert("RGB"), config="--psm 6").strip()
    except pytesseract.TesseractNotFoundError as exc:
        raise OCRUnavailable(
            "Tesseract OCR is unavailable. Use the packaged Windows executable or install Tesseract OCR."
        ) from exc


def extract_text(path: str | Path) -> str:
    """Extract text from an image or PDF, using OCR when PDF text is absent."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        chunks: list[str] = []
        with fitz.open(path) as pdf:
            for page in pdf:
                text = page.get_text("text").strip()
                if len(text) >= 30:
                    chunks.append(text)
                    continue
                matrix = fitz.Matrix(2.2, 2.2)
                pix = page.get_pixmap(matrix=matrix, alpha=False)
                image = Image.open(io.BytesIO(pix.tobytes("png")))
                chunks.append(_ocr_image(image))
        return "\n\n".join(chunks).strip()

    if suffix in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}:
        with Image.open(path) as image:
            return _ocr_image(image)

    if suffix in {".txt", ".md"}:
        return path.read_text(encoding="utf-8")

    raise ValueError(f"Unsupported document format: {suffix or '<none>'}")
