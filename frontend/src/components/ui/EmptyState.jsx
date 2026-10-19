import React from 'react';
import { FolderOpen } from 'lucide-react';
import { Button } from './Button';
import './EmptyState.css';

/**
 * Reusable EmptyState component supporting:
 * - icon: custom icon component or default
 * - title: primary empty heading
 * - description: contextual guidance
 * - actionLabel & onAction: primary CTA
 * - secondaryActionLabel & onSecondaryAction: secondary CTA
 * - compact: boolean for compact containers
 */
export const EmptyState = ({
  icon,
  title = 'No results found',
  description = 'There are no items to display matching your criteria.',
  actionLabel,
  onAction,
  actionIcon,
  secondaryActionLabel,
  onSecondaryAction,
  secondaryActionIcon,
  compact = false,
  className = '',
}) => {
  return (
    <div
      className={`empty-state-card ${compact ? 'compact' : ''} ${className}`}
      role="region"
      aria-label={title}
    >
      <div className="empty-state-icon-wrapper" aria-hidden="true">
        {icon || <FolderOpen size={compact ? 28 : 38} className="empty-state-default-icon" />}
      </div>

      <div className="empty-state-text-block">
        <h3 className="empty-state-title">{title}</h3>
        {description && <p className="empty-state-desc">{description}</p>}
      </div>

      {(actionLabel || secondaryActionLabel) && (
        <div className="empty-state-actions">
          {actionLabel && onAction && (
            <Button
              variant="primary"
              size={compact ? 'sm' : 'md'}
              onClick={onAction}
              icon={actionIcon}
            >
              {actionLabel}
            </Button>
          )}

          {secondaryActionLabel && onSecondaryAction && (
            <Button
              variant="outline"
              size={compact ? 'sm' : 'md'}
              onClick={onSecondaryAction}
              icon={secondaryActionIcon}
            >
              {secondaryActionLabel}
            </Button>
          )}
        </div>
      )}
    </div>
  );
};

export default EmptyState;
