import React, { useEffect, useState } from 'react';
import { useAuth } from '../features/auth/AuthContext';
import { AppLayout } from '../layouts/AppLayout';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import {
  FileText,
  Shield,
  Calendar,
  CheckCircle,
  Lock,
  TrendingUp,
  ArrowRight,
  Sparkles,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '../api/client';
import { documentsApi } from '../api/documents';
import { expensesApi } from '../api/expenses';
import './DashboardPage.css';

export const DashboardPage = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [healthStatus, setHealthStatus] = useState('checking...');
  const [isHealthReady, setIsHealthReady] = useState(null);
  const [docCount, setDocCount] = useState(0);
  const [expenseSummary, setExpenseSummary] = useState(null);

  useEffect(() => {
    // Check backend readiness probe
    const checkSystemHealth = async () => {
      try {
        const res = await apiClient('/health/ready');
        setHealthStatus(res.status === 'ready' ? 'Operational' : 'Degraded');
        setIsHealthReady(res.status === 'ready');
      } catch {
        setHealthStatus('Offline / Unreachable');
        setIsHealthReady(false);
      }
    };

    const fetchStats = async () => {
      try {
        const docs = await documentsApi.getDocuments();
        if (Array.isArray(docs)) {
          setDocCount(docs.length);
        }
      } catch {
        // silent fail on dashboard metrics
      }

      try {
        const expData = await expensesApi.getExpenseSummary();
        setExpenseSummary(expData);
      } catch {
        // silent fail on expense summary
      }
    };

    checkSystemHealth();
    fetchStats();
  }, []);

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
        {/* Welcome Banner */}
        <div className="dashboard-hero">
          <div className="hero-text-block">
            <span className="hero-greeting-badge">
              <CheckCircle size={14} className="badge-icon" />
              Authenticated Session
            </span>
            <h1 className="hero-title">Welcome to DocuMind Workspace</h1>
            <p className="hero-subtitle">
              Your AI-powered environment for intelligent receipt analysis, document OCR, and multi-tenant RAG search.
            </p>
          </div>

          <div className="system-health-pill">
            <span className={`status-dot ${isHealthReady ? 'status-green' : isHealthReady === false ? 'status-red' : 'status-yellow'}`} />
            <span className="health-label">Backend Service:</span>
            <strong className="health-val">{healthStatus}</strong>
          </div>
        </div>

        {/* Quick Stat Highlights */}
        <div className="dashboard-metrics-grid">
          <Card
            variant="glass"
            className="metric-card interactive"
            onClick={() => navigate('/documents')}
            style={{ cursor: 'pointer' }}
            title="Click to manage documents"
          >
            <div className="metric-header">
              <span className="metric-label">Document Store</span>
              <div className="metric-icon-box blue">
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
            style={{ cursor: 'pointer' }}
            title="Click to ask questions with AI Chat"
          >
            <div className="metric-header">
              <span className="metric-label">RAG Intelligence</span>
              <div className="metric-icon-box cyan">
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
            style={{ cursor: 'pointer' }}
            title="Click to view detailed expense summaries"
          >
            <div className="metric-header">
              <span className="metric-label">Expense Intelligence</span>
              <div className="metric-icon-box purple">
                <TrendingUp size={18} />
              </div>
            </div>
            <div className="metric-value">
              {expenseSummary?.total_expenses?.[0]
                ? `${expenseSummary.total_expenses[0].currency} ${expenseSummary.total_expenses[0].total_amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
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
              <div className="metric-icon-box green">
                <Shield size={18} />
              </div>
            </div>
            <div className="metric-value">Argon2id</div>
            <p className="metric-desc">Cryptographically secured tenant</p>
          </Card>
        </div>

        {/* Expense Quick Glance Banner */}
        {expenseSummary && expenseSummary.overall_document_count > 0 && (
          <div className="dashboard-expense-banner animate-fade-in">
            <Card variant="glass" className="expense-glance-card">
              <div className="glance-left">
                <div className="glance-icon-box">
                  <TrendingUp size={22} />
                </div>
                <div>
                  <h3 className="glance-title">Expense Summaries Active</h3>
                  <p className="glance-subtitle">
                    Tracking {expenseSummary.overall_document_count} analyzed receipts across{' '}
                    {expenseSummary.available_vendors.length} vendors with time-series trends and invoice rankings.
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
            <h3 className="section-title">
              <Lock size={18} className="title-icon" />
              Tenant Credentials &amp; Session Details
            </h3>

            <div className="details-grid">
              <div className="detail-item">
                <span className="detail-name">Account Email
