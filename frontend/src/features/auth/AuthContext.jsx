import React, { createContext, useEffect, useState } from 'react';
import { authApi } from '../../api/auth';
import { getAuthToken, setAuthToken } from '../../api/client';

export const AuthContext = createContext(undefined);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(getAuthToken());
  const [isLoading, setIsLoading] = useState(true);

  // Initialize and validate existing token on mount
  useEffect(() => {
    const initializeAuth = async () => {
      const storedToken = getAuthToken();
      if (!storedToken) {
        setIsLoading(false);
        return;
      }

      try {
        const currentUser = await authApi.getMe();
        setUser(currentUser);
        setToken(storedToken);
      } catch {
        // Token expired or invalid
        setAuthToken(null);
        setToken(null);
        setUser(null);
      } finally {
        setIsLoading(false);
      }
    };

    initializeAuth();

    // Listen for unauthorized events emitted by API client
    const handleUnauthorized = () => {
      setAuthToken(null);
      setToken(null);
      setUser(null);
    };

    window.addEventListener('documind:unauthorized', handleUnauthorized);
    return () => {
      window.removeEventListener('documind:unauthorized', handleUnauthorized);
    };
  }, []);

  const login = async (credentials) => {
    const tokenResponse = await authApi.login(credentials);
    setAuthToken(tokenResponse.access_token);
    setToken(tokenResponse.access_token);

    const currentUser = await authApi.getMe();
    setUser(currentUser);
  };

  const register = async (credentials) => {
    // 1. Create account on backend
    await authApi.register(credentials);
    // 2. Automatically log in to establish session
    const tokenResponse = await authApi.login(credentials);
    setAuthToken(tokenResponse.access_token);
    setToken(tokenResponse.access_token);

    const currentUser = await authApi.getMe();
    setUser(currentUser);
  };

  const logout = async () => {
    try {
      if (token) {
        await authApi.logout();
      }
    } catch {
      // Ignore network errors on logout to ensure client state is always cleared
    } finally {
      setAuthToken(null);
      setToken(null);
      setUser(null);
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isAuthenticated: !!user && !!token,
        isLoading,
        login,
        register,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export { useAuth } from './useAuth';
