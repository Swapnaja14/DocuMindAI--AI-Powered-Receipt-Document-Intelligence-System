import { apiClient } from './client';
import type { AuthTokenResponse, LoginCredentials, RegisterCredentials, User } from '../types/auth';

export const authApi = {
  login: async (credentials: LoginCredentials): Promise<AuthTokenResponse> => {
    return apiClient<AuthTokenResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify(credentials),
    });
  },

  register: async (credentials: RegisterCredentials): Promise<User> => {
    return apiClient<User>('/auth/register', {
      method: 'POST',
      body: JSON.stringify(credentials),
    });
  },

  getMe: async (): Promise<User> => {
    return apiClient<User>('/users/me', {
      method: 'GET',
    });
  },

  logout: async (): Promise<{ message: string }> => {
    return apiClient<{ message: string }>('/auth/logout', {
      method: 'POST',
    });
  },
};
