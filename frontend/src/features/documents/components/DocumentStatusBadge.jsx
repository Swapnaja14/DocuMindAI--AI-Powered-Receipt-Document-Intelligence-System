import React from 'react';
import {
  Clock,
  Loader2,
  CheckCircle2,
  AlertCircle,
  Database,
  Sparkles,
} from 'lucide-react';
import { getStatusCategory, getStatusLabel } from '../utils/statusUtils';
import { formatProcessingElapsed } from '../utils/dateUtils';
import './DocumentStatusBadge.css';

export { getStatusCategory, getStatusLabel };

export const DocumentStatusBadge = ({
  status,
  stage,
  vectorStatus,
  size = 'md',
  showVectorStatus = true,
  uploadedAt,
  now,
}) => {
  const category = getStatusCategory(status);
  const baseLabel = getStatusLabel(status, stage);

  // Compute live elapsed duration if actively in queue or processing
  const isActive = category === 'uploaded' || category === 'processing' || vectorStatus === 'INDEXING';
  const elapsed = (isActive && uploadedAt) ? formatProcessingElapsed(uploadedAt, now) : '';

  let dynamicLabel = baseLabel;
  if (isActive && elapsed) {
    if (category === 'uploaded') {
      dynamicLabel = `In Queue (${elapsed})`;
    } else if (category === 'processing') {
      dynamicLabel = `${baseLabel} (${elapsed})`;
    }
  }

  return (
    <div className={`status-badge-container size-${size}`}>
      <span
        className={`status-badge badge-${category} ${isActive ? 'badge-live-pulse' : ''}`}
        title={isActive ? `Processing actively for ${elapsed || 'a few seconds'}` : `Status: ${dynamicLabel}`}
      >
        {category === 'uploaded' && <Clock size={13} className="badge-icon" />}
        {category === 'processing' && <Loader2 size={13} className="badge-icon spinning" />}
        {category === 'completed' && <CheckCircle2 size={13} className="badge-icon" />}
        {category === 'failed' && <AlertCircle size={13} className="badge-icon" />}
        <span className="badge-text">{dynamicLabel}</span>
      </span>

      {showVectorStatus && vectorStatus && category === 'completed' && (
        <span
          className={`vector-badge vector-${vectorStatus.toLowerCase()}`}
          title={`Vector Index: ${vectorStatus}`}
        >
          {vectorStatus === 'INDEXING' ? (
            <Sparkles size={11} className="vector-icon spinning" />
          ) : (
            <Database size={11} className="vector-icon" />
          )}
          <span>
            {vectorStatus === 'INDEXED'
              ? 'Vector Ready'
              : vectorStatus === 'INDEXING'
              ? `Indexing Vectors${elapsed ? ` (${elapsed})` : '...'}`
              : 'Vector Error'}
          </span>
        </span>
      )}
    </div>
  );
};

export default DocumentStatusBadge;
