import React from 'react';
import {
  Filter,
  Calendar,
  X,
  RotateCcw,
  Building2,
  FileText,
  DollarSign,
  ChevronDown,
} from 'lucide-react';
import { Card } from '../../../components/ui/Card';
import { Button } from '../../../components/ui/Button';
import './ExpenseFilterBar.css';

export const ExpenseFilterBar = ({
  filters,
  onFilterChange,
  onResetFilters,
  availableCurrencies = [],
  availableVendors = [],
  availableDocuments = [],
  totalMatches = 0,
}) => {
  // Quick date presets
  const handlePreset = (preset) => {
    const today = new Date();
    const yyyy = today.getFullYear();
    const mm = String(today.getMonth() + 1).padStart(2, '0');
    const dd = String(today.getDate()).padStart(2, '0');
    const todayStr = `${yyyy}-${mm}-${dd}`;

    if (preset === 'all') {
      onFilterChange({ startDate: '', endDate: '' });
    } else if (preset === 'this-month') {
      const startOfMonth = `${yyyy}-${mm}-01`;
      onFilterChange({ startDate: startOfMonth, endDate: todayStr });
    } else if (preset === 'last-30') {
      const pastDate = new Date();
      pastDate.setDate(today.getDate() - 30);
      const pastYyyy = pastDate.getFullYear();
      const pastMm = String(pastDate.getMonth() + 1).padStart(2, '0');
      const pastDd = String(pastDate.getDate()).padStart(2, '0');
      onFilterChange({
        startDate: `${pastYyyy}-${pastMm}-${pastDd}`,
        endDate: todayStr,
      });
    } else if (preset === 'this-year') {
      onFilterChange({ startDate: `${yyyy}-01-01`, endDate: todayStr });
    }
  };

  const hasActiveFilters = Boolean(
    filters.startDate ||
      filters.endDate ||
      filters.currency ||
      filters.vendor ||
      (filters.documentIds && filters.documentIds.length > 0)
  );

  return (
    <Card variant="glass" className="expense-filter-card">
      <div className="filter-card-header">
        <div className="filter-title-group">
          <div className="filter-icon-box">
            <Filter size={18} />
          </div>
          <div>
            <h3 className="filter-title">Expense Summary Filters</h3>
            <p className="filter-subtitle">
              Filter by date periods, specific documents, vendors, or currencies
            </p>
          </div>
        </div>

        <div className="filter-header-actions">
          {hasActiveFilters && (
            <Button
              variant="outline"
              size="sm"
              onClick={onResetFilters}
              icon={<RotateCcw size={14} />}
              className="reset-btn"
            >
              Reset Filters
            </Button>
          )}
          <span className="results-count-badge">
            {totalMatches} {totalMatches === 1 ? 'receipt' : 'receipts'} analyzed
          </span>
        </div>
      </div>

      <div className="filter-controls-grid">
        {/* Date Range Inputs */}
        <div className="filter-group date-range-group">
          <label className="filter-label">
            <Calendar size={13} />
            <span>Date Range</span>
          </label>
          <div className="date-inputs-wrapper">
            <div className="input-with-icon">
              <input
                type="date"
                className="filter-date-input"
                value={filters.startDate || ''}
                onChange={(e) => onFilterChange({ startDate: e.target.value })}
                title="Start date"
              />
            </div>
            <span className="date-separator">to</span>
            <div className="input-with-icon">
              <input
                type="date"
                className="filter-date-input"
                value={filters.endDate || ''}
                onChange={(e) => onFilterChange({ endDate: e.target.value })}
                title="End date"
              />
            </div>
          </div>
        </div>

        {/* Currency Filter */}
        <div className="filter-group">
          <label className="filter-label">
            <DollarSign size={13} />
            <span>Currency</span>
          </label>
          <div className="select-wrapper">
            <select
              className="filter-select"
              value={filters.currency || ''}
              onChange={(e) => onFilterChange({ currency: e.target.value })}
            >
              <option value="">All Currencies</option>
              {availableCurrencies.map((curr) => (
                <option key={curr} value={curr}>
                  {curr}
                </option>
              ))}
            </select>
            <ChevronDown size={14} className="select-chevron" />
          </div>
        </div>

        {/* Vendor Search / Filter */}
        <div className="filter-group">
          <label className="filter-label">
            <Building2 size={13} />
            <span>Vendor</span>
          </label>
          <div className="input-with-clear">
            <input
              type="text"
              list="vendor-datalist"
              className="filter-text-input"
              placeholder="Search merchant or vendor..."
              value={filters.vendor || ''}
              onChange={(e) => onFilterChange({ vendor: e.target.value })}
            />
            {availableVendors.length > 0 && (
              <datalist id="vendor-datalist">
                {availableVendors.map((v) => (
                  <option key={v} value={v} />
                ))}
              </datalist>
            )}
            {filters.vendor && (
              <button
                type="button"
                className="clear-input-btn"
                onClick={() => onFilterChange({ vendor: '' })}
                title="Clear vendor"
              >
                <X size={12} />
              </button>
            )}
          </div>
        </div>

        {/* Specific Document Filter */}
        <div className="filter-group">
          <label className="filter-label">
            <FileText size={13} />
            <span>Filter by Document</span>
          </label>
          <div className="select-wrapper">
            <select
              className="filter-select"
              value={filters.documentIds?.[0] || ''}
              onChange={(e) =>
                onFilterChange({
                  documentIds: e.target.value ? [e.target.value] : [],
                })
              }
            >
              <option value="">All Documents ({availableDocuments.length})</option>
              {availableDocuments.map((doc) => (
                <option key={doc.id} value={doc.id}>
                  {doc.filename} {doc.vendor ? `(${doc.vendor})` : ''}
                  {doc.total != null ? ` • ${doc.currency || ''} ${doc.total.toFixed(2)}` : ''}
                </option>
              ))}
            </select>
            <ChevronDown size={14} className="select-chevron" />
          </div>
        </div>
      </div>

      {/* Preset Buttons & Active Chips */}
      <div className="filter-footer-bar">
        <div className="quick-presets">
          <span className="presets-label">Presets:</span>
          <button
            type="button"
            className="preset-chip"
            onClick={() => handlePreset('all')}
          >
            All Time
          </button>
          <button
            type="button"
            className="preset-chip"
            onClick={() => handlePreset('this-month')}
          >
            This Month
          </button>
          <button
            type="button"
            className="preset-chip"
            onClick={() => handlePreset('last-30')}
          >
            Last 30 Days
          </button>
          <button
            type="button"
            className="preset-chip"
            onClick={() => handlePreset('this-year')}
          >
            This Year
          </button>
        </div>

        {hasActiveFilters && (
          <div className="active-filter-chips">
            {filters.startDate && (
              <span className="filter-tag">
                From: {filters.startDate}
                <X
                  size={12}
                  className="tag-remove"
                  onClick={() => onFilterChange({ startDate: '' })}
                />
              </span>
            )}
            {filters.endDate && (
              <span className="filter-tag">
                To: {filters.endDate}
                <X
                  size={12}
                  className="tag-remove"
                  onClick={() => onFilterChange({ endDate: '' })}
                />
              </span>
            )}
            {filters.currency && (
              <span className="filter-tag">
                Currency: {filters.currency}
                <X
                  size={12}
                  className="tag-remove"
                  onClick={() => onFilterChange({ currency: '' })}
                />
              </span>
            )}
            {filters.vendor && (
              <span className="filter-tag">
                Vendor: {filters.vendor}
                <X
                  size={12}
                  className="tag-remove"
                  onClick={() => onFilterChange({ vendor: '' })}
                />
              </span>
            )}
            {filters.documentIds?.length > 0 && (
              <span className="filter-tag">
                Single Document Selected
                <X
                  size={12}
                  className="tag-remove"
                  onClick={() => onFilterChange({ documentIds: [] })}
                />
              </span>
            )}
          </div>
        )}
      </div>
    </Card>
  );
};
