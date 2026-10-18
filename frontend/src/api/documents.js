import { apiClient } from './client';

export const documentsApi = {
  getDocuments: async () => {
    return apiClient('/documents', {
      method: 'GET',
    });
  },

  getDocument: async (docId) => {
    return apiClient(`/documents/${docId}`, {
      method: 'GET',
    });
  },

  uploadDocument: async (file) => {
    const formData = new FormData();
    formData.append('file', file);

    return apiClient('/documents/upload', {
      method: 'POST',
      body: formData,
    });
  },

  deleteDocument: async (docId) => {
    return apiClient(`/documents/${docId}`, {
      method: 'DELETE',
    });
  },
};
