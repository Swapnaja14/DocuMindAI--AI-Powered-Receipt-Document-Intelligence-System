import React, { useState } from 'react';
import { AlertCircle, RefreshCw, X, ChevronDown, ChevronUp, ServerCrash, WifiOff } from 'lucide-react';
import { Button } from './Button';
import './ErrorState.css';

/**
 * Reusable ErrorState component for Server errors, Network failures, and Validation alerts.
 * Features:
 * - variant: 'card' | 'banner' | 'inline'
 * - title: Custom or automatically derived from status code
 * - message: Human-readable error message
 * - status: HTTP status code (e.g. 500, 503, 401, 0)
 * - onRetry: Callback to retry the failed operation
 * - isRetrying: Boolean for loading indicator on Retry button
 * - onDismiss: Callback to dismiss the error
 * - details: Optional technical error details / stack
 */
export const ErrorState = ({
  variant = 'card',
  title,
  message = 'An unexpected error occurred. Please try again.',
  status,
  onRetry,
  isRetrying = false,
  onDismiss,
  details,
  className = '',
}) => {
  const [showDetails, setShowDetails] = useState(false);

  // Deriving icon and contextual heading
  const isNetworkOffline = status === 0 || message?.toLowerCase().includes('network') || message?.toLowerCase().includes('offline');
  const isServerDown = status === 500 || status === 502 || status === 503 || status === 504;

  const defaultTitle = title || (
    isNetworkOffline
      ? 'Connection Offline'
      : isServerDown
      ? 'Backend Service Unavailable'
      : 'Something went wrong'
  );

  const StatusIcon = isNetworkOffline ? WifiOff : isServerDown ? ServerCrash : AlertCircle;

  if (variant === 'banner') {
    return (
      <div
        className={`error-state-banner animate-fade-in ${className}`}
        role="alert"
        aria-live="assertive"
      >
        <div className="banner-icon-col">
          <StatusIcon size={20} className="error-icon" />
        </div>

        <div className="banner-content">
          <strong className="banner-title">{defaultTitle}:</strong>{' '}
          <span className="banner-msg">{message}</span>
        </div>

        <div className="banner-actions">
          {onRetry && (
            <Button
              variant="outline"
              size="sm"
              onClick={onRetry}
              isLoading={isRetrying}
              icon={<RefreshCw size={13} />}
              className="error-retry-btn"
            >
              Retry
            </Button>
          )}

          {onDismiss && (
            <button
              type="button"
              className="error-dismiss-btn"
              onClick={onDismiss}
              aria-label="Dismiss error notice"
            >
              <X size={16} />
            </button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div
      className={`error-state-card animate-fade-in ${className}`}
      role="alert"
      aria-live="assertive"
    >
      <div className="error-state-icon-wrapper">
        <StatusIcon size={36} className="error-card-icon" />
      </div>

      <div className="error-state-content">
        <div className="error-state-badge-row">
          {status !== undefined && status !== null && (
            <span className="error-status-badge">
              Status {status === 0 ? 'Offline' : status}
            </span>
          )}
          <span className="error-type-badge">
            {isNetworkOffline ? 'Network Failure' : isServerDown ? 'Server Error' : 'Request Error'}
          </span>
        </div>

        <h3 className="error-state-heading">{defaultTitle}</h3>
        <p className="error-state-message">{message}</p>

        {details && (
          <div className="error-details-disclosure">
            <button
              type="button"
              className="details-toggle-btn"
              onClick={() => setShowDetails(!showDetails)}
              aria-expanded={showDetails}
            >
              <span>Technical details</span>
              {showDetails ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            </button>

            {showDetails && (
              <pre className="error-details-pre">
                {typeof details === 'object' ? JSON.stringify(details, null, 2) : String(details)}
              </pre>
            )}
          </div>
        )}
      </div>

      <div className="error-state-actions">
        {onRetry && (
          <Button
            variant="primary"
            size="md"
            onClick={onRetry}
            isLoading={isRetrying}
            icon={<RefreshCw size={16} />}
          >
            Retry Request
          </Button>
        )}

        {onDismiss && (
          <Button
            variant="ghost"
            size="md"
            onClick={onDismiss}
          >
            Dismiss
          </Button>
        )}
      </div>
    </div>
  );
};

export default ErrorState;
