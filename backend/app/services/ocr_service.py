import io
import os
from pathlib import Path
from typing import Any, Dict

import fitz
import pytesseract
from PIL import Image

# Windows Fallback
# If tesseract is already in PATH, this is not required
TESSERACT_PATH = os.getenv("TESSERACT_PATH", r"C:\Program Files\Tesseract-OCR\tesseract.exe")

if os.path.exists(TESSERACT_PATH):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

SUPPORTED_IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".bmp",
    ".tiff",
    ".webp",
}

SUPPORTED_PDF_EXTENSIONS = {
    ".pdf",
}


class OCRProcessingError(Exception):
    """Raised when OCR processing fails."""
    pass


def validate_file(file_path: str) -> str:
    """Validate that the uploaded document has a supported extension and exists."""
    path = Path(file_path)
    if not path.exists():
        raise OCRProcessingError(f"File does not exist: {file_path}")

    extension = path.suffix.lower()

    if extension not in (
        SUPPORTED_IMAGE_EXTENSIONS | SUPPORTED_PDF_EXTENSIONS
    ):
        raise OCRProcessingError(
            f"Unsupported file type: {extension}"
        )

    return extension


def ocr_image(image: Image.Image) -> str:
    """Run OCR on a PIL image and return stripped recognized text."""
    try:
        text = pytesseract.image_to_string(image)
        return text.strip()

    except Exception as exc:
        raise OCRProcessingError(
            f"Image OCR failed: {exc}"
        ) from exc


def ocr_pdf(file_path: str) -> Dict[str, Any]:
    """Convert each PDF page to an image and perform OCR, returning raw_text and page_count."""
    extracted_text = []

    try:
        pdf = fitz.open(file_path)
        page_count = len(pdf)

        for page_number, page in enumerate(pdf):
            # Render PDF page at approximately 300 DPI
            matrix = fitz.Matrix(300 / 72, 300 / 72)

            pixmap = page.get_pixmap(
                matrix=matrix,
                alpha=False,
            )

            image_bytes = pixmap.tobytes("png")

            image = Image.open(
                io.BytesIO(image_bytes)
            )

            page_text = ocr_image(image)

            if page_text:
                extracted_text.append(
                    f"--- Page {page_number + 1} ---\n"
                    f"{page_text}"
                )

        pdf.close()
        raw_text = "\n\n".join(extracted_text).strip()

        return {
            "raw_text": raw_text,
            "page_count": page_count,
        }

    except OCRProcessingError:
        raise

    except Exception as exc:
        raise OCRProcessingError(
            f"PDF OCR failed: {exc}"
        ) from exc


def ocr_document(file_path: str) -> Dict[str, Any]:
    """
    Main OCR entry point.
    Supported: JPG, JPEG, PNG, BMP, TIFF, WEBP, PDF

    Returns:
        {
            "raw_text": "...",
            "page_count": int
        }
    """
    extension = validate_file(file_path)

    try:
        if extension in SUPPORTED_PDF_EXTENSIONS:
            return ocr_pdf(file_path)

        with Image.open(file_path) as image:
            raw_text = ocr_image(image)

        return {
            "raw_text": raw_text,
            "page_count": 1,
        }

    except OCRProcessingError:
        raise

    except Exception as exc:
        raise OCRProcessingError(
            f"Document OCR failed: {exc}"
        ) from exc