import { apiClient, getAuthToken, resolveApiUrl } from './client';

export const documentsApi = {
  /**
   * Fetches the user's document list, sorted by upload date descending.
   */
  getDocuments: async () => {
    return apiClient('/documents', {
      method: 'GET',
    });
  },

  /**
   * Fetches a single document's detailed status and parsed metadata.
   */
  getDocument: async (docId) => {
    return apiClient(`/documents/${docId}`, {
      method: 'GET',
    });
  },

  /**
   * Fetches chunks generated from this document.
   */
  getDocumentChunks: async (docId) => {
    return apiClient(`/documents/${docId}/chunks`, {
      method: 'GET',
    });
  },

  /**
   * Uploads a document with real-time byte progress reporting via XMLHttpRequest.
   * 
   * @param {File} file - PDF or image file
   * @param {Function} [onProgress] - Callback ({ percent, loaded, total })
   * @returns {Promise<Object>} The uploaded document response
   */
  uploadDocument: (file, onProgress) => {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      const formData = new FormData();
      formData.append('file', file);

      const url = resolveApiUrl('/documents/upload');

      xhr.open('POST', url, true);

      // Attach auth token
      const token = getAuthToken();
      if (token) {
        xhr.setRequestHeader('Authorization', `Bearer ${token}`);
      }

      // Track upload progress
      if (xhr.upload && onProgress) {
        xhr.upload.addEventListener('progress', (event) => {
          if (event.lengthComputable) {
            const percent = Math.min(
              100,
              Math.max(0, Math.round((event.loaded / event.total) * 100))
            );
            onProgress({
              percent,
              loaded: event.loaded,
              total: event.total,
            });
          }
        });
      }

      xhr.onload = () => {
        let responseData = null;
        try {
          responseData = xhr.responseText ? JSON.parse(xhr.responseText) : {};
        } catch {
          responseData = { message: xhr.responseText };
        }

        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(responseData);
        } else {
          let errorMessage = 'Failed to upload document.';
          if (responseData?.detail) {
            errorMessage =
              typeof responseData.detail === 'string'
                ? responseData.detail
                : Array.isArray(responseData.detail)
                ? responseData.detail.map((d) => d.msg || JSON.stringify(d)).join(', ')
                : JSON.stringify(responseData.detail);
          } else if (responseData?.message) {
            errorMessage = responseData.message;
          }

          if (xhr.status === 401) {
            window.dispatchEvent(new CustomEvent('documind:unauthorized'));
          }

          reject({
            status: xhr.status,
            message: errorMessage,
            detail: responseData?.detail,
          });
        }
      };

      xhr.onerror = () => {
        reject({
          status: 0,
          message: 'Network error occurred during document upload.',
        });
      };

      xhr.onabort = () => {
        reject({
          status: 0,
          message: 'Upload was aborted.',
        });
      };

      xhr.send(formData);
    });
  },

  /**
   * Deletes a document and its associated chunks / embeddings.
   */
  deleteDocument: async (docId) => {
    return apiClient(`/documents/${docId}`, {
      method: 'DELETE',
    });
  },
};
