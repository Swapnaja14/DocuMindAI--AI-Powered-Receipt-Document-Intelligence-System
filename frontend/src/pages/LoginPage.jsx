import React from 'react';
import { AuthLayout } from '../layouts/AuthLayout';
import { LoginForm } from '../features/auth/LoginForm';

export const LoginPage = () => {
  return (
    <AuthLayout>
      <LoginForm />
    </AuthLayout>
  );
};
