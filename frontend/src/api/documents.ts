import { apiClient } from './client';

export interface DocumentItem {
  id: string;
  filename: string;
  status: 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED';
  uploaded_at: string;
  extracted_data?: Record<string, any>;
  error_message?: string;
}

export const documentsApi = {
  getDocuments: async (): Promise<DocumentItem[]> => {
    return apiClient<DocumentItem[]>('/documents', {
      method: 'GET',
    });
  },

  getDocument: async (docId: string): Promise<DocumentItem> => {
    return apiClient<DocumentItem>(`/documents/${docId}`, {
      method: 'GET',
    });
  },

  uploadDocument: async (file: File): Promise<DocumentItem> => {
    const formData = new FormData();
    formData.append('file', file);

    return apiClient<DocumentItem>('/documents/upload', {
      method: 'POST',
      body: formData,
    });
  },

  deleteDocument: async (docId: string): Promise<{ message: string }> => {
    return apiClient<{ message: string }>(`/documents/${docId}`, {
      method: 'DELETE',
    });
  },
};
