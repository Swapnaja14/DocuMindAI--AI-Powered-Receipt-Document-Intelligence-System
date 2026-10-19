import React, { useState } from 'react';
import { Card } from '../../../components/ui/Card';
import {
  TrendingUp,
  Calendar,
} from 'lucide-react';
import './ExpenseTrendsChart.css';

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

// Formats YYYY-MM to readable month year e.g. "Jan 2024"
const formatPeriod = (period) => {
  if (!period || period === 'Undated') return 'Undated';
  const parts = period.split('-');
  if (parts.length >= 2) {
    const year = parts[0];
    const month = parseInt(parts[1], 10) - 1;
    const date = new Date(year, month);
    return date.toLocaleDateString(undefined, { month: 'short', year: 'numeric' });
  }
  return period;
};

export const ExpenseTrendsChart = ({
  trends = [],
}) => {
  const [hoveredPoint, setHoveredPoint] = useState(null);

  if (!trends || trends.length === 0) {
    return (
      <Card variant="glass" className="expense-trends-card">
        <div className="card-header-bar">
          <div className="header-title-box">
            <div className="header-icon-box cyan">
              <TrendingUp size={18} />
            </div>
            <div>
              <h3 className="section-title">Expense Trends Over Time</h3>
              <p className="section-desc">Monthly financial burn and invoice velocity</p>
            </div>
          </div>
        </div>
        <div className="trends-empty-state">
          <Calendar size={32} className="empty-icon" />
          <p>No dated transaction records available to build time-series trends.</p>
        </div>
      </Card>
    );
  }

  // Calculate maximum total amount per currency for proportional bar heights
  const maxAmountsByCurrency = trends.reduce((acc, curr) => {
    acc[curr.currency] = Math.max(acc[curr.currency] || 0, curr.total_amount);
    return acc;
  }, {});

  // Distinct currencies in trends
  const distinctCurrencies = Array.from(new Set(trends.map((t) => t.currency)));

  return (
    <Card variant="glass" className="expense-trends-card">
      <div className="card-header-bar">
        <div className="header-title-box">
          <div className="header-icon-box cyan">
            <TrendingUp size={18} />
          </div>
          <div>
            <h3 className="section-title">Expense Trends Over Time</h3>
            <p className="section-desc">
              Chronological expense velocity across {trends.length} active periods
            </p>
          </div>
        </div>

        {distinctCurrencies.length > 1 && (
          <div className="currency-legend-pills">
            {distinctCurrencies.map((c) => (
              <span key={c} className="legend-chip">
                <span className={`legend-dot dot-${c.toLowerCase()}`} />
                {c}
              </span>
            ))}
          </div>
        )}
      </div>

      <div className="chart-viewport">
        <div className="trend-bars-timeline">
          {trends.map((pt, idx) => {
            const maxForCurr = maxAmountsByCurrency[pt.currency] || 1;
            const barHeightPct = Math.max(
              12,
              Math.min(100, Math.round((pt.total_amount / maxForCurr) * 100))
            );
            const isHovered = hoveredPoint === idx;

            return (
              <div
                key={`${pt.period}-${pt.currency}-${idx}`}
                className="trend-bar-column"
                onMouseEnter={() => setHoveredPoint(idx)}
                onMouseLeave={() => setHoveredPoint(null)}
              >
                {/* Tooltip on hover */}
                {isHovered && (
                  <div className="bar-floating-tooltip">
                    <span className="tooltip-period">{formatPeriod(pt.period)}</span>
                    <strong className="tooltip-amount">
                      {formatCurrency(pt.total_amount, pt.currency)}
                    </strong>
                    <span className="tooltip-count">
                      {pt.receipt_count} {pt.receipt_count === 1 ? 'receipt' : 'receipts'}
                    </span>
                  </div>
                )}

                <div className="bar-track">
                  <div
                    className={`bar-fill bar-${pt.currency.toLowerCase()} ${isHovered ? 'hovered' : ''}`}
                    style={{ height: `${barHeightPct}%` }}
                  >
                    <span className="bar-amount-label">
                      {formatCurrency(pt.total_amount, pt.currency)}
                    </span>
                  </div>
                </div>

                <div className="bar-x-label">
                  <span className="period-text">{formatPeriod(pt.period)}</span>
                  <span className="currency-sub-pill">{pt.currency}</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </Card>
  );
};
