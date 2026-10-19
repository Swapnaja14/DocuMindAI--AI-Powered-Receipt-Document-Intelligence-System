import React, { useState, useEffect, useCallback } from 'react';
import { AppLayout } from '../layouts/AppLayout';
import { Card } from '../components/ui/Card';
import {
  FileText,
  UploadCloud,
  CheckCircle2,
  AlertTriangle,
  Loader2,
  Layers,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import { documentsApi } from '../api/documents';
import { DocumentUploader } from '../features/documents/components/DocumentUploader';
import { DocumentFilterBar } from '../features/documents/components/DocumentFilterBar';
import { DocumentList } from '../features/documents/components/DocumentList';
import { DocumentFailureModal } from '../features/documents/components/DocumentFailureModal';
import { DeleteConfirmDialog } from '../features/documents/components/DeleteConfirmDialog';
import { DocumentDetailsModal } from '../features/documents/components/DocumentDetailsModal';
import { getStatusCategory } from '../features/documents/utils/statusUtils';
import './DocumentsPage.css';

const POLLING_INTERVAL_MS = 3500;

export const DocumentsPage = () => {
  const [documents, setDocuments] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [activeTab, setActiveTab] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [isUploadSectionOpen, setIsUploadSectionOpen] = useState(true);

  // Modals state
  const [failureModalDoc, setFailureModalDoc] = useState(null);
  const [deleteModalDoc, setDeleteModalDoc] = useState(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [detailsModalDocId, setDetailsModalDocId] = useState(null);

  // Toast notifications state
  const [toastMessage, setToastMessage] = useState(null);

  const showToast = (text, type = 'success') => {
    setToastMessage({ text, type, id: Date.now() });
    setTimeout(() => {
      setToastMessage((current) => (current?.text === text ? null : current));
    }, 4500);
  };

  // Fetch document list
  const fetchDocuments = useCallback(async (isSilent = false) => {
    if (!isSilent) setIsRefreshing(true);
    try {
      const data = await documentsApi.getDocuments();
      setDocuments(Array.isArray(data) ? data : []);
      setLastUpdated(new Date());
    } catch (err) {
      if (!isSilent) {
        showToast(err.message || 'Failed to fetch document status.', 'error');
      }
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, []);

  // Initial load
  useEffect(() => {
    fetchDocuments(false);
  }, [fetchDocuments]);

  // Check if any documents are actively processing
  const hasActiveProcessing = documents.some((doc) => {
    const category = getStatusCategory(doc.status);
    const isIndexing = doc.vector_status === 'INDEXING';
    return category === 'uploaded' || category === 'processing' || isIndexing;
  });

  // Polling effect: poll periodically only while processing is active
  useEffect(() => {
    if (!hasActiveProcessing) return;

    const intervalId = setInterval(() => {
      fetchDocuments(true);
    }, POLLING_INTERVAL_MS);

    return () => clearInterval(intervalId);
  }, [hasActiveProcessing, fetchDocuments]);

  // Handle successful upload
  const handleUploadSuccess = (newDoc) => {
    showToast(`Uploaded ${newDoc.filename}. Processing queued!`, 'success');
    fetchDocuments(false);
  };

  // Handle Document Deletion
  const handleDeleteConfirm = async () => {
    if (!deleteModalDoc) return;
    setIsDeleting(true);
    try {
      await documentsApi.deleteDocument(deleteModalDoc.id);
      showToast(`Document "${deleteModalDoc.filename}" permanently deleted.`, 'success');
      setDeleteModalDoc(null);
      // Remove directly from local state for immediate responsiveness
      setDocuments((prev) => prev.filter((d) => d.id !== deleteModalDoc.id));
    } catch (err) {
      showToast(err.message || 'Failed to delete document.', 'error');
    } finally {
      setIsDeleting(false);
    }
  };

  // Counts for tabs & summary cards
  const counts = documents.reduce(
    (acc, doc) => {
      acc.all += 1;
      const cat = getStatusCategory(doc.status);
      if (cat === 'uploaded') acc.uploaded += 1;
      else if (cat === 'processing') acc.processing += 1;
      else if (cat === 'completed') acc.completed += 1;
      else if (cat === 'failed') acc.failed += 1;
      return acc;
    },
    { all: 0, uploaded: 0, processing: 0, completed: 0, failed: 0 }
  );

  // Filtered documents list based on tab & search query
  const filteredDocuments = documents.filter((doc) => {
    // 1. Status Filter Tab
    if (activeTab !== 'all') {
      const category = getStatusCategory(doc.status);
      if (category !== activeTab) return false;
    }

    // 2. Search Query
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      const filenameMatch = doc.filename?.toLowerCase().includes(q);
      const typeMatch = doc.file_type?.toLowerCase().includes(q);
      return filenameMatch || typeMatch;
    }

    return true;
  });

  return (
    <AppLayout>
      <div className="documents-page-view animate-fade-in">
        {/* Page Header */}
        <div className="doc-page-header">
          <div>
            <span className="doc-page-badge">
              <FileText size={14} className="inline-icon" />
              Document Intelligence Hub
            </span>
            <h1 className="doc-page-title">Document Management</h1>
            <p className="doc-page-subtitle">
              Upload, process, and inspect PDF receipts &amp; invoices with OCR extraction and vector search indexing.
            </p>
          </div>

          <div className="header-actions">
            <button
              className="toggle-upload-btn"
              onClick={() => setIsUploadSectionOpen((prev) => !prev)}
              aria-expanded={isUploadSectionOpen}
            >
              <UploadCloud size={16} />
              <span>{isUploadSectionOpen ? 'Hide Uploader' : 'Upload PDF'}</span>
              {isUploadSectionOpen ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
            </button>
          </div>
        </div>

        {/* Global Toast Notification */}
        {toastMessage && (
          <div className={`doc-toast-banner ${toastMessage.type} animate-slide-up`}>
            {toastMessage.type === 'success' ? (
              <CheckCircle2 size={16} className="toast-icon" />
            ) : (
              <AlertTriangle size={16} className="toast-icon" />
            )}
            <span className="toast-text">{toastMessage.text}</span>
          </div>
        )}

        {/* Metric Summary Cards */}
        <div className="doc-metrics-grid">
          <Card variant="glass" className="doc-metric-card">
            <div className="metric-header">
              <span className="metric-label">Total Documents</span>
              <div className="metric-icon-box blue">
                <FileText size={18} />
              </div>
            </div>
            <div className="metric-value">{counts.all}</div>
            <p className="metric-desc">In tenant workspace</p>
          </Card>

          <Card variant="glass" className="doc-metric-card">
            <div className="metric-header">
              <span className="metric-label">Pipeline Active</span>
              <div className={`metric-icon-box purple ${counts.processing > 0 ? 'pulse' : ''}`}>
                {counts.processing > 0 ? (
                  <Loader2 size={18} className="spinning" />
                ) : (
                  <Layers size={18} />
                )}
              </div>
            </div>
            <div className="metric-value">
              {counts.processing + counts.uploaded}
            </div>
            <p className="metric-desc">
              {counts.processing} processing • {counts.uploaded} in queue
            </p>
          </Card>

          <Card variant="glass" className="doc-metric-card">
            <div className="metric-header">
              <span className="metric-label">Completed &amp; Ready</span>
              <div className="metric-icon-box green">
                <CheckCircle2 size={18} />
              </div>
            </div>
            <div className="metric-value">{counts.completed}</div>
            <p className="metric-desc">OCR &amp; AI extracted</p>
          </Card>

          <Card variant="glass" className="doc-metric-card">
            <div className="metric-header">
              <span className="metric-label">Action Required</span>
              <div className={`metric-icon-box red ${counts.failed > 0 ? 'alert' : ''}`}>
                <AlertTriangle size={18} />
              </div>
            </div>
            <div className="metric-value">{counts.failed}</div>
            <p className="metric-desc">
              {counts.failed > 0 ? 'Failures with safe details' : 'Zero pipeline failures'}
            </p>
          </Card>
        </div>

        {/* Upload Section */}
        {isUploadSectionOpen && (
          <div className="upload-container-section animate-slide-up">
            <DocumentUploader onUploadSuccess={handleUploadSuccess} />
          </div>
        )}

        {/* Filter and Search Bar */}
        <DocumentFilterBar
          activeTab={activeTab}
          onTabChange={setActiveTab}
          counts={counts}
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          onRefresh={() => fetchDocuments(false)}
          isRefreshing={isRefreshing}
          isAutoPolling={hasActiveProcessing}
          lastUpdated={lastUpdated}
        />

        {/* Document List */}
        <DocumentList
          documents={filteredDocuments}
          isLoading={isLoading}
          onViewDetails={(doc) => setDetailsModalDocId(doc.id)}
          onViewFailure={(doc) => setFailureModalDoc(doc)}
          onDeleteRequest={(doc) => setDeleteModalDoc(doc)}
          activeFilter={activeTab}
          searchQuery={searchQuery}
        />

        {/* Safe Failure Details Modal */}
        <DocumentFailureModal
          document={failureModalDoc}
          isOpen={Boolean(failureModalDoc)}
          onClose={() => setFailureModalDoc(null)}
          onDeleteRequest={(doc) => {
            setFailureModalDoc(null);
            setDeleteModalDoc(doc);
          }}
          onReuploadRequest={() => {
            setFailureModalDoc(null);
            setIsUploadSectionOpen(true);
            window.scrollTo({ top: 0, behavior: 'smooth' });
          }}
        />

        {/* Delete Confirmation Modal */}
        <DeleteConfirmDialog
          document={deleteModalDoc}
          isOpen={Boolean(deleteModalDoc)}
          isDeleting={isDeleting}
          onClose={() => {
            if (!isDeleting) setDeleteModalDoc(null);
          }}
          onConfirm={handleDeleteConfirm}
        />

        {/* Document Details Modal */}
        <DocumentDetailsModal
          docId={detailsModalDocId}
          isOpen={Boolean(detailsModalDocId)}
          onClose={() => setDetailsModalDocId(null)}
        />
      </div>
    </AppLayout>
  );
};
