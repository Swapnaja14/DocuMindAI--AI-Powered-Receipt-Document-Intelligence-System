import React from 'react';
import { Card } from '../../../components/ui/Card';
import { Button } from '../../../components/ui/Button';
import {
  Award,
  FileText,
  Calendar,
  Eye,
  Hash,
  Layers,
} from 'lucide-react';
import './HighestValueInvoices.css';

const formatCurrency = (amount, currency = 'USD') => {
  const numericAmount = Number(amount) || 0;
  try {
    return new Intl.NumberFormat(undefined, {
      style: 'currency',
      currency: currency.length === 3 ? currency : 'USD',
      maximumFractionDigits: 2,
    }).format(numericAmount);
  } catch {
    return `${currency} ${numericAmount.toFixed(2)}`;
  }
};

export const HighestValueInvoices = ({
  invoices = [],
  onInspectInvoice,
}) => {
  if (!invoices || invoices.length === 0) {
    return (
      <Card variant="glass" className="highest-invoices-card">
        <div className="card-header-bar">
          <div className="header-title-box">
            <div className="header-icon-box gold">
              <Award size={18} />
            </div>
            <div>
              <h3 className="section-title">Highest-Value Invoices</h3>
              <p className="section-desc">Top transactions and large capital expenditures</p>
            </div>
          </div>
        </div>
        <div className="invoices-empty-state">
          <FileText size={32} className="empty-icon" />
          <p>No high-value invoices found matching your current filter criteria.</p>
        </div>
      </Card>
    );
  }

  return (
    <Card variant="glass" className="highest-invoices-card">
      <div className="card-header-bar">
        <div className="header-title-box">
          <div className="header-icon-box gold">
            <Award size={18} />
          </div>
          <div>
            <h3 className="section-title">Highest-Value Invoices</h3>
            <p className="section-desc">
              Top {invoices.length} largest expenses extracted from your document repository
            </p>
          </div>
        </div>
        <span className="invoices-count-badge">Ranked by Value</span>
      </div>

      <div className="invoices-table-container">
        <div className="invoices-table-header">
          <span className="col-rank">Rank</span>
          <span className="col-doc">Invoice &amp; Vendor</span>
          <span className="col-date">Date</span>
          <span className="col-items">Line Items</span>
          <span className="col-amount">Total Amount</span>
          <span className="col-action">Action</span>
        </div>

        <div className="invoices-list-body">
          {invoices.map((inv, idx) => {
            const rank = idx + 1;
            const rankBadgeClass =
              rank === 1
                ? 'rank-gold'
                : rank === 2
                ? 'rank-silver'
                : rank === 3
                ? 'rank-bronze'
                : 'rank-standard';

            return (
              <div
                key={inv.document_id || idx}
                className="invoice-row-card"
                onClick={() => onInspectInvoice && onInspectInvoice(inv.document_id)}
                title="Click to view extraction and OCR document details"
              >
                <div className="col-rank">
                  <span className={`rank-badge ${rankBadgeClass}`}>#{rank}</span>
                </div>

                <div className="col-doc">
                  <div className="doc-avatar-box">
                    <FileText size={16} />
                  </div>
                  <div className="doc-text-block">
                    <span className="doc-vendor-name">
                      {inv.vendor || 'Unknown Vendor'}
                    </span>
                    <span className="doc-meta-sub">
                      {inv.invoice_number ? (
                        <>
                          <Hash size={10} className="inline-icon" />
                          {inv.invoice_number} •{' '}
                        </>
                      ) : null}
                      {inv.filename}
                    </span>
                  </div>
                </div>

                <div className="col-date">
                  <span className="invoice-date-text">
                    {inv.date ? (
                      <>
                        <Calendar size={11} className="inline-icon" />
                        {inv.date}
                      </>
                    ) : (
                      '—'
                    )}
                  </span>
                </div>

                <div className="col-items">
                  <span className="items-count-pill">
                    <Layers size={11} /> {inv.items_count}{' '}
                    {inv.items_count === 1 ? 'item' : 'items'}
                  </span>
                </div>

                <div className="col-amount">
                  <div className="amount-cell">
                    <span className="invoice-total-text">
                      {formatCurrency(inv.total, inv.currency)}
                    </span>
                    {inv.tax != null && inv.tax > 0 && (
                      <span className="invoice-tax-sub">
                        Tax: {formatCurrency(inv.tax, inv.currency)}
                      </span>
                    )}
                  </div>
                </div>

                <div className="col-action">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="inspect-btn"
                    onClick={(e) => {
                      e.stopPropagation();
                      if (onInspectInvoice) onInspectInvoice(inv.document_id);
                    }}
                    icon={<Eye size={13} />}
                  >
                    View
                  </Button>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </Card>
  );
};
