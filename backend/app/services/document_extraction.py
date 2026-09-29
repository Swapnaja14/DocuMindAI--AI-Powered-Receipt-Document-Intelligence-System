from app.services.gemini_extractor import GeminiExtractor
from app.services.extraction_validator import validate_extraction

def extract_document_data(ocr_text: str):
    extractor = GeminiExtractor()
    extracted_data = extractor.extract(ocr_text)
    validation = validate_extraction(extracted_data)

    return {
        "data": extracted_data.model_dump(),
        "validation": validation.to_dict(),
    }