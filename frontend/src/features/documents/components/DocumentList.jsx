import React from 'react';
import {
  FileText,
  AlertTriangle,
  Trash2,
  Eye,
  HardDrive,
  FileSearch,
} from 'lucide-react';
import { Button } from '../../../components/ui/Button';
import { DocumentStatusBadge } from './DocumentStatusBadge';
import { getStatusCategory } from '../utils/statusUtils';
import './DocumentList.css';

function formatFileSize(bytes) {
  if (!bytes || bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
}

function formatRelativeTime(dateString) {
  if (!dateString) return 'Recently';
  const date = new Date(dateString);
  const now = new Date();
  const diffInSeconds = Math.floor((now - date) / 1000);

  if (diffInSeconds < 60) return 'Just now';
  if (diffInSeconds < 3600) return `${Math.floor(diffInSeconds / 60)}m ago`;
  if (diffInSeconds < 86400) return `${Math.floor(diffInSeconds / 3600)}h ago`;
  return date.toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined,
  });
}

export const DocumentList = ({
  documents = [],
  isLoading = false,
  onViewDetails,
  onViewFailure,
  onDeleteRequest,
  activeFilter = 'all',
  searchQuery = '',
}) => {
  if (isLoading && documents.length === 0) {
    return (
      <div className="doc-list-loading">
        <div className="skeleton-row" />
        <div className="skeleton-row" />
        <div className="skeleton-row" />
      </div>
    );
  }

  if (documents.length === 0) {
    return (
      <div className="doc-list-empty-card">
        <div className="empty-icon-box">
          <FileSearch size={32} />
        </div>
        <h3 className="empty-title">
          {searchQuery
            ? `No documents matching "${searchQuery}"`
            : activeFilter !== 'all'
            ? `No ${activeFilter} documents found`
            : 'No documents uploaded yet'}
        </h3>
        <p className="empty-description">
          {searchQuery
            ? 'Try adjusting your search query or switching to the "All Documents" tab.'
            : activeFilter !== 'all'
            ? `There are currently no documents categorized as "${activeFilter}".`
            : 'Upload a PDF receipt or invoice above to extract text, line items, and enable AI search.'}
        </p>
      </div>
    );
  }

  return (
    <div className="doc-list-container">
      <div className="doc-table-wrapper">
        <table className="doc-table" aria-label="Documents List">
          <thead>
            <tr>
              <th scope="col" className="col-name">Document</th>
              <th scope="col" className="col-status">Status &amp; Pipeline</th>
              <th scope="col" className="col-size">Size</th>
              <th scope="col" className="col-date">Uploaded</th>
              <th scope="col" className="col-actions text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {documents.map((doc) => {
              const category = getStatusCategory(doc.status);
              const isFailed = category === 'failed';
              const isProcessing = category === 'processing';

              return (
                <tr
                  key={doc.id}
                  className={`doc-row ${isFailed ? 'row-failed' : ''} ${isProcessing ? 'row-processing' : ''}`}
                >
                  {/* Name & Type */}
                  <td className="cell-doc-info">
                    <div className="doc-item-title-box">
                      <div className={`doc-icon-badge ${doc.file_type || 'pdf'}`}>
                        <FileText size={18} />
                      </div>
                      <div className="doc-name-col">
                        <span className="doc-filename" title={doc.filename}>
                          {doc.filename}
                        </span>
                        <span className="doc-type-pill">
                          {doc.file_type ? doc.file_type.toUpperCase() : 'PDF'}
                        </span>
                      </div>
                    </div>
                  </td>

                  {/* Status */}
                  <td className="cell-status">
                    <DocumentStatusBadge
                      status={doc.status}
                      stage={doc.processing?.stage}
                      vectorStatus={doc.vector_status}
                      size="sm"
                    />
                  </td>

                  {/* Size */}
                  <td className="cell-size">
                    <span className="size-badge">
                      <HardDrive size={12} className="inline-icon" />
                      {formatFileSize(doc.file_size)}
                    </span>
                  </td>

                  {/* Date */}
                  <td className="cell-date">
                    <div className="date-wrapper">
                      <span className="relative-date">
                        {formatRelativeTime(doc.uploaded_at || doc.processing?.uploaded_at)}
                      </span>
                      <span className="absolute-date">
                        {new Date(doc.uploaded_at || doc.processing?.uploaded_at).toLocaleTimeString([], {
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </span>
                    </div>
                  </td>

                  {/* Actions */}
                  <td className="cell-actions text-right">
                    <div className="actions-cluster">
                      {/* For Failed documents: Show prominent Safe Failure Details button */}
                      {isFailed && (
                        <Button
                          variant="danger"
                          size="sm"
                          icon={<AlertTriangle size={14} />}
                          onClick={() => onViewFailure(doc)}
                          title="View safe diagnostic details"
                        >
                          Failure Details
                        </Button>
                      )}

                      {/* For Completed / Processing: View details button */}
                      {!isFailed && (
                        <Button
                          variant="ghost"
                          size="sm"
                          icon={<Eye size={14} />}
                          onClick={() => onViewDetails(doc)}
                          title="View extracted data and OCR"
                        >
                          View Details
                        </Button>
                      )}

                      {/* Delete button */}
                      <button
                        type="button"
                        className="action-icon-btn delete"
                        onClick={() => onDeleteRequest(doc)}
                        title="Delete document"
                        aria-label={`Delete ${doc.filename}`}
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};
