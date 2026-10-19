import { apiClient } from './client';

export const ragApi = {
  /**
   * Ask a question against the authenticated user's uploaded documents.
   * @param {Object} params
   * @param {string} params.question - The question to ask (3-2000 chars)
   * @param {number} [params.top_k=5] - Number of top chunks to retrieve (1-10)
   * @param {AbortSignal} [signal] - Optional AbortSignal for request cancellation
   * @returns {Promise<{ answer: string, sources: Array, retrieval: { top_k: number, sources_used: number } }>}
   */
  askQuestion: async ({ question, top_k = 5 }, signal) => {
    return apiClient('/rag/ask', {
      method: 'POST',
      body: JSON.stringify({
        question: question.trim(),
        top_k: Number(top_k) || 5,
      }),
      signal,
    });
  },

  /**
   * Retrieve operational metrics and cache hit-ratio report.
   * @returns {Promise<{ summary: Object, report: string }>}
   */
  getCacheMetrics: async () => {
    return apiClient('/rag/cache/metrics', {
      method: 'GET',
    });
  },
};
