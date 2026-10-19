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
      let errorMessage = '';

      if (data && data.detail) {
        if (typeof data.detail === 'string') {
          errorMessage = data.detail;
        } else if (Array.isArray(data.detail)) {
          // Format FastAPI / Pydantic validation error details cleanly
          errorMessage = data.detail
            .map((d) => {
              const field = Array.isArray(d.loc) ? d.loc.slice(-1)[0] : '';
              const msg = d.msg || (typeof d === 'string' ? d : JSON.stringify(d));
              return field && field !== 'body' ? `${field}: ${msg}` : msg;
            })
            .join('; ');
        } else if (typeof data.detail === 'object') {
          errorMessage = data.detail.message || data.detail.msg || JSON.stringify(data.detail);
        }
      } else if (data && data.message && typeof data.message === 'string' && !data.message.includes('<!DOCTYPE') && !data.message.includes('<html')) {
        errorMessage = data.message;
      } else if (data && data.error && typeof data.error === 'string') {
        errorMessage = data.error;
      }

      // Friendly contextual fallbacks if backend did not supply a readable detail
      if (!errorMessage) {
        switch (response.status) {
          case 400:
            errorMessage = 'Invalid request. Please check your input and try again.';
            break;
          case 401:
            errorMessage = 'Incorrect email or password. Please try again.';
            break;
          case 403:
            errorMessage = 'Access denied. You do not have permission for this action.';
            break;
          case 404:
            errorMessage = 'The requested resource was not found.';
            break;
          case 409:
            errorMessage = 'This email address is already registered. Please sign in instead.';
            break;
          case 422:
            errorMessage = 'Input validation failed. Please check all fields.';
            break;
          case 429:
            errorMessage = 'Too many requests. Please wait a moment before trying again.';
            break;
          case 500:
            errorMessage = 'Server error encountered. Please try again shortly.';
            break;
          case 502:
          case 503:
          case 504:
            errorMessage = 'Backend service is currently unavailable. Please ensure the server is running.';
            break;
          default:
            errorMessage = `Request failed with status ${response.status}. Please try again.`;
            break;
        }
      }

      // If token expired or unauthorized, broadcast event
      if (response.status === 401) {
        window.dispatchEvent(new CustomEvent('documind:unauthorized'));
      }

      console.error(`[API Error ${response.status}] ${url}:`, errorMessage, data);

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
