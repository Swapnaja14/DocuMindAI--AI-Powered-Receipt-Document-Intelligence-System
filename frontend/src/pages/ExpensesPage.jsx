import React, { useState, useEffect, useCallback } from 'react';
import { AppLayout } from '../layouts/AppLayout';
import { Button } from '../components/ui/Button';
import {
  TrendingUp,
  RefreshCw,
  AlertCircle,
  UploadCloud,
  Loader2,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { expensesApi } from '../api/expenses';
import { ExpenseFilterBar } from '../features/expenses/components/ExpenseFilterBar';
import { ExpenseTotalCards } from '../features/expenses/components/ExpenseTotalCards';
import { ExpensesByVendor } from '../features/expenses/components/ExpensesByVendor';
import { ExpenseTrendsChart } from '../features/expenses/components/ExpenseTrendsChart';
import { HighestValueInvoices } from '../features/expenses/components/HighestValueInvoices';
import { DocumentDetailsModal } from '../features/documents/components/DocumentDetailsModal';
import './ExpensesPage.css';

export const ExpensesPage = () => {
  const navigate = useNavigate();

  const [filters, setFilters] = useState({
    startDate: '',
    endDate: '',
    documentIds: [],
    currency: '',
    vendor: '',
    limitInvoices: 10,
  });

  const [summaryData, setSummaryData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState(null);

  // Modal inspection state
  const [selectedDocId, setSelectedDocId] = useState(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  const fetchSummary = useCallback(
    async (isManualRefresh = false) => {
      if (isManualRefresh) setIsRefreshing(true);
      setError(null);
      try {
        const data = await expensesApi.getExpenseSummary(filters);
        setSummaryData(data);
      } catch (err) {
        setError(err.message || 'Failed to load expense summary data.');
      } finally {
        setIsLoading(false);
        setIsRefreshing(false);
      }
    },
    [filters]
  );

  useEffect(() => {
    fetchSummary();
  }, [fetchSummary]);

  const handleFilterChange = (newFilterPartial) => {
    setFilters((prev) => ({
      ...prev,
      ...newFilterPartial,
    }));
  };

  const handleResetFilters = () => {
    setFilters({
      startDate: '',
      endDate: '',
      documentIds: [],
      currency: '',
      vendor: '',
      limitInvoices: 10,
    });
  };

  const handleInspectInvoice = (docId) => {
    if (docId) {
      setSelectedDocId(docId);
      setIsModalOpen(true);
    }
  };

  const handleVendorSelect = (vendorName) => {
    setFilters((prev) => ({
      ...prev,
      vendor: vendorName,
    }));
  };

  return (
    <AppLayout>
      <div className="expenses-page-view animate-fade-in">
        {/* Page Top Banner */}
        <div className="expenses-hero">
          <div className="hero-text-block">
            <span className="hero-badge">
              <TrendingUp size={14} className="badge-icon" />
              Financial Intelligence
            </span>
            <h1 className="hero-title">Expense Summaries &amp; Analytics</h1>
            <p className="hero-subtitle">
              Audited financial breakdown across your documents: totals by currency, merchant distribution, time-series velocity, and highest-value invoices.
            </p>
          </div>

          <div className="hero-actions">
            <Button
              variant="outline"
              size="sm"
              onClick={() => fetchSummary(true)}
              isLoading={isRefreshing}
              icon={<RefreshCw size={14} />}
            >
              Refresh Data
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={() => navigate('/documents')}
              icon={<UploadCloud size={14} />}
            >
              Upload Receipts
            </Button>
          </div>
        </div>

        {/* Error Notification */}
        {error && (
          <div className="expenses-error-banner animate-fade-in">
            <AlertCircle size={18} />
            <span>{error}</span>
            <Button variant="ghost" size="sm" onClick={() => fetchSummary(true)}>
              Retry
            </Button>
          </div>
        )}

        {/* Filter Controls Bar */}
        <ExpenseFilterBar
          filters={filters}
          onFilterChange={handleFilterChange}
          onResetFilters={handleResetFilters}
          availableCurrencies={summaryData?.available_currencies || []}
          availableVendors={summaryData?.available_vendors || []}
          availableDocuments={summaryData?.available_documents || []}
          totalMatches={summaryData?.overall_document_count || 0}
        />

        {/* Loading State Skeleton */}
        {isLoading && !summaryData ? (
          <div className="expenses-loading-state">
            <Loader2 size={36} className="spinner" />
            <p>Aggregating verified expense summaries across your documents...</p>
          </div>
        ) : (
          <>
            {/* View 1: Total Expenses Partitioned Safely by Currency */}
            <ExpenseTotalCards
              totalExpenses={summaryData?.total_expenses || []}
              overallCount={summaryData?.overall_document_count || 0}
            />

            {/* Split View: Expense Trends Over Time & Expenses by Vendor */}
            <div className="expenses-analytics-grid">
              {/* View 2: Expense Trends over Time */}
              <div className="analytics-col-trends">
                <ExpenseTrendsChart trends={summaryData?.expense_trends || []} />
              </div>

              {/* View 3: Expenses by Vendor */}
              <div className="analytics-col-vendors">
                <ExpensesByVendor
                  vendors={summaryData?.expenses_by_vendor || []}
                  onSelectVendor={handleVendorSelect}
                />
              </div>
            </div>

            {/* View 4: Highest-Value Invoices */}
            <div className="expenses-highest-section">
              <HighestValueInvoices
                invoices={summaryData?.highest_value_invoices || []}
                onInspectInvoice={handleInspectInvoice}
              />
            </div>
          </>
        )}

        {/* Document Inspection Modal */}
        <DocumentDetailsModal
          docId={selectedDocId}
          isOpen={isModalOpen}
          onClose={() => {
            setIsModalOpen(false);
            setSelectedDocId(null);
          }}
        />
      </div>
    </AppLayout>
  );
};
export default ExpensesPage;
