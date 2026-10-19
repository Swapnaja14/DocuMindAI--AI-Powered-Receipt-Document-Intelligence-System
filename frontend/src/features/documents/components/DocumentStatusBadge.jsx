import React from 'react';
import {
  Clock,
  Loader2,
  CheckCircle2,
  AlertCircle,
  Database,
} from 'lucide-react';
import { getStatusCategory, getStatusLabel } from '../utils/statusUtils';
import './DocumentStatusBadge.css';

export { getStatusCategory, getStatusLabel };

export const DocumentStatusBadge = ({
  status,
  stage,
  vectorStatus,
  size = 'md',
  showVectorStatus = true,
}) => {
  const category = getStatusCategory(status);
  const label = getStatusLabel(status, stage);

  return (
    <div className={`status-badge-container size-${size}`}>
      <span className={`status-badge badge-${category}`}>
        {category === 'uploaded' && <Clock size={13} className="badge-icon" />}
        {category === 'processing' && <Loader2 size={13} className="badge-icon spinning" />}
        {category === 'completed' && <CheckCircle2 size={13} className="badge-icon" />}
        {category === 'failed' && <AlertCircle size={13} className="badge-icon" />}
        <span className="badge-text">{label}</span>
      </span>

      {showVectorStatus && vectorStatus && category === 'completed' && (
        <span className={`vector-badge vector-${vectorStatus.toLowerCase()}`} title={`Vector Index: ${vectorStatus}`}>
          <Database size={11} className="vector-icon" />
          <span>{vectorStatus === 'INDEXED' ? 'Vector Ready' : vectorStatus === 'INDEXING' ? 'Indexing...' : 'Vector Error'}</span>
        </span>
      )}
    </div>
  );
};
