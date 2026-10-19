import React, { useState, useEffect } from 'react';
import { X, Sliders, Trash2, Activity, Info, RefreshCw } from 'lucide-react';
import { ragApi } from '../../../api/rag';
import './ChatSettingsModal.css';

export const ChatSettingsModal = ({
  isOpen,
  onClose,
  topK,
  onChangeTopK,
  onClearHistory,
  messageCount,
}) => {
  const [cacheMetrics, setCacheMetrics] = useState(null);
  const [isLoadingMetrics, setIsLoadingMetrics] = useState(false);
  const [metricsError, setMetricsError] = useState(null);
  const [confirmClear, setConfirmClear] = useState(false);

  useEffect(() => {
    if (isOpen) {
      fetchMetrics();
      setConfirmClear(false);
    }
  }, [isOpen]);

  const fetchMetrics = async () => {
    setIsLoadingMetrics(true);
    setMetricsError(null);
    try {
      const data = await ragApi.getCacheMetrics();
      setCacheMetrics(data);
    } catch (err) {
      setMetricsError(err.message || 'Failed to load cache metrics');
    } finally {
      setIsLoadingMetrics(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="modal-backdrop animate-fade-in" onClick={onClose} role="dialog" aria-modal="true">
      <div className="chat-settings-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="header-title-group">
            <Sliders size={20} className="header-icon" />
            <h2 className="modal-title">Chat &amp; Retrieval Settings</h2>
          </div>
          <button type="button" className="close-btn" onClick={onClose} aria-label="Close settings">
            <X size={18} />
          </button>
        </div>

        <div className="modal-body">
          {/* Top-K Retrieval Parameter */}
          <div className="settings-section">
            <div className="section-label-row">
              <label htmlFor="top-k-slider" className="section-label">
                Retrieval Depth (Top-K Chunks)
              </label>
              <span className="top-k-value-pill">{topK} chunks</span>
            </div>
            <p className="section-desc">
              Determines how many top relevant text passages are retrieved from your vector index for answer grounding.
            </p>
            <div className="slider-wrapper">
              <input
                id="top-k-slider"
                type="range"
                min="1"
                max="10"
                step="1"
                value={topK}
                onChange={(e) => onChangeTopK(Number(e.target.value))}
                className="top-k-range-input"
              />
              <div className="slider-ticks">
                <span>1 (Focused)</span>
                <span>5 (Balanced)</span>
                <span>10 (Broad)</span>
              </div>
            </div>
          </div>

          {/* RAG Cache Status & Metrics */}
          <div className="settings-section">
            <div className="section-label-row">
              <span className="section-label">RAG Cache Performance</span>
              <button
                type="button"
                className="refresh-metrics-btn"
                onClick={fetchMetrics}
                disabled={isLoadingMetrics}
                title="Refresh metrics"
              >
                <RefreshCw size={12} className={isLoadingMetrics ? 'animate-spin' : ''} />
                <span>Refresh</span>
              </button>
            </div>
            <p className="section-desc">
              Monitors Redis response caching and hit ratio to reduce LLM latency and cost.
            </p>

            {metricsError ? (
              <div className="metrics-error-box">
                <Info size={14} />
                <span>{metricsError}</span>
              </div>
            ) : cacheMetrics?.summary ? (
              <div className="metrics-grid">
                <div className="metric-cell">
                  <span className="metric-label">Hit Ratio</span>
                  <span className="metric-value">
                    {cacheMetrics.summary.hit_ratio != null
                      ? `${(cacheMetrics.summary.hit_ratio * 100).toFixed(1)}%`
                      : 'N/A'}
                  </span>
                </div>
                <div className="metric-cell">
                  <span className="metric-label">Total Hits</span>
                  <span className="metric-value">{cacheMetrics.summary.hits ?? 0}</span>
                </div>
                <div className="metric-cell">
                  <span className="metric-label">Total Misses</span>
                  <span className="metric-value">{cacheMetrics.summary.misses ?? 0}</span>
                </div>
              </div>
            ) : (
              <div className="metrics-loading-box">
                <Activity size={14} className="animate-spin" />
                <span>Loading metrics...</span>
              </div>
            )}
          </div>

          {/* History Management */}
          <div className="settings-section danger-section">
            <span className="section-label">Conversation Storage</span>
            <p className="section-desc">
              Your chat conversation contains {messageCount} {messageCount === 1 ? 'message' : 'messages'} stored locally.
            </p>

            {confirmClear ? (
              <div className="confirm-clear-box animate-fade-in">
                <span className="confirm-warning">Are you sure you want to clear your chat history?</span>
                <div className="confirm-buttons-row">
                  <button
                    type="button"
                    className="btn-danger-confirm"
                    onClick={() => {
                      onClearHistory();
                      setConfirmClear(false);
                    }}
                  >
                    Yes, Clear All
                  </button>
                  <button
                    type="button"
                    className="btn-cancel-confirm"
                    onClick={() => setConfirmClear(false)}
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <button
                type="button"
                className="btn-clear-history"
                onClick={() => setConfirmClear(true)}
                disabled={messageCount === 0}
              >
                <Trash2 size={14} />
                <span>Clear Chat History</span>
              </button>
            )}
          </div>
        </div>

        <div className="modal-footer">
          <button type="button" className="btn-modal-done" onClick={onClose}>
            Done
          </button>
        </div>
      </div>
    </div>
  );
};
