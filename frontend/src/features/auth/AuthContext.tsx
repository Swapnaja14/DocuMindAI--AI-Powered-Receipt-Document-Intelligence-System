import React, { createContext, useContext, useEffect, useState } from 'react';
import type { AuthContextType, LoginCredentials, RegisterCredentials, User } from '../../types/auth';
import { authApi } from '../../api/auth';
import { getAuthToken, setAuthToken } from '../../api/client';

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(getAuthToken());
  const [isLoading, setIsLoading] = useState<boolean>(true);

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
      } catch (err) {
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

  const login = async (credentials: LoginCredentials) => {
    setIsLoading(true);
    try {
      const tokenResponse = await authApi.login(credentials);
      setAuthToken(tokenResponse.access_token);
      setToken(tokenResponse.access_token);

      const currentUser = await authApi.getMe();
      setUser(currentUser);
    } finally {
      setIsLoading(false);
    }
  };

  const register = async (credentials: RegisterCredentials) => {
    setIsLoading(true);
    try {
      // 1. Create account on backend
      await authApi.register(credentials);
      // 2. Automatically log in to establish session
      const tokenResponse = await authApi.login(credentials);
      setAuthToken(tokenResponse.access_token);
      setToken(tokenResponse.access_token);

      const currentUser = await authApi.getMe();
      setUser(currentUser);
    } finally {
      setIsLoading(false);
    }
  };

  const logout = async () => {
    try {
      if (token) {
        await authApi.logout();
      }
    } catch (err) {
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

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
