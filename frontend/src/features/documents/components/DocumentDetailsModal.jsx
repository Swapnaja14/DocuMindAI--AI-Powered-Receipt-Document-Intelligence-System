import React, { useState, useEffect } from 'react';
import {
  FileText,
  X,
  Receipt,
  Database,
  Loader2,
} from 'lucide-react';
import { Button } from '../../../components/ui/Button';
import { DocumentStatusBadge } from './DocumentStatusBadge';
import { documentsApi } from '../../../api/documents';
import { formatDeviceDateTime, formatDynamicRelativeTime } from '../utils/dateUtils';
import './DocumentDetailsModal.css';

export const DocumentDetailsModal = ({
  docId,
  isOpen,
  onClose,
}) => {
  const [docDetails, setDocDetails] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('extracted'); // 'extracted' | 'ocr' | 'vector'
  const [fetchError, setFetchError] = useState(null);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  useEffect(() => {
    if (!isOpen || !docId) {
      setDocDetails(null);
      return;
    }

    const loadDetails = async () => {
      setIsLoading(true);
      setFetchError(null);
      try {
        const data = await documentsApi.getDocument(docId);
        setDocDetails(data);
      } catch (err) {
        setFetchError(err.message || 'Failed to load document details.');
      } finally {
        setIsLoading(false);
      }
    };

    loadDetails();
  }, [isOpen, docId]);

  if (!isOpen) return null;

  const extracted = docDetails?.extracted_data || {};
  const ocr = docDetails?.ocr || {};
  const processing = docDetails?.processing || {};

  return (
    <div
      className="modal-overlay animate-fade-in"
      onClick={onClose}
      role="presentation"
    >
      <div
        className="modal-container doc-details-modal animate-slide-up"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="doc-details-title"
      >
        {/* Header */}
        <div className="modal-header">
          <div className="doc-header-left">
            <div className="doc-icon-box">
              <FileText size={22} />
            </div>
            <div>
              <h2 id="doc-details-title" className="modal-title">
                {docDetails?.filename || 'Document Details'}
              </h2>
              <div className="doc-meta-pills">
                {docDetails && (
                  <>
                    <DocumentStatusBadge
                      status={docDetails.status}
                      stage={processing.stage}
                      vectorStatus={docDetails.vector_status}
                      size="sm"
                    />
                    <span className="meta-text">
                      {(docDetails.file_size / (1024 * 1024)).toFixed(2)} MB
                    </span>
                    <span className="meta-text">•</span>
                    <span className="meta-text" title={formatDynamicRelativeTime(processing.uploaded_at)}>
                      Uploaded: {formatDeviceDateTime(processing.uploaded_at)} ({formatDynamicRelativeTime(processing.uploaded_at)})
                    </span>
                  </>
                )}
              </div>
            </div>
          </div>

          <button
            className="modal-close-btn"
            onClick={onClose}
            aria-label="Close document details"
          >
            <X size={18} />
          </button>
        </div>

        {/* Tab Navigation */}
        <div className="details-tab-nav">
          <button
            className={`tab-btn ${activeTab === 'extracted' ? 'tab-active' : ''}`}
            onClick={() => setActiveTab('extracted')}
          >
            <Receipt size={15} />
            Extracted Receipt Data
          </button>
          <button
            className={`tab-btn ${activeTab === 'ocr' ? 'tab-active' : ''}`}
            onClick={() => setActiveTab('ocr')}
          >
            <FileText size={15} />
            OCR Raw Text ({ocr.page_count || 0} pgs)
          </button>
          <button
            className={`tab-btn ${activeTab === 'vector' ? 'tab-active' : ''}`}
            onClick={() => setActiveTab('vector')}
          >
            <Database size={15} />
            Vector &amp; Chunks ({docDetails?.chunk_count || 0})
          </button>
        </div>

        {/* Body */}
        <div className="modal-body details-body">
          {isLoading && (
            <div className="loading-state">
              <Loader2 size={32} className="spinning text-primary" />
              <p>Loading document intelligence records...</p>
            </div>
          )}

          {fetchError && (
            <div className="details-error-callout">
              <p>{fetchError}</p>
            </div>
          )}

          {!isLoading && docDetails && (
            <>
              {/* Tab 1: Extracted Receipt Data */}
              {activeTab === 'extracted' && (
                <div className="tab-pane animate-fade-in">
                  <div className="extracted-fields-grid">
                    <div className="field-card">
                      <span className="field-label">Vendor Name</span>
                      <strong className="field-val">
                        {extracted.vendor || '—'}
                      </strong>
                    </div>

                    <div className="field-card">
                      <span className="field-label">Invoice / Receipt #</span>
                      <strong className="field-val">
                        {extracted.invoice_number || '—'}
                      </strong>
                    </div>

                    <div className="field-card">
                      <span className="field-label">Date</span>
                      <strong className="field-val">
                        {extracted.date || '—'}
                      </strong>
                    </div>

                    <div className="field-card highlight">
                      <span className="field-label">Total Amount</span>
                      <strong className="field-val total-price">
                        {extracted.currency || '$'}{' '}
                        {extracted.total !== null && extracted.total !== undefined
                          ? Number(extracted.total).toFixed(2)
                          : '—'}
                      </strong>
                    </div>
                  </div>

                  {/* Subtotal & Tax breakdown */}
                  <div className="pricing-breakdown">
                    <div className="breakdown-row">
                      <span>Subtotal:</span>
                      <strong>
                        {extracted.subtotal != null
                          ? `${extracted.currency || '$'} ${Number(extracted.subtotal).toFixed(2)}`
                          : '—'}
                      </strong>
                    </div>
                    <div className="breakdown-row">
                      <span>Tax Amount:</span>
                      <strong>
                        {extracted.tax != null
                          ? `${extracted.currency || '$'} ${Number(extracted.tax).toFixed(2)}`
                          : '—'}
                      </strong>
                    </div>
                  </div>

                  {/* Line Items Table */}
                  <div className="items-section">
                    <h4 className="section-heading">
                      Line Items ({extracted.items?.length || 0})
                    </h4>
                    {extracted.items && extracted.items.length > 0 ? (
                      <div className="items-table-wrapper">
                        <table className="items-table">
                          <thead>
                            <tr>
                              <th>Description</th>
                              <th className="text-right">Qty</th>
                              <th className="text-right">Unit Price</th>
                              <th className="text-right">Amount</th>
                            </tr>
                          </thead>
                          <tbody>
                            {extracted.items.map((item, idx) => (
                              <tr key={idx}>
                                <td>{item.description || 'Item'}</td>
                                <td className="text-right">{item.quantity ?? 1}</td>
                                <td className="text-right">
                                  {item.unit_price != null ? `$${Number(item.unit_price).toFixed(2)}` : '—'}
                                </td>
                                <td className="text-right font-bold">
                                  {item.amount != null ? `$${Number(item.amount).toFixed(2)}` : '—'}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <p className="empty-subtext">No individual line items parsed.</p>
                    )}
                  </div>
                </div>
              )}

              {/* Tab 2: OCR Raw Text */}
              {activeTab === 'ocr' && (
                <div className="tab-pane animate-fade-in">
                  <div className="ocr-meta-banner">
                    <span>Total Pages: <strong>{ocr.page_count || 1}</strong></span>
                    <span>•</span>
                    <span>Status: <strong>{docDetails.ocr_status || 'COMPLETED'}</strong></span>
                  </div>
                  <pre className="raw-text-viewer">
                    {ocr.raw_text || 'No raw text available.'}
                  </pre>
                </div>
              )}

              {/* Tab 3: Vector & Chunks */}
              {activeTab === 'vector' && (
                <div className="tab-pane animate-fade-in">
                  <div className="vector-summary-cards">
                    <div className="vector-card">
                      <span className="vector-label">FAISS Vector Status</span>
                      <strong className={`vector-status-val ${docDetails.vector_status === 'INDEXED' ? 'text-green' : ''}`}>
                        {docDetails.vector_status || 'PENDING'}
                      </strong>
                    </div>
                    <div className="vector-card">
                      <span className="vector-label">Chunk Count</span>
                      <strong className="vector-status-val">
                        {docDetails.chunk_count || 0} Chunks
                      </strong>
                    </div>
                  </div>

                  <p className="vector-info-desc">
                    Chunks are indexed into FAISS using multi-tenant user isolation. When you query the AI Assistant or RAG search, these embeddings provide semantic context.
                  </p>
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div className="modal-footer">
          <Button variant="secondary" size="sm" onClick={onClose}>
            Close
          </Button>
        </div>
      </div>
    </div>
  );
};
