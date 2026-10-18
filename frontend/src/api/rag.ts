import { apiClient } from './client';

export interface RAGAskRequest {
  query: string;
  top_k?: number;
  document_ids?: string[];
  search_mode?: 'semantic' | 'bm25' | 'hybrid';
}

export interface RAGCitations {
  chunk_id: string;
  document_id: string;
  snippet: string;
  similarity_score?: number;
}

export interface RAGAskResponse {
  answer: string;
  citations: RAGCitations[];
  cached?: boolean;
}

export const ragApi = {
  askQuestion: async (params: RAGAskRequest): Promise<RAGAskResponse> => {
    return apiClient<RAGAskResponse>('/rag/ask', {
      method: 'POST',
      body: JSON.stringify(params),
    });
  },
};
