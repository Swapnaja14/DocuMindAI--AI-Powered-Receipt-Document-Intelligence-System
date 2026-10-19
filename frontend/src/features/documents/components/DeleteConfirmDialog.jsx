import React, { useEffect } from 'react';
import { AlertTriangle, Trash2, X, FileText } from 'lucide-react';
import { Button } from '../../../components/ui/Button';
import './DeleteConfirmDialog.css';

export const DeleteConfirmDialog = ({
  isOpen,
  document,
  isDeleting,
  onClose,
  onConfirm,
}) => {
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && isOpen && !isDeleting) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, isDeleting, onClose]);

  if (!isOpen || !document) return null;

  return (
    <div
      className="modal-overlay animate-fade-in"
      onClick={() => {
        if (!isDeleting) onClose();
      }}
      role="presentation"
    >
      <div
        className="modal-container delete-dialog-card animate-slide-up"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="delete-dialog-title"
        aria-describedby="delete-dialog-desc"
      >
        <div className="modal-header delete-dialog-header">
          <div className="delete-icon-bubble">
            <Trash2 size={22} />
          </div>
          <div className="delete-header-info">
            <span className="danger-chip">Permanent Action</span>
            <h2 id="delete-dialog-title" className="modal-title">
              Delete Document?
            </h2>
          </div>
          <button
            className="modal-close-btn"
            onClick={onClose}
            disabled={isDeleting}
            aria-label="Cancel and close dialog"
          >
            <X size={18} />
          </button>
        </div>

        <div className="modal-body delete-dialog-body">
          <div className="delete-target-preview">
            <FileText size={18} className="preview-icon" />
            <div className="preview-details">
              <span className="target-name">{document.filename}</span>
              <span className="target-meta">
                {(document.file_size / (1024 * 1024)).toFixed(2)} MB •{' '}
                {document.file_type?.toUpperCase()}
              </span>
            </div>
          </div>

          <div className="delete-warning-callout" id="delete-dialog-desc">
            <AlertTriangle size={18} className="callout-icon" />
            <p>
              This action cannot be undone. The stored document, OCR extracted text, structured receipt data, and vector search embeddings will be <strong>permanently removed</strong> from your tenant storage.
            </p>
          </div>
        </div>

        <div className="modal-footer delete-dialog-footer">
          <Button
            variant="secondary"
            size="sm"
            onClick={onClose}
            disabled={isDeleting}
          >
            Cancel
          </Button>

          <Button
            variant="danger"
            size="sm"
            onClick={onConfirm}
            isLoading={isDeleting}
            icon={<Trash2 size={16} />}
          >
            Permanently Delete
          </Button>
        </div>
      </div>
    </div>
  );
};
