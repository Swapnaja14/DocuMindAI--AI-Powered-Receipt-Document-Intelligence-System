import React from 'react';
import { AlertTriangle, UploadCloud, Search, Sliders } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import './InsufficientEvidenceBanner.css';

export const InsufficientEvidenceBanner = ({ onOpenSettings }) => {
  const navigate = useNavigate();

  return (
    <div className="insufficient-evidence-banner animate-fade-in" role="status">
      <div className="insufficient-header">
        <div className="alert-icon-ring">
          <AlertTriangle size={18} className="alert-icon" />
        </div>
        <div className="insufficient-text-header">
          <span className="banner-title">Insufficient Document Evidence</span>
          <p className="banner-subtitle">
            The AI engine could not ground a reliable answer in your current document index.
          </p>
        </div>
      </div>

      <div className="insufficient-suggestions-box">
        <span className="suggestions-label">Suggestions to improve your answer:</span>
        <ul className="suggestions-list">
          <li>
            <Search size={14} className="suggestion-bullet-icon" />
            <span>Try rephrasing with specific keywords like vendor names, item names, or dates.</span>
          </li>
          <li>
            <UploadCloud size={14} className="suggestion-bullet-icon" />
            <span>Ensure the relevant receipts or documents are uploaded and marked as <strong>PROCESSED</strong>.</span>
          </li>
          <li>
            <Sliders size={14} className="suggestion-bullet-icon" />
            <span>Consider increasing the <strong>Top-K chunks</strong> retrieval depth in chat settings.</span>
          </li>
        </ul>
      </div>

      <div className="insufficient-actions-row">
        <button
          type="button"
          className="btn-action-outline"
          onClick={() => navigate('/documents')}
        >
          <UploadCloud size={14} />
          <span>Upload More Documents</span>
        </button>
        {onOpenSettings && (
          <button
            type="button"
            className="btn-action-ghost"
            onClick={onOpenSettings}
          >
            <Sliders size={14} />
            <span>Adjust Retrieval Settings</span>
          </button>
        )}
      </div>
    </div>
  );
};
