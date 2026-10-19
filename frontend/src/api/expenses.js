import { apiClient } from './client';

export const expensesApi = {
  /**
   * Fetches structured financial expense analytics and summaries.
   * Scoped strictly to the authenticated tenant.
   *
   * @param {Object} [filters]
   * @param {string} [filters.startDate] - YYYY-MM-DD
   * @param {string} [filters.endDate] - YYYY-MM-DD
   * @param {string[]} [filters.documentIds] - Specific document IDs
   * @param {string} [filters.currency] - Currency code (e.g. 'USD', 'INR')
   * @param {string} [filters.vendor] - Vendor substring filter
   * @param {number} [filters.limitInvoices] - Max top-value invoices
   * @returns {Promise<Object>}
   */
  getExpenseSummary: async (filters = {}) => {
    const params = new URLSearchParams();

    if (filters.startDate) params.append('start_date', filters.startDate.trim());
    if (filters.endDate) params.append('end_date', filters.endDate.trim());
    if (filters.currency) params.append('currency', filters.currency.trim());
    if (filters.vendor) params.append('vendor', filters.vendor.trim());
    if (filters.limitInvoices) params.append('limit_invoices', String(filters.limitInvoices));

    if (Array.isArray(filters.documentIds) && filters.documentIds.length > 0) {
      params.append('document_ids', filters.documentIds.join(','));
    }

    const queryString = params.toString();
    const endpoint = `/expenses/summary${queryString ? `?${queryString}` : ''}`;

    return apiClient(endpoint, {
      method: 'GET',
    });
  },
};
