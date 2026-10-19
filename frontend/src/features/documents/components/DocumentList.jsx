import React from 'react';
import {
  FileText,
  AlertTriangle,
  Trash2,
  Eye,
  HardDrive,
  FileSearch,
  UploadCloud,
  RotateCcw,
  Clock,
} from 'lucide-react';
import { Button } from '../../../components/ui/Button';
import { DocumentStatusBadge } from './DocumentStatusBadge';
import { LoadingState } from '../../../components/ui/LoadingState';
import { EmptyState } from '../../../components/ui/EmptyState';
import { getStatusCategory } from '../utils/statusUtils';
import {
  useLiveDeviceTime,
  formatDynamicRelativeTime,
  formatDeviceTime,
  formatDeviceDate,
  formatDeviceDateTime,
  parseToDeviceDate,
} from '../utils/dateUtils';
import './DocumentList.css';

function formatFileSize(bytes) {
  if (!bytes || bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
}

export const DocumentList = ({
  documents = [],
  isLoading = false,
  onViewDetails,
  onViewFailure,
  onDeleteRequest,
  activeFilter = 'all',
  searchQuery = '',
  onClearSearch,
  onResetFilter,
  onUploadClick,
}) => {
  // Drives dynamic real-time updates every 1000ms synchronized with the device's clock
  const currentDeviceTime = useLiveDeviceTime(1000);

  if (isLoading && documents.length === 0) {
    return (
      <div className="doc-list-loading" role="status" aria-live="polite">
        <LoadingState
          variant="skeleton-table"
          rows={4}
          message="Retrieving tenant document records..."
        />
      </div>
    );
  }

  if (documents.length === 0) {
    if (searchQuery) {
      return (
        <EmptyState
          icon={<FileSearch size={36} />}
          title={`No documents matching "${searchQuery}"`}
          description="We couldn't find any documents matching your keyword search. Try searching by a different term or clear your search query."
          actionLabel="Clear Search"
          onAction={onClearSearch}
          actionIcon={<RotateCcw size={15} />}
        />
      );
    }

    if (activeFilter !== 'all') {
      return (
        <EmptyState
          icon={<FileSearch size={36} />}
          title={`No ${activeFilter} documents found`}
          description={`There are currently no documents categorized as "${activeFilter}".`}
          actionLabel="Show All Documents"
          onAction={onResetFilter}
          actionIcon={<RotateCcw size={15} />}
        />
      );
    }

    return (
      <EmptyState
        icon={<UploadCloud size={38} />}
        title="No documents uploaded yet"
        description="Upload a receipt or invoice PDF above to run OCR extraction, inspect line items, and enable grounded AI search."
        actionLabel="Upload Receipt PDF"
        onAction={onUploadClick}
        actionIcon={<UploadCloud size={16} />}
      />
    );
  }

  return (
    <div className="doc-list-container">
      <div
        className="doc-table-wrapper"
        tabIndex={0}
        aria-label="Documents data table, scrollable horizontally"
      >
        <table className="doc-table" aria-label="Documents List">
          <thead>
            <tr>
              <th scope="col" className="col-name">Document</th>
              <th scope="col" className="col-status">Status &amp; Pipeline</th>
              <th scope="col" className="col-size">Size</th>
              <th scope="col" className="col-date">Uploaded (Device Time)</th>
              <th scope="col" className="col-actions text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {documents.map((doc) => {
              const category = getStatusCategory(doc.status);
              const isFailed = category === 'failed';
              const isProcessing = category === 'processing';
              const isUploaded = category === 'uploaded';
              const uploadTimestamp = doc.uploaded_at || doc.processing?.uploaded_at;

              // Synchronized with device clock
              const relativeTimeStr = formatDynamicRelativeTime(uploadTimestamp, currentDeviceTime);
              const deviceTimeStr = formatDeviceTime(uploadTimestamp, true);
              const deviceDateStr = formatDeviceDate(uploadTimestamp);
              const fullTooltip = `Device Local Time: ${formatDeviceDateTime(uploadTimestamp)}`;

              return (
                <tr
                  key={doc.id}
                  className={`doc-row ${isFailed ? 'row-failed' : ''} ${
                    isProcessing || isUploaded ? 'row-processing' : ''
                  }`}
                >
                  {/* Name & Type */}
                  <td className="cell-doc-info">
                    <div className="doc-item-title-box">
                      <div className={`doc-icon-badge ${doc.file_type || 'pdf'}`} aria-hidden="true">
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

                  {/* Status: Continuously updates dynamically as time passes */}
                  <td className="cell-status">
                    <DocumentStatusBadge
                      status={doc.status}
                      stage={doc.processing?.stage}
                      vectorStatus={doc.vector_status}
                      size="sm"
                      uploadedAt={uploadTimestamp}
                      now={currentDeviceTime}
                    />
                  </td>

                  {/* Size */}
                  <td className="cell-size">
                    <span className="size-badge">
                      <HardDrive size={12} className="inline-icon" aria-hidden="true" />
                      {formatFileSize(doc.file_size)}
                    </span>
                  </td>

                  {/* Synchronized Device Uploaded Time with dynamic ticking */}
                  <td className="cell-date">
                    <div className="date-wrapper" title={fullTooltip}>
                      <span className="relative-date">
                        <span className={`live-time-indicator ${isProcessing || isUploaded ? 'active-pulse' : ''}`} />
                        {relativeTimeStr}
                      </span>
                      <span className="absolute-date">
                        <Clock size={11} className="clock-micro-icon" aria-hidden="true" />
                        <span className="time-part">{deviceTimeStr}</span>
                        <span className="date-separator-dot">•</span>
                        <span className="date-part">{deviceDateStr}</span>
                      </span>
                    </div>
                  </td>

                  {/* Actions */}
                  <td className="cell-actions text-right">
                    <div className="actions-cluster">
                      {/* For Failed documents: Show safe Diagnostic Failure Details button */}
                      {isFailed && (
                        <Button
                          variant="danger"
                          size="sm"
                          icon={<AlertTriangle size={14} />}
                          onClick={() => onViewFailure(doc)}
                          title={`View safe failure details for ${doc.filename}`}
                          aria-label={`View safe failure details for ${doc.filename}`}
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
                          title={`View extracted data for ${doc.filename}`}
                          aria-label={`View extracted data for ${doc.filename}`}
                        >
                          View Details
                        </Button>
                      )}

                      {/* Delete button */}
                      <button
                        type="button"
                        className="action-icon-btn delete"
                        onClick={() => onDeleteRequest(doc)}
                        title={`Delete ${doc.filename}`}
                        aria-label={`Delete document ${doc.filename}`}
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

export default DocumentList;
