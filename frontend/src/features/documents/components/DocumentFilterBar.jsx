import React from 'react';
import { Search, RotateCw, Activity } from 'lucide-react';
import { Button } from '../../../components/ui/Button';
import { formatDeviceTime } from '../utils/dateUtils';
import './DocumentFilterBar.css';

export const DocumentFilterBar = ({
  activeTab,
  onTabChange,
  counts = {},
  searchQuery,
  onSearchChange,
  onRefresh,
  isRefreshing,
  isAutoPolling,
  lastUpdated,
}) => {
  const tabs = [
    { id: 'all', label: 'All Documents', count: counts.all || 0 },
    { id: 'uploaded', label: 'Uploaded (Queued)', count: counts.uploaded || 0 },
    { id: 'processing', label: 'Processing', count: counts.processing || 0 },
    { id: 'completed', label: 'Completed', count: counts.completed || 0 },
    { id: 'failed', label: 'Failed', count: counts.failed || 0 },
  ];

  return (
    <div className="filter-bar-container">
      {/* Top row: Status Tabs & Auto-polling pill */}
      <div className="filter-tabs-row">
        <div className="status-tabs-group" role="tablist" aria-label="Filter documents by status">
          {tabs.map((tab) => {
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                role="tab"
                aria-selected={isActive}
                className={`filter-tab-pill ${isActive ? 'active' : ''} tab-${tab.id}`}
                onClick={() => onTabChange(tab.id)}
              >
                <span className="tab-label">{tab.label}</span>
                <span className="tab-count-badge">{tab.count}</span>
              </button>
            );
          })}
        </div>

        {/* Live Auto-Polling Indicator */}
        <div className="sync-status-indicator">
          {isAutoPolling ? (
            <div className="polling-active-pill" title="Auto-polling active while processing documents">
              <span className="pulse-dot" />
              <Activity size={13} className="pulse-icon" />
              <span>Live sync active</span>
            </div>
          ) : (
            <div className="polling-idle-pill">
              <span className="idle-dot" />
              <span>Sync idle</span>
            </div>
          )}

          {/* Manual Refresh Button */}
          <Button
            variant="outline"
            size="sm"
            onClick={onRefresh}
            isLoading={isRefreshing}
            icon={<RotateCw size={14} className={isRefreshing ? 'spinning' : ''} />}
            title="Refresh document status"
          >
            Refresh
          </Button>
        </div>
      </div>

      {/* Bottom row: Search input & Last updated caption */}
      <div className="filter-controls-row">
        <div className="search-input-wrapper">
          <Search size={16} className="search-icon" />
          <input
            type="text"
            className="search-input"
            placeholder="Search documents by filename..."
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            aria-label="Search documents by filename"
          />
          {searchQuery && (
            <button
              className="clear-search-btn"
              onClick={() => onSearchChange('')}
              aria-label="Clear search"
            >
              ×
            </button>
          )}
        </div>

        {lastUpdated && (
          <span className="last-updated-text" title="Synchronized with your device clock">
            Last sync: {formatDeviceTime(lastUpdated, true)}
          </span>
        )}
      </div>
    </div>
  );
};
