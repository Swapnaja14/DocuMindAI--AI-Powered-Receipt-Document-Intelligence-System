import React, { useState, useRef } from 'react';
import {
  UploadCloud,
  FileText,
  CheckCircle2,
  AlertCircle,
  X,
  Loader2,
} from 'lucide-react';
import { Button } from '../../../components/ui/Button';
import { documentsApi } from '../../../api/documents';
import './DocumentUploader.css';

const MAX_SIZE_BYTES = 10 * 1024 * 1024; // 10 MB

export const DocumentUploader = ({ onUploadSuccess }) => {
  const [isDragging, setIsDragging] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [transferredBytes, setTransferredBytes] = useState({ loaded: 0, total: 0 });
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState(null);
  const [uploadSuccessDoc, setUploadSuccessDoc] = useState(null);
  const fileInputRef = useRef(null);

  const validateFile = (file) => {
    if (!file) return 'No file selected.';

    const validTypes = ['application/pdf', 'image/png', 'image/jpeg', 'image/jpg'];
    const isPdfByName = file.name.toLowerCase().endsWith('.pdf');
    const isImageByName = /\.(png|jpe?g)$/i.test(file.name);

    if (!validTypes.includes(file.type) && !isPdfByName && !isImageByName) {
      return 'Unsupported file type. Please upload a PDF receipt or invoice (or PNG/JPG).';
    }

    if (file.size === 0) {
      return 'The selected file is empty (0 bytes).';
    }

    if (file.size > MAX_SIZE_BYTES) {
      return `File exceeds the 10 MB limit (${(file.size / (1024 * 1024)).toFixed(1)} MB).`;
    }

    return null;
  };

  const handleFileSelection = (file) => {
    setUploadError(null);
    setUploadSuccessDoc(null);
    setUploadProgress(0);

    const error = validateFile(file);
    if (error) {
      setUploadError(error);
      setSelectedFile(null);
      return;
    }

    setSelectedFile(file);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (!isDragging) setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    const files = e.dataTransfer?.files;
    if (files && files.length > 0) {
      handleFileSelection(files[0]);
    }
  };

  const handleStartUpload = async () => {
    if (!selectedFile || isUploading) return;

    setIsUploading(true);
    setUploadProgress(0);
    setUploadError(null);
    setTransferredBytes({ loaded: 0, total: selectedFile.size });

    try {
      const result = await documentsApi.uploadDocument(selectedFile, (progress) => {
        setUploadProgress(progress.percent);
        setTransferredBytes({ loaded: progress.loaded, total: progress.total });
      });

      setUploadSuccessDoc(result);
      setSelectedFile(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }

      if (onUploadSuccess) {
        onUploadSuccess(result);
      }
    } catch (err) {
      setUploadError(err.message || 'Failed to upload document.');
    } finally {
      setIsUploading(false);
    }
  };

  const handleReset = () => {
    setSelectedFile(null);
    setUploadProgress(0);
    setUploadError(null);
    setUploadSuccessDoc(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  return (
    <div className="document-uploader-card animate-fade-in">
      {/* Hidden native input */}
      <input
        type="file"
        ref={fileInputRef}
        onChange={(e) => {
          if (e.target.files && e.target.files.length > 0) {
            handleFileSelection(e.target.files[0]);
          }
        }}
        accept=".pdf,application/pdf,image/png,image/jpeg"
        className="uploader-native-input"
        id="pdf-file-upload-input"
      />

      {/* Upload Zone */}
      {!selectedFile && !isUploading && (
        <div
          className={`dropzone-area ${isDragging ? 'dropzone-active' : ''}`}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              fileInputRef.current?.click();
            }
          }}
          aria-label="Upload PDF Document"
        >
          <div className="dropzone-glow" />
          <div className="dropzone-content">
            <div className="uploader-icon-ring">
              <UploadCloud size={32} className="upload-icon" />
            </div>

            <div className="dropzone-text">
              <h3 className="dropzone-title">
                Drag and drop your PDF document here
              </h3>
              <p className="dropzone-subtitle">
                or <span className="browse-link">browse files</span> from your computer
              </p>
            </div>

            <div className="format-badges-row">
              <span className="badge-format pdf">PDF Preferred</span>
              <span className="badge-format">PNG / JPG</span>
              <span className="badge-format max-size">Max 10 MB</span>
            </div>
          </div>
        </div>
      )}

      {/* Selected File & Upload In-Flight State */}
      {selectedFile && (
        <div className="selected-file-container animate-fade-in">
          <div className="file-preview-card">
            <div className="file-icon-box">
              <FileText size={28} />
            </div>

            <div className="file-info-col">
              <span className="file-name">{selectedFile.name}</span>
              <span className="file-size-label">
                {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB • PDF Document
              </span>
            </div>

            {!isUploading && (
              <button
                type="button"
                className="remove-file-btn"
                onClick={handleReset}
                title="Choose different file"
                aria-label="Remove selected file"
              >
                <X size={18} />
              </button>
            )}
          </div>

          {/* Upload Progress Bar */}
          {isUploading && (
            <div className="upload-progress-box animate-fade-in">
              <div className="progress-labels">
                <span className="progress-status-text">
                  <Loader2 size={14} className="spinning inline-icon" />
                  {uploadProgress < 100
                    ? `Uploading bytes... ${uploadProgress}%`
                    : 'Dispatching to AI pipeline queue...'}
                </span>
                <span className="progress-bytes-text">
                  {(transferredBytes.loaded / (1024 * 1024)).toFixed(1)} /{' '}
                  {(transferredBytes.total / (1024 * 1024)).toFixed(1)} MB
                </span>
              </div>

              <div className="progress-bar-track">
                <div
                  className="progress-bar-fill"
                  style={{ width: `${uploadProgress}%` }}
                />
              </div>
            </div>
          )}

          {/* Action Row */}
          {!isUploading && (
            <div className="file-action-buttons">
              <Button
                variant="secondary"
                size="sm"
                onClick={handleReset}
              >
                Cancel
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={handleStartUpload}
                icon={<UploadCloud size={16} />}
              >
                Upload &amp; Process Document
              </Button>
            </div>
          )}
        </div>
      )}

      {/* Error Callout */}
      {uploadError && (
        <div className="uploader-message error animate-shake" role="alert">
          <AlertCircle size={18} className="message-icon" />
          <div className="message-content">
            <span className="message-title">Upload Failed</span>
            <p className="message-desc">{uploadError}</p>
          </div>
          <button
            className="message-dismiss-btn"
            onClick={() => setUploadError(null)}
            aria-label="Dismiss error"
          >
            <X size={15} />
          </button>
        </div>
      )}

      {/* Upload Success Callout */}
      {uploadSuccessDoc && (
        <div className="uploader-message success animate-fade-in" role="status">
          <CheckCircle2 size={18} className="message-icon" />
          <div className="message-content">
            <span className="message-title">Upload Successful!</span>
            <p className="message-desc">
              <strong>{uploadSuccessDoc.filename}</strong> has been uploaded and queued for OCR, extraction, and vector indexing.
            </p>
          </div>
          <button
            className="message-dismiss-btn"
            onClick={() => setUploadSuccessDoc(null)}
            aria-label="Dismiss success message"
          >
            <X size={15} />
          </button>
        </div>
      )}
    </div>
  );
};
