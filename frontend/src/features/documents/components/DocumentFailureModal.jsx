import React, { useEffect } from 'react';
import {
  AlertTriangle,
  X,
  FileText,
  ShieldCheck,
  HelpCircle,
  Trash2,
  UploadCloud,
  Layers,
} from 'lucide-react';
import { Button } from '../../../components/ui/Button';
import { getSafeFailureDetails } from '../utils/errorSanitizer';
import './DocumentFailureModal.css';

export const DocumentFailureModal = ({
  document,
  isOpen,
  onClose,
  onDeleteRequest,
  onReuploadRequest,
}) => {
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen || !document) return null;

  const failureDetails = getSafeFailureDetails(document);

  return (
    <div
      className="modal-overlay animate-fade-in"
      onClick={onClose}
      role="presentation"
    >
      <div
        className="modal-container failure-modal-card animate-slide-up"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="failure-dialog-title"
      >
        {/* Modal Header */}
        <div className="modal-header failure-header">
          <div className="failure-icon-bubble">
            <AlertTriangle size={24} />
          </div>
          <div className="failure-header-text">
            <span className="failure-category-chip">{failureDetails.category}</span>
            <h2 id="failure-dialog-title" className="modal-title">
              {failureDetails.title}
            </h2>
          </div>
          <button
            className="modal-close-btn"
            onClick={onClose}
            aria-label="Close failure details modal"
          >
            <X size={18} />
          </button>
        </div>

        {/* Modal Body */}
        <div className="modal-body failure-modal-body">
          {/* Document Summary Pill */}
          <div className="failure-doc-meta">
            <div className="meta-row">
              <FileText size={16} className="meta-icon" />
              <span className="doc-name">{document.filename}</span>
            </div>
            <div className="meta-sub">
              <span>Size: {(document.file_size / (1024 * 1024)).toFixed(2)} MB</span>
              <span>•</span>
              <span>
                Uploaded: {new Date(document.uploaded_at || document.processing?.uploaded_at).toLocaleString()}
              </span>
            </div>
          </div>

          {/* User Explanation Card */}
          <div className="failure-explanation-box">
            <p className="failure-primary-message">{failureDetails.message}</p>
          </div>

          {/* Actionable Guidance */}
          <div className="failure-guidance-card">
            <div className="guidance-header">
              <HelpCircle size={16} className="guidance-icon" />
              <h4>Recommended Action:</h4>
            </div>
            <p className="guidance-text">{failureDetails.actionableGuidance}</p>
          </div>

          {/* Technical Stage Info (Safe & Sanitized) */}
          <div className="failure-technical-card">
            <div className="technical-item">
              <span className="tech-label">
                <Layers size={13} className="inline-icon" /> Failed Pipeline Stage:
              </span>
              <span className="tech-value">{failureDetails.stage}</span>
            </div>

            {failureDetails.safeExcerpt && (
              <div className="safe-excerpt-section">
                <div className="safe-notice">
                  <ShieldCheck size={13} className="shield-icon" />
                  <span>Sanitized Error Excerpt (Protected):</span>
                </div>
                <pre className="safe-excerpt-box">{failureDetails.safeExcerpt}</pre>
              </div>
            )}
          </div>
        </div>

        {/* Modal Footer */}
        <div className="modal-footer failure-modal-footer">
          <Button
            variant="danger"
            size="sm"
            icon={<Trash2 size={15} />}
            onClick={() => {
              onClose();
              onDeleteRequest(document);
            }}
          >
            Delete Document
          </Button>

          <div className="footer-right-actions">
            <Button variant="secondary" size="sm" onClick={onClose}>
              Dismiss
            </Button>
            {failureDetails.isRetryable && onReuploadRequest && (
              <Button
                variant="primary"
                size="sm"
                icon={<UploadCloud size={15} />}
                onClick={() => {
                  onClose();
                  onReuploadRequest();
                }}
              >
                Re-upload New File
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
