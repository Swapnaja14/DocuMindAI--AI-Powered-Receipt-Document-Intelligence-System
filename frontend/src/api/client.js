const BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1';

// In-memory token storage (with sessionStorage sync to preserve active sessions across tabs/refreshes)
let activeToken = sessionStorage.getItem('documind_token');

export const setAuthToken = (token) => {
  activeToken = token;
  if (token) {
    sessionStorage.setItem('documind_token', token);
  } else {
    sessionStorage.removeItem('documind_token');
  }
};

export const getAuthToken = () => {
  return activeToken || sessionStorage.getItem('documind_token');
};

export async function apiClient(endpoint, options = {}) {
  const token = getAuthToken();
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  // Remove Content-Type for FormData uploads so browser sets boundary automatically
  if (options.body instanceof FormData) {
    delete headers['Content-Type'];
  }

  const url = endpoint.startsWith('http')
    ? endpoint
    : `${BASE_URL}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;

  try {
    const response = await fetch(url, {
      ...options,
      headers,
    });

    // Handle 204 No Content
    if (response.status === 204) {
      return {};
    }

    let data = null;
    const contentType = response.headers.get('content-type');
    if (contentType && contentType.includes('application/json')) {
      data = await response.json();
    } else {
      const text = await response.text();
      data = text ? { message: text } : {};
    }

    if (!response.ok) {
      let errorMessage = 'An unexpected error occurred. Please try again.';

      if (data && data.detail) {
        if (typeof data.detail === 'string') {
          errorMessage = data.detail;
        } else if (Array.isArray(data.detail)) {
          // Format FastAPI validation error details
          errorMessage = data.detail.map((d) => d.msg || JSON.stringify(d)).join(', ');
        }
      } else if (data && data.message) {
        errorMessage = data.message;
      }

      // If token expired or unauthorized, broadcast event
      if (response.status === 401) {
        window.dispatchEvent(new CustomEvent('documind:unauthorized'));
      }

      const error = {
        message: errorMessage,
        status: response.status,
        detail: data?.detail,
      };
      throw error;
    }

    return data;
  } catch (error) {
    if (error.status) {
      throw error;
    }
    // Network / offline error
    throw {
      message: error.message || 'Network connection error. Please ensure the backend server is running.',
      status: 0,
    };
  }
}
