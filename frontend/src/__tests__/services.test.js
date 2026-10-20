import { describe, it, expect, vi, beforeEach } from 'vitest';
import * as clientModule from '../api/client';
import { authApi } from '../api/auth';
import { documentsApi } from '../api/documents';
import { expensesApi } from '../api/expenses';
import { ragApi } from '../api/rag';

describe('Frontend API Services Contract Tests', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  describe('authApi', () => {
    it('calls /auth/login with credentials and POST method', async () => {
      const spy = vi.spyOn(clientModule, 'apiClient').mockResolvedValue({
        access_token: 'fake-jwt',
        token_type: 'bearer',
      });

      const res = await authApi.login({ email: 'user@example.com', password: 'Password123!' });
      expect(spy).toHaveBeenCalledWith('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email: 'user@example.com', password: 'Password123!' }),
      });
      expect(res.access_token).toBe('fake-jwt');
    });

    it('calls /auth/register with user data', async () => {
      const spy = vi.spyOn(clientModule, 'apiClient').mockResolvedValue({
        id: 'user-123',
        email: 'user@example.com',
      });

      const res = await authApi.register({ email: 'user@example.com', password: 'Password123!' });
      expect(spy).toHaveBeenCalledWith('/auth/register', {
        method: 'POST',
        body: JSON.stringify({ email: 'user@example.com', password: 'Password123!' }),
      });
      expect(res.id).toBe('user-123');
    });

    it('calls /users/me to fetch current profile', async () => {
      const spy = vi.spyOn(clientModule, 'apiClient').mockResolvedValue({
        id: 'user-123',
        email: 'user@example.com',
      });

      const res = await authApi.getMe();
      expect(spy).toHaveBeenCalledWith('/users/me', { method: 'GET' });
      expect(res.email).toBe('user@example.com');
    });

    it('calls /auth/logout to invalidate backend session', async () => {
      const spy = vi.spyOn(clientModule, 'apiClient').mockResolvedValue({
        message: 'Successfully logged out',
      });

      const res = await authApi.logout();
      expect(spy).toHaveBeenCalledWith('/auth/logout', { method: 'POST' });
      expect(res.message).toBe('Successfully logged out');
    });
  });

  describe('documentsApi', () => {
    it('fetches document list via GET /documents', async () => {
      const docs = [{ id: 'doc-1', filename: 'invoice.pdf' }];
      const spy = vi.spyOn(clientModule, 'apiClient').mockResolvedValue(docs);

      const res = await documentsApi.getDocuments();
      expect(spy).toHaveBeenCalledWith('/documents', { method: 'GET' });
      expect(res).toEqual(docs);
    });

    it('fetches single document status via GET /documents/:id', async () => {
      const doc = { id: 'doc-1', status: 'PROCESSED' };
      const spy = vi.spyOn(clientModule, 'apiClient').mockResolvedValue(doc);

      const res = await documentsApi.getDocument('doc-1');
      expect(spy).toHaveBeenCalledWith('/documents/doc-1', { method: 'GET' });
      expect(res.status).toBe('PROCESSED');
    });

    it('fetches document chunks via GET /documents/:id/chunks', async () => {
      const chunks = [{ chunk_id: 'c1', text: 'Total: $120' }];
      const spy = vi.spyOn(clientModule, 'apiClient').mockResolvedValue(chunks);

      const res = await documentsApi.getDocumentChunks('doc-1');
      expect(spy).toHaveBeenCalledWith('/documents/doc-1/chunks', { method: 'GET' });
      expect(res).toEqual(chunks);
    });

    it('deletes document via DELETE /documents/:id', async () => {
      const spy = vi.spyOn(clientModule, 'apiClient').mockResolvedValue({});

      const res = await documentsApi.deleteDocument('doc-1');
      expect(spy).toHaveBeenCalledWith('/documents/doc-1', { method: 'DELETE' });
      expect(res).toEqual({});
    });
  });

  describe('expensesApi', () => {
    it('constructs filter query string accurately for /expenses/summary', async () => {
      const spy = vi.spyOn(clientModule, 'apiClient').mockResolvedValue({
        total_spend: 450.5,
      });

      await expensesApi.getExpenseSummary({
        startDate: '2026-01-01',
        endDate: '2026-01-31',
        currency: 'USD',
        vendor: 'Acme',
        limitInvoices: 10,
        documentIds: ['doc-1', 'doc-2'],
      });

      expect(spy).toHaveBeenCalledTimes(1);
      const endpoint = spy.mock.calls[0][0];
      expect(endpoint).toContain('/expenses/summary?');
      expect(endpoint).toContain('start_date=2026-01-01');
      expect(endpoint).toContain('end_date=2026-01-31');
      expect(endpoint).toContain('currency=USD');
      expect(endpoint).toContain('vendor=Acme');
      expect(endpoint).toContain('limit_invoices=10');
      expect(endpoint).toContain('document_ids=doc-1%2Cdoc-2');
    });
  });

  describe('ragApi', () => {
    it('dispatches question and top_k parameter to /rag/ask', async () => {
      const mockAnswer = {
        answer: 'The total expense was $1,250 on invoice 104.',
        sources: [
          {
            document_id: 'doc-1',
            filename: 'receipt.pdf',
            page: 1,
            chunk_id: 'chk-1',
            snippet: 'Total: $1,250.00',
          },
        ],
        retrieval: { top_k: 5, sources_used: 1 },
      };

      const spy = vi.spyOn(clientModule, 'apiClient').mockResolvedValue(mockAnswer);

      const res = await ragApi.askQuestion({
        question: 'What was the total invoice cost?',
        top_k: 5,
      });

      expect(spy).toHaveBeenCalledWith('/rag/ask', {
        method: 'POST',
        body: JSON.stringify({
          question: 'What was the total invoice cost?',
          top_k: 5,
        }),
        signal: undefined,
      });
      expect(res.answer).toBe(mockAnswer.answer);
      expect(res.sources).toHaveLength(1);
      expect(res.sources[0].filename).toBe('receipt.pdf');
    });

    it('fetches cache hit metrics from /rag/cache/metrics', async () => {
      const spy = vi.spyOn(clientModule, 'apiClient').mockResolvedValue({
        summary: { total_lookups: 10, cache_hits: 8 },
      });

      const res = await ragApi.getCacheMetrics();
      expect(spy).toHaveBeenCalledWith('/rag/cache/metrics', { method: 'GET' });
      expect(res.summary.cache_hits).toBe(8);
    });
  });
});
