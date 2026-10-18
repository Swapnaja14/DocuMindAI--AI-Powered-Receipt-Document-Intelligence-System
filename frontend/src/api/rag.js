import { apiClient } from './client';

export const ragApi = {
  askQuestion: async (params) => {
    return apiClient('/rag/ask', {
      method: 'POST',
      body: JSON.stringify(params),
    });
  },
};
