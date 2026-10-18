import { apiClient } from './client';

export const authApi = {
  login: async (credentials) => {
    return apiClient('/auth/login', {
      method: 'POST',
      body: JSON.stringify(credentials),
    });
  },

  register: async (credentials) => {
    return apiClient('/auth/register', {
      method: 'POST',
      body: JSON.stringify(credentials),
    });
  },

  getMe: async () => {
    return apiClient('/users/me', {
      method: 'GET',
    });
  },

  logout: async () => {
    return apiClient('/auth/logout', {
      method: 'POST',
    });
  },
};
