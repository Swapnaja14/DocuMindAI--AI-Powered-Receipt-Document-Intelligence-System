import React, { useEffect, useState } from 'react';
import { useAuth } from '../features/auth/AuthContext';
import { AppLayout } from '../layouts/AppLayout';
import { Card } from '../components/ui/Card';
import {
  FileText,
  Search,
  Shield,
  Calendar,
  CheckCircle,
  Database,
  Lock,
} from 'lucide-react';
import { apiClient } from '../api/client';
import './DashboardPage.css';

export const DashboardPage = () => {
  const { user } = useAuth();
  const [healthStatus, setHealthStatus] = useState('checking...');
  const [isHealthReady, setIsHealthReady] = useState(null);

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

    checkSystemHealth();
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
          <Card variant="glass" className="metric-card">
            <div className="metric-header">
              <span className="metric-label">Document Store</span>
              <div className="metric-icon-box blue">
                <FileText size={18} />
              </div>
            </div>
            <div className="metric-value">0</div>
            <p className="metric-desc">Receipts &amp; invoices uploaded</p>
          </Card>

          <Card variant="glass" className="metric-card">
            <div className="metric-header">
              <span className="metric-label">Vector Search</span>
              <div className="metric-icon-box purple">
                <Search size={18} />
              </div>
            </div>
            <div className="metric-value">FAISS</div>
            <p className="metric-desc">Multi-tenant vector retriever ready</p>
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

          <Card variant="glass" className="metric-card">
            <div className="metric-header">
              <span className="metric-label">Storage Isolation</span>
              <div className="metric-icon-box cyan">
                <Database size={18} />
              </div>
            </div>
            <div className="metric-value">50 MB</div>
            <p className="metric-desc">Max allocation quota</p>
          </Card>
        </div>

        {/* Profile & Security Credentials Card */}
        <div className="dashboard-details-section">
          <Card variant="glass" className="details-card">
            <h3 className="section-title">
              <Lock size={18} className="title-icon" />
              Tenant Credentials &amp; Session Details
            </h3>

            <div className="details-grid">
              <div className="detail-item">
                <span className="detail-name">Account Email</span>
                <span className="detail-value">{user?.email}</span>
              </div>

              <div className="detail-item">
                <span className="detail-name">User Identifier</span>
                <span className="detail-value mono">{user?.id}</span>
              </div>

              <div className="detail-item">
                <span className="detail-name">Access Role</span>
                <span className="detail-value capitalize">{user?.role}</span>
              </div>

              <div className="detail-item">
                <span className="detail-name">Member Since</span>
                <span className="detail-value">
                  <Calendar size={14} className="inline-icon" />
                  {formattedDate}
                </span>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </AppLayout>
  );
};
