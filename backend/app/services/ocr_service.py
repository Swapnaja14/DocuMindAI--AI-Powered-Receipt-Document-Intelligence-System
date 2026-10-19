import io
import os
from pathlib import Path
from typing import Any, Dict

import pymupdf as fitz
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


def preprocess_image(image: Image.Image) -> Image.Image:
    """Preprocess image for optimal receipt and invoice OCR recognition."""
    # Convert RGBA/P images with alpha/transparency to clean RGB with white background
    if image.mode in ("RGBA", "LA", "P"):
        background = Image.new("RGB", image.size, (255, 255, 255))
        if image.mode == "P":
            image = image.convert("RGBA")
        background.paste(
            image,
            mask=image.split()[-1] if "A" in image.getbands() else None,
        )
        image = background
    elif image.mode != "RGB":
        image = image.convert("RGB")

    # If image resolution is low (e.g., width < 1200), upscale with Lanczos for clearer character shapes
    w, h = image.size
    if w < 1200:
        factor = 1400 / w
        image = image.resize(
            (int(w * factor), int(h * factor)),
            Image.Resampling.LANCZOS,
        )

    return image


def ocr_image(image: Image.Image) -> str:
    """Run OCR on a PIL image with layout optimization and return recognized text."""
    try:
        processed_img = preprocess_image(image)

        # Try PSM 6 (single uniform block of text, ideal for tabular receipts)
        text_psm6 = pytesseract.image_to_string(
            processed_img,
            config="--psm 6 --oem 3",
        ).strip()

        # Try PSM 3 (fully automatic page segmentation)
        text_psm3 = pytesseract.image_to_string(
            processed_img,
            config="--psm 3 --oem 3",
        ).strip()

        # Choose whichever captured more rich information
        selected_text = text_psm6 if len(text_psm6) >= len(text_psm3) else text_psm3
        return selected_text

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
            page_text = ""
            direct_text = page.get_text().strip()

            try:
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
            except Exception as ocr_exc:
                if direct_text:
                    page_text = direct_text
                else:
                    raise ocr_exc

            # If OCR yielded little or no text but digital PDF text exists, use digital text
            if direct_text and len(direct_text) > len(page_text):
                page_text = direct_text

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