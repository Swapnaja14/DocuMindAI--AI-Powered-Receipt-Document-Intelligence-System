import React from 'react';
import { Loader2 } from 'lucide-react';
import './LoadingState.css';

/**
 * Reusable LoadingState component supporting:
 * - 'spinner': A clean, centered pulsing spinner with message
 * - 'card': Skeleton placeholder for metrics/cards
 * - 'table': Skeleton rows for data tables
 * - 'fullscreen': Full viewport loader
 */
export const LoadingState = ({
  variant = 'spinner',
  message = 'Loading data...',
  description = null,
  rows = 3,
  cardCount = 3,
  className = '',
}) => {
  if (variant === 'skeleton-cards') {
    return (
      <div
        className={`loading-skeleton-grid ${className}`}
        role="status"
        aria-live="polite"
        aria-label={message}
      >
        <span className="sr-only">{message}</span>
        {Array.from({ length: cardCount }).map((_, i) => (
          <div key={i} className="skeleton-card-item">
            <div className="skeleton-line skeleton-title" />
            <div className="skeleton-line skeleton-value" />
            <div className="skeleton-line skeleton-subtitle" />
          </div>
        ))}
      </div>
    );
  }

  if (variant === 'skeleton-table') {
    return (
      <div
        className={`loading-skeleton-table ${className}`}
        role="status"
        aria-live="polite"
        aria-label={message}
      >
        <span className="sr-only">{message}</span>
        {Array.from({ length: rows }).map((_, i) => (
          <div key={i} className="skeleton-table-row">
            <div className="skeleton-pill skeleton-avatar" />
            <div className="skeleton-line skeleton-cell-wide" />
            <div className="skeleton-line skeleton-cell-medium" />
            <div className="skeleton-line skeleton-cell-small" />
          </div>
        ))}
      </div>
    );
  }

  if (variant === 'fullscreen') {
    return (
      <div
        className={`loading-fullscreen-overlay ${className}`}
        role="status"
        aria-live="polite"
      >
        <div className="loading-spinner-box">
          <Loader2 size={40} className="spinning spinner-brand" />
          <p className="loading-message">{message}</p>
          {description && <p className="loading-desc">{description}</p>}
        </div>
      </div>
    );
  }

  return (
    <div
      className={`loading-spinner-container ${className}`}
      role="status"
      aria-live="polite"
    >
      <Loader2 size={32} className="spinning spinner-brand" />
      <span className="loading-message">{message}</span>
      {description && <span className="loading-desc">{description}</span>}
    </div>
  );
};

export default LoadingState;
