import React from 'react';
import { Card } from '../../../components/ui/Card';
import {
  Wallet,
  Receipt,
  Percent,
  Coins,
} from 'lucide-react';
import './ExpenseTotalCards.css';

// Currency symbol helper
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

export const ExpenseTotalCards = ({
  totalExpenses = [],
  overallCount = 0,
}) => {
  if (!totalExpenses || totalExpenses.length === 0) {
    return (
      <Card variant="glass" className="expense-empty-totals-card">
        <div className="empty-totals-inner">
          <div className="empty-totals-icon">
            <Wallet size={24} />
          </div>
          <div>
            <h4 className="empty-totals-title">No Expense Totals Found</h4>
            <p className="empty-totals-desc">
              No receipts with extracted financial totals match your current filter selection.
            </p>
          </div>
        </div>
      </Card>
    );
  }

  return (
    <div className="expense-totals-container">
      <div className="totals-header-row">
        <h3 className="section-heading">
          <Wallet size={18} className="heading-icon" />
          <span>Total Expenses by Currency</span>
        </h3>
        <span className="totals-subtitle">
          {overallCount} receipts analyzed across {totalExpenses.length}{' '}
          {totalExpenses.length === 1 ? 'currency' : 'currencies'}
        </span>
      </div>

      <div className="currency-cards-grid">
        {totalExpenses.map((currTotal, idx) => {
          const isPrimary = idx === 0;
          return (
            <Card
              key={currTotal.currency}
              variant="glass"
              className={`currency-total-card ${isPrimary ? 'primary-currency' : ''}`}
            >
              <div className="card-top-meta">
                <span className="currency-badge">{currTotal.currency}</span>
                <span className="receipt-count-pill">
                  <Receipt size={12} />
                  {currTotal.receipt_count} {currTotal.receipt_count === 1 ? 'invoice' : 'invoices'}
                </span>
              </div>

              <div className="currency-amount-box">
                <div className="amount-label">Total Spend</div>
                <div className="amount-headline">
                  {formatCurrency(currTotal.total_amount, currTotal.currency)}
                </div>
              </div>

              <div className="card-metrics-row">
                <div className="sub-metric">
                  <span className="sub-metric-label">
                    <Percent size={11} /> Tax Included
                  </span>
                  <span className="sub-metric-value">
                    {formatCurrency(currTotal.total_tax, currTotal.currency)}
                  </span>
                </div>

                <div className="sub-metric">
                  <span className="sub-metric-label">
                    <Coins size={11} /> Average / Invoice
                  </span>
                  <span className="sub-metric-value">
                    {formatCurrency(currTotal.average_amount, currTotal.currency)}
                  </span>
                </div>
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
};
