import React from 'react';
import { AuthLayout } from '../layouts/AuthLayout';
import { RegisterForm } from '../features/auth/RegisterForm';

export const RegisterPage: React.FC = () => {
  return (
    <AuthLayout>
      <RegisterForm />
    </AuthLayout>
  );
};
