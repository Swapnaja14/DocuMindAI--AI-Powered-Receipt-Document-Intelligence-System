import React from 'react';
import { Card } from '../components/ui/Card';
import { FileText, Sparkles, ShieldCheck, Zap } from 'lucide-react';
import './AuthLayout.css';

export const AuthLayout = ({ children }) => {
  return (
    <div className="auth-layout-container">
      {/* Dynamic Ambient Background Glows */}
      <div className="ambient-glow glow-top-left" />
      <div className="ambient-glow glow-bottom-right" />

      <div className="auth-content-wrapper">
        {/* Brand Side Hero */}
        <div className="auth-brand-side">
          <div className="brand-logo-badge">
            <div className="logo-icon-wrapper">
              <FileText size={24} className="logo-icon" />
              <Sparkles size={14} className="logo-sparkle" />
            </div>
            <span className="brand-name">DocuMind AI</span>
          </div>

          <h1 className="brand-hero-title">
            Intelligent Receipt &amp; Document Intelligence System
          </h1>

          <p className="brand-hero-desc">
            Transform raw financial receipts, invoices, and accounting PDFs into structured, validated data with multi-tenant RAG semantic search.
          </p>

          <div className="brand-features-list">
            <div className="feature-item">
              <div className="feature-icon-box">
                <Zap size={16} />
              </div>
              <div>
                <strong className="feature-title">Real-Time Extraction</strong>
                <p className="feature-desc">Automated OCR and Gemini-powered line-item parsing</p>
              </div>
            </div>

            <div className="feature-item">
              <div className="feature-icon-box">
                <ShieldCheck size={16} />
              </div>
              <div>
                <strong className="feature-title">Isolated Multi-Tenant Security</strong>
                <p className="feature-desc">Argon2id auth, cryptographic JWTs, and isolated FAISS vectors</p>
              </div>
            </div>
          </div>
        </div>

        {/* Form Container */}
        <div className="auth-form-side">
          <Card variant="glass" glow className="auth-card">
            {children}
          </Card>
        </div>
      </div>
    </div>
  );
};
