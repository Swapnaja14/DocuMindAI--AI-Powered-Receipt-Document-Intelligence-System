/**
 * Helper utilities for document statuses and stages
 */

/**
 * Returns a normalized status bucket: 'uploaded' | 'processing' | 'completed' | 'failed'
 */
export function getStatusCategory(status) {
  if (!status) return 'uploaded';
  const s = String(status).toUpperCase();

  if (s === 'FAILED') return 'failed';
  if (s === 'COMPLETED' || s === 'VALIDATED') return 'completed';
  if (
    s === 'PROCESSING' ||
    s === 'OCR_COMPLETED' ||
    s === 'EXTRACTING' ||
    s === 'EXTRACTION_COMPLETED' ||
    s === 'CHUNKING_COMPLETED' ||
    s === 'EMBEDDING_COMPLETED'
  ) {
    return 'processing';
  }
  return 'uploaded';
}

/**
 * Returns user-friendly status label and stage detail
 */
export function getStatusLabel(status, stage) {
  if (!status) return 'Uploaded';
  const s = String(status).toUpperCase();

  switch (s) {
    case 'UPLOADED':
      return 'In Queue';
    case 'PROCESSING':
      return stage === 'ocr_processing' ? 'Running OCR...' : 'Processing...';
    case 'OCR_COMPLETED':
      return 'OCR Ready';
    case 'EXTRACTING':
    case 'EXTRACTION_COMPLETED':
      return 'AI Extracting...';
    case 'CHUNKING_COMPLETED':
    case 'EMBEDDING_COMPLETED':
      return 'Indexing Vectors...';
    case 'COMPLETED':
    case 'VALIDATED':
      return 'Completed';
    case 'FAILED':
      return 'Failed';
    default:
      return status;
  }
}
