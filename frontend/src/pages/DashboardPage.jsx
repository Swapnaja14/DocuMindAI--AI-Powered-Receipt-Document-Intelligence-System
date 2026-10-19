import React, { useEffect, useState, useCallback } from 'react';
import { useAuth } from '../features/auth/AuthContext';
import { AppLayout } from '../layouts/AppLayout';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { LoadingState } from '../components/ui/LoadingState';
import { EmptyState } from '../components/ui/EmptyState';
import { ErrorState } from '../components/ui/ErrorState';
import {
  FileText,
  Shield,
  Calendar,
  CheckCircle,
  Lock,
  TrendingUp,
  ArrowRight,
  Sparkles,
  UploadCloud,
  RefreshCw,
  Server,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '../api/client';
import { documentsApi } from '../api/documents';
import { expensesApi } from '../api/expenses';
import './DashboardPage.css';

export const DashboardPage = () => {
  const { user } = useAuth();
  const navigate = useNavigate();

  // State Management for UX States
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [serverError, setServerError] = useState(null);

  const [healthStatus, setHealthStatus] = useState('checking...');
  const [isHealthReady, setIsHealthReady] = useState(null);
  const [docCount, setDocCount] = useState(0);
  const [expenseSummary, setExpenseSummary] = useState(null);

  const fetchDashboardData = useCallback(async (isManual = false) => {
    if (isManual) {
      setIsRefreshing(true);
    } else {
      setIsLoading(true);
    }
    setServerError(null);

    let hasCriticalError = false;
    let errorDetail = null;

    // 1. Backend health probe
    try {
      const res = await apiClient('/health/ready');
      setHealthStatus(res.status === 'ready' ? 'Operational' : 'Degraded');
      setIsHealthReady(res.status === 'ready');
    } catch (err) {
      setHealthStatus('Offline / Unreachable');
      setIsHealthReady(false);
      hasCriticalError = true;
      errorDetail = err;
    }

    // 2. Fetch Document stats
    try {
      const docs = await documentsApi.getDocuments();
      if (Array.isArray(docs)) {
        setDocCount(docs.length);
      }
    } catch (err) {
      if (!errorDetail) errorDetail = err;
    }

    // 3. Fetch Expense Summary
    try {
      const expData = await expensesApi.getExpenseSummary();
      setExpenseSummary(expData);
    } catch (err) {
      // Optional metrics fallback
    }

    if (hasCriticalError && errorDetail) {
      setServerError({
        message: errorDetail.message || 'Unable to connect to backend intelligence services.',
        status: errorDetail.status || 503,
        details: errorDetail.detail,
      });
    }

    setIsLoading(false);
    setIsRefreshing(false);
  }, []);

  useEffect(() => {
    fetchDashboardData(false);
  }, [fetchDashboardData]);

  const formattedDate = user?.created_at
    ? new Date(user.created_at).toLocaleDateString(undefined, {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
      })
    : 'Recently';

  return (
    <AppLayout>
      <div className="dashboard-view animate-fade-in">
        {/* Welcome Hero Banner */}
        <div className="dashboard-hero">
          <div className="hero-text-block">
            <span className="hero-greeting-badge">
              <CheckCircle size={14} className="badge-icon" aria-hidden="true" />
              Authenticated Session
            </span>
            <h1 className="hero-title">Welcome to DocuMind Workspace</h1>
            <p className="hero-subtitle">
              Your AI-powered environment for intelligent receipt analysis, document OCR, and multi-tenant RAG search.
            </p>
          </div>

          <div className="hero-right-actions">
            <div
              className="system-health-pill"
              role="status"
              aria-live="polite"
              aria-label={`Backend service status: ${healthStatus}`}
            >
              <span
                className={`status-dot ${
                  isHealthReady ? 'status-green' : isHealthReady === false ? 'status-red' : 'status-yellow'
                }`}
                aria-hidden="true"
              />
              <span className="health-label">Backend Service:</span>
              <strong className="health-val">{healthStatus}</strong>
            </div>

            <Button
              variant="outline"
              size="sm"
              onClick={() => fetchDashboardData(true)}
              isLoading={isRefreshing}
              icon={<RefreshCw size={14} />}
              title="Refresh dashboard metrics"
              aria-label="Refresh dashboard metrics"
            >
              Refresh
            </Button>
          </div>
        </div>

        {/* Server Error State Callout */}
        {serverError && (
          <ErrorState
            variant="banner"
            title="Service Warning"
            message={serverError.message}
            status={serverError.status}
            onRetry={() => fetchDashboardData(true)}
            isRetrying={isRefreshing}
            onDismiss={() => setServerError(null)}
          />
        )}

        {/* Loading State */}
        {isLoading ? (
          <div className="dashboard-loading-section">
            <LoadingState
              variant="skeleton-cards"
              cardCount={4}
              message="Fetching workspace statistics..."
            />
          </div>
        ) : (
          <>
            {/* Quick Stat Highlights Grid */}
            <div className="dashboard-metrics-grid" role="region" aria-label="Key Workspace Metrics">
              <Card
                variant="glass"
                className="metric-card interactive"
                onClick={() => navigate('/documents')}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    navigate('/documents');
                  }
                }}
                aria-label={`Document Store: ${docCount} documents. Click to view.`}
                title="Click to manage documents"
              >
                <div className="metric-header">
                  <span className="metric-label">Document Store</span>
                  <div className="metric-icon-box blue" aria-hidden="true">
                    <FileText size={18} />
                  </div>
                </div>
                <div className="metric-value">{docCount}</div>
                <p className="metric-desc">Receipts &amp; invoices uploaded • View all →</p>
              </Card>

              <Card
                variant="glass"
                className="metric-card interactive"
                onClick={() => navigate('/chat')}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    navigate('/chat');
                  }
                }}
                aria-label="RAG Intelligence AI Chat. Click to ask questions."
                title="Click to ask questions with AI Chat"
              >
                <div className="metric-header">
                  <span className="metric-label">RAG Intelligence</span>
                  <div className="metric-icon-box cyan" aria-hidden="true">
                    <Sparkles size={18} />
                  </div>
                </div>
                <div className="metric-value">AI Chat</div>
                <p className="metric-desc">Grounded Q&amp;A with citations • Ask now →</p>
              </Card>

              <Card
                variant="glass"
                className="metric-card interactive"
                onClick={() => navigate('/expenses')}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    navigate('/expenses');
                  }
                }}
                aria-label={`Expense Intelligence: ${
                  expenseSummary?.total_expenses?.[0]
                    ? `${expenseSummary.total_expenses[0].currency} ${expenseSummary.total_expenses[0].total_amount}`
                    : '0 invoices'
                }. Click to view summaries.`}
                title="Click to view detailed expense summaries"
              >
                <div className="metric-header">
                  <span className="metric-label">Expense Intelligence</span>
                  <div className="metric-icon-box purple" aria-hidden="true">
                    <TrendingUp size={18} />
                  </div>
                </div>
                <div className="metric-value">
                  {expenseSummary?.total_expenses?.[0]
                    ? `${expenseSummary.total_expenses[0].currency} ${expenseSummary.total_expenses[0].total_amount.toLocaleString(
                        undefined,
                        { minimumFractionDigits: 2, maximumFractionDigits: 2 }
                      )}`
                    : `${expenseSummary?.overall_document_count || 0} Invoices`}
                </div>
                <p className="metric-desc">
                  {expenseSummary?.total_expenses?.length > 1
                    ? `${expenseSummary.total_expenses.length} currencies tracked • View summaries →`
                    : 'Audited summaries & analytics • View →'}
                </p>
              </Card>

              <Card variant="glass" className="metric-card">
                <div className="metric-header">
                  <span className="metric-label">Security Tier</span>
                  <div className="metric-icon-box green" aria-hidden="true">
                    <Shield size={18} />
                  </div>
                </div>
                <div className="metric-value">Argon2id</div>
                <p className="metric-desc">Cryptographically secured tenant</p>
              </Card>
            </div>

            {/* Empty State Onboarding: Shown when 0 documents exist */}
            {docCount === 0 && (
              <div className="dashboard-empty-banner">
                <EmptyState
                  icon={<UploadCloud size={36} className="empty-state-default-icon" />}
                  title="Your Document Workspace is Ready"
                  description="Upload receipts and invoices to automatically extract merchant data, analyze line-item expenses, and query documents with citations in AI Chat."
                  actionLabel="Upload First Receipt"
                  onAction={() => navigate('/documents')}
                  actionIcon={<UploadCloud size={16} />}
                  secondaryActionLabel="Explore AI Chat"
                  onSecondaryAction={() => navigate('/chat')}
                  secondaryActionIcon={<Sparkles size={16} />}
                />
              </div>
            )}

            {/* Expense Quick Glance Banner */}
            {expenseSummary && expenseSummary.overall_document_count > 0 && (
              <div className="dashboard-expense-banner animate-fade-in">
                <Card variant="glass" className="expense-glance-card">
                  <div className="glance-left">
                    <div className="glance-icon-box" aria-hidden="true">
                      <TrendingUp size={22} />
                    </div>
                    <div>
                      <h2 className="glance-title">Expense Summaries Active</h2>
                      <p className="glance-subtitle">
                        Tracking {expenseSummary.overall_document_count} analyzed receipts across{' '}
                        {expenseSummary.available_vendors?.length || 0} vendors with time-series trends and invoice rankings.
                      </p>
                    </div>
                  </div>
                  <div className="glance-actions">
                    <Button
                      variant="primary"
                      size="sm"
                      onClick={() => navigate('/expenses')}
                      icon={<ArrowRight size={14} />}
                    >
                      View Expense Summaries
                    </Button>
                  </div>
                </Card>
              </div>
            )}

            {/* Profile & Security Credentials Card */}
            <div className="dashboard-details-section">
              <Card variant="glass" className="details-card">
                <h2 className="section-title">
                  <Lock size={18} className="title-icon" aria-hidden="true" />
                  Tenant Credentials &amp; Session Details
                </h2>

                <div className="details-grid">
                  <div className="detail-item">
                    <span className="detail-name">Account Email</span>
                    <span className="detail-value">{user?.email || 'N/A'}</span>
                  </div>
                  <div className="detail-item">
                    <span className="detail-name">Role &amp; Permissions</span>
                    <span className="detail-value capitalize">{user?.role || 'User'}</span>
                  </div>
                  <div className="detail-item">
                    <span className="detail-name">Tenant Identifier</span>
                    <span className="detail-value mono">{user?.tenant_id || user?.id || 'tenant-default'}</span>
                  </div>
                  <div className="detail-item">
                    <span className="detail-name">Session Created</span>
                    <span className="detail-value">
                      <Calendar size={14} className="inline-icon" aria-hidden="true" />
                      {formattedDate}
                    </span>
                  </div>
                </div>
              </Card>
            </div>
          </>
        )}
      </div>
    </AppLayout>
  );
};

export default DashboardPage;
