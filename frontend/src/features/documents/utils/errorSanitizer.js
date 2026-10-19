/**
 * Safe Error Sanitizer for Document Processing Failures
 * Sanitizes backend errors to prevent internal server paths, database details,
 * or stack traces from leaking to end users, while providing clear,
 * actionable guidance.
 */

// Patterns to scrub internal system paths and sensitive tokens
const SENSITIVE_PATTERNS = [
  /[A-Z]:\\[^:\n\r\t]+/gi,              // Windows file paths (e.g. C:\Users\...)
  /\/[\w\-.]+(?:\/[\w\-.]+)+/g,        // Unix file paths (e.g. /var/app/...)
  /ObjectId\('[a-f0-9]{24}'\)/gi,       // MongoDB ObjectIds
  /[a-f0-9]{24}/gi,                     // Raw 24-char hex IDs
  /Bearer\s+[A-Za-z0-9\-_.]+/gi,        // Auth tokens
  /api[_-]?key[:=]\s*['"]?[^'"\s]+/gi,  // API keys
];

/**
 * Strips raw system paths, database IDs, and sensitive tokens from a message.
 */
export function sanitizeRawError(rawError) {
  if (!rawError || typeof rawError !== 'string') {
    return 'An unexpected processing error occurred.';
  }

  let cleaned = rawError;
  for (const pattern of SENSITIVE_PATTERNS) {
    cleaned = cleaned.replace(pattern, '[system-path]');
  }

  // Remove python exception class names like "pymupdf.FileDataError: " or "ValueError: "
  cleaned = cleaned.replace(/^[A-Za-z0-9_.]+(?:Error|Exception):\s*/i, '');
  
  // Collapse whitespace
  cleaned = cleaned.trim().replace(/\s+/g, ' ');
  return cleaned || 'An unexpected processing error occurred.';
}

/**
 * Categorizes and formats failure details safely for display.
 * 
 * @param {Object} document - The document response or item
 * @returns {Object} Safe failure details object
 */
export function getSafeFailureDetails(document) {
  const processing = document?.processing || {};
  const rawError = processing.error || document?.error || '';
  const stage = processing.stage || document?.stage || 'unknown';
  const vectorError = processing.vector_error || '';

  const lowerError = (rawError + ' ' + vectorError).toLowerCase();

  // 1. Password Protected / Encrypted PDF
  if (
    lowerError.includes('password') ||
    lowerError.includes('encrypted') ||
    lowerError.includes('drm')
  ) {
    return {
      title: 'Protected or Encrypted Document',
      category: 'Security / Permissions',
      message: 'This document is password-protected or encrypted and cannot be parsed.',
      actionableGuidance: 'Please remove password protection or encryption from the PDF before uploading.',
      stage: 'OCR Extraction',
      isRetryable: true,
      safeExcerpt: sanitizeRawError(rawError),
    };
  }

  // 2. Corrupt or Malformed PDF
  if (
    lowerError.includes('malformed') ||
    lowerError.includes('cannot open broken file') ||
    lowerError.includes('filedataerror') ||
    lowerError.includes('corrupt') ||
    lowerError.includes('unreadable pdf') ||
    lowerError.includes('page_count == 0') ||
    lowerError.includes('zero pages')
  ) {
    return {
      title: 'Unreadable or Corrupt PDF',
      category: 'File Structure',
      message: 'The file appears to be damaged or has an unsupported PDF structure.',
      actionableGuidance: 'Try re-saving or re-exporting the PDF from your viewer (e.g. Chrome "Print to PDF") and upload again.',
      stage: 'File Ingestion',
      isRetryable: true,
      safeExcerpt: sanitizeRawError(rawError),
    };
  }

  // 3. Empty / No text detected (blank or very blurry scan)
  if (
    lowerError.includes('no text was detected') ||
    lowerError.includes('no ocr text found') ||
    lowerError.includes('empty text')
  ) {
    return {
      title: 'No Readable Text Found',
      category: 'OCR Recognition',
      message: 'The OCR scanner completed but could not detect any legible text or receipt data.',
      actionableGuidance: 'Ensure the document contains visible text or clean high-contrast receipt scans, not blank pages.',
      stage: 'OCR Extraction',
      isRetryable: true,
      safeExcerpt: 'No text was detected during OCR scanning.',
    };
  }

  // 4. Document / Storage Quota Limit
  if (
    lowerError.includes('quota') ||
    lowerError.includes('limit reached') ||
    lowerError.includes('storage limit') ||
    lowerError.includes('too large')
  ) {
    return {
      title: 'Storage or Document Quota Reached',
      category: 'Account Limit',
      message: 'You have exceeded the maximum storage allowance or document limit for your account.',
      actionableGuidance: 'Delete older or unused documents from your workspace to free up storage quota.',
      stage: 'Validation',
      isRetryable: false,
      safeExcerpt: 'User document or storage quota exceeded.',
    };
  }

  // 5. AI Extraction Failure (Gemini API rate limit or parsing error)
  if (
    stage.includes('extraction') ||
    lowerError.includes('extract_document') ||
    lowerError.includes('rate limit') ||
    lowerError.includes('gemini') ||
    lowerError.includes('json')
  ) {
    return {
      title: 'AI Extraction Notice',
      category: 'AI Analysis',
      message: 'The AI model was unable to extract structured receipt details from this document.',
      actionableGuidance: 'This may be a temporary service limit. You can re-upload or try again in a few moments.',
      stage: 'AI Field Extraction',
      isRetryable: true,
      safeExcerpt: sanitizeRawError(rawError),
    };
  }

  // 6. Vector Indexing / Chunking Failure
  if (
    stage.includes('chunk') ||
    stage.includes('vector') ||
    lowerError.includes('faiss') ||
    lowerError.includes('embedding')
  ) {
    return {
      title: 'Search Indexing Issue',
      category: 'Vector Search Index',
      message: 'The document was processed, but vector search indexing failed.',
      actionableGuidance: 'The text was saved, but semantic search may not include this document. Try re-uploading.',
      stage: 'Vector Embeddings',
      isRetryable: true,
      safeExcerpt: sanitizeRawError(vectorError || rawError),
    };
  }

  // 7. General fallback
  const cleaned = sanitizeRawError(rawError);
  return {
    title: 'Processing Encountered an Issue',
    category: 'Pipeline Processing',
    message: cleaned || 'The document pipeline encountered an issue while processing.',
    actionableGuidance: 'Please check that the file is a valid PDF under 10MB and re-upload.',
    stage: stage === 'ocr_failed' ? 'OCR Scanning' : stage === 'extraction_failed' ? 'AI Extraction' : 'Background Worker',
    isRetryable: true,
    safeExcerpt: cleaned,
  };
}
