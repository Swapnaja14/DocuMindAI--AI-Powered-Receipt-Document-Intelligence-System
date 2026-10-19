import React, { useState } from 'react';
import { Card } from '../../../components/ui/Card';
import {
  Building2,
  Calendar,
  Receipt,
  Search,
} from 'lucide-react';
import './ExpensesByVendor.css';

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

export const ExpensesByVendor = ({
  vendors = [],
  onSelectVendor,
}) => {
  const [searchTerm, setSearchTerm] = useState('');

  const filteredVendors = vendors.filter((v) =>
    v.vendor.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <Card variant="glass" className="expenses-by-vendor-card">
      <div className="card-header-bar">
        <div className="header-title-box">
          <div className="header-icon-box purple">
            <Building2 size={18} />
          </div>
          <div>
            <h3 className="section-title">Expenses by Vendor</h3>
            <p className="section-desc">
              Vendor distribution and share of total commercial spend
            </p>
          </div>
        </div>

        {vendors.length > 5 && (
          <div className="vendor-search-mini">
            <Search size={14} className="search-icon" />
            <input
              type="text"
              placeholder="Filter vendors..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="mini-search-input"
            />
          </div>
        )}
      </div>

      {vendors.length === 0 ? (
        <div className="vendor-empty-state">
          <Building2 size={32} className="empty-icon" />
          <p>No vendor expense records available for this filter range.</p>
        </div>
      ) : filteredVendors.length === 0 ? (
        <div className="vendor-empty-state">
          <p>No vendors matching "{searchTerm}".</p>
        </div>
      ) : (
        <div className="vendor-list-container">
          <div className="vendor-table-header">
            <span>Vendor / Merchant</span>
            <span className="col-invoices">Invoices</span>
            <span className="col-date">Last Active</span>
            <span className="col-share">Share</span>
            <span className="col-total">Total Spent</span>
          </div>

          <div className="vendor-rows-list">
            {filteredVendors.map((item, idx) => (
              <div
                key={`${item.vendor}-${item.currency}-${idx}`}
                className="vendor-row"
                onClick={() => onSelectVendor && onSelectVendor(item.vendor)}
                title={onSelectVendor ? `Filter by ${item.vendor}` : undefined}
                style={{ cursor: onSelectVendor ? 'pointer' : 'default' }}
              >
                <div className="vendor-info-col">
                  <div className="vendor-avatar">
                    {item.vendor.charAt(0).toUpperCase()}
                  </div>
                  <div>
                    <span className="vendor-name-text">{item.vendor}</span>
                    <span className="vendor-currency-sub">{item.currency}</span>
                  </div>
                </div>

                <div className="col-invoices">
                  <span className="invoice-count-badge">
                    <Receipt size={11} /> {item.receipt_count}
                  </span>
                </div>

                <div className="col-date">
                  <span className="vendor-date-text">
                    {item.latest_date ? (
                      <>
                        <Calendar size={11} className="date-icon" />
                        {item.latest_date}
                      </>
                    ) : (
                      '—'
                    )}
                  </span>
                </div>

                <div className="col-share">
                  <div className="share-cell">
                    <div className="progress-bar-bg">
                      <div
                        className="progress-bar-fill"
                        style={{
                          width: `${Math.min(100, Math.max(4, item.percentage_of_currency))}%`,
                        }}
                      />
                    </div>
                    <span className="share-percent">
                      {item.percentage_of_currency}%
                    </span>
                  </div>
                </div>

                <div className="col-total">
                  <span className="vendor-total-amount">
                    {formatCurrency(item.total_amount, item.currency)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
};
