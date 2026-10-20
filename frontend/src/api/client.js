const RAW_BASE_URL = (typeof import.meta !== 'undefined' && import.meta.env?.VITE_API_BASE_URL) || '/api/v1';
export const BASE_URL = RAW_BASE_URL.replace(/\/+$/, '');

export const resolveApiUrl = (endpoint) => {
  if (!endpoint) return BASE_URL;
  if (endpoint.startsWith('http://') || endpoint.startsWith('https://')) {
    return endpoint;
  }
  const cleanEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  return `${BASE_URL}${cleanEndpoint}`;
};

// In-memory token storage (with sessionStorage sync when available)
let activeToken = typeof sessionStorage !== 'undefined' ? sessionStorage.getItem('documind_token') : null;

export const setAuthToken = (token) => {
  activeToken = token;
  if (typeof sessionStorage !== 'undefined') {
    if (token) {
      sessionStorage.setItem('documind_token', token);
    } else {
      sessionStorage.removeItem('documind_token');
    }
  }
};

export const getAuthToken = () => {
  if (activeToken) return activeToken;
  if (typeof sessionStorage !== 'undefined') {
    return sessionStorage.getItem('documind_token');
  }
  return null;
};

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

export async function apiClient(endpoint, options = {}) {
  const maxRetries = options.retries !== undefined ? options.retries : 2;
  const retryDelay = options.retryDelay || 800;
  let attempt = 0;

  while (true) {
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

    const url = resolveApiUrl(endpoint);

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

      // Check if backend is reloading/starting (Vite proxy 503 interception)
      if (
        response.status === 503 &&
        (data?.code === 'BACKEND_STARTING' || data?.code === 'BACKEND_OFFLINE') &&
        attempt < maxRetries
      ) {
        attempt++;
        await sleep(retryDelay * attempt);
        continue;
      }

      if (!response.ok) {
        let errorMessage = '';

        if (
          response.status === 503 &&
          (data?.code === 'BACKEND_STARTING' || data?.code === 'BACKEND_OFFLINE')
        ) {
          errorMessage =
            'Backend server is offline or unreachable on port 8000. Please ensure the backend server is running.';
        } else if (data && data.detail) {
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
        if (response.status === 401 && typeof window !== 'undefined' && typeof window.dispatchEvent === 'function') {
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
      // Transient network / connection error (e.g. connection refused during reload)
      if (attempt < maxRetries) {
        attempt++;
        await sleep(retryDelay * attempt);
        continue;
      }
      // Network / offline error
      throw {
        message: error.message || 'Network connection error. Please ensure the backend server is running.',
        status: 0,
      };
    }
  }
}
