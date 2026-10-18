import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Mail, Lock, AlertCircle, ArrowRight, CheckCircle2 } from 'lucide-react';
import { useAuth } from './AuthContext';
import { Input } from '../../components/ui/Input';
import { Button } from '../../components/ui/Button';
import './AuthForms.css';

export const RegisterForm: React.FC = () => {
  const { register } = useAuth();
  const navigate = useNavigate();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [errors, setErrors] = useState<{
    email?: string;
    password?: string;
    confirmPassword?: string;
    general?: string;
  }>({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Compute real-time password strength score (0 to 4)
  const calculatePasswordStrength = (pwd: string): { score: number; label: string; color: string } => {
    if (!pwd) return { score: 0, label: 'Empty', color: 'transparent' };
    let score = 0;
    if (pwd.length >= 8) score += 1;
    if (/[A-Z]/.test(pwd)) score += 1;
    if (/[a-z]/.test(pwd)) score += 1;
    if (/[0-9]/.test(pwd) || /[^A-Za-z0-9]/.test(pwd)) score += 1;

    switch (score) {
      case 1:
        return { score: 1, label: 'Weak', color: '#EF4444' };
      case 2:
        return { score: 2, label: 'Fair', color: '#F59E0B' };
      case 3:
        return { score: 3, label: 'Good', color: '#3B82F6' };
      case 4:
        return { score: 4, label: 'Strong', color: '#10B981' };
      default:
        return { score: 0, label: 'Weak', color: '#EF4444' };
    }
  };

  const strength = calculatePasswordStrength(password);

  const validate = (): boolean => {
    const newErrors: { email?: string; password?: string; confirmPassword?: string } = {};

    if (!email.trim()) {
      newErrors.email = 'Email address is required';
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      newErrors.email = 'Please enter a valid email address';
    }

    if (!password) {
      newErrors.password = 'Password is required';
    } else if (password.length < 8) {
      newErrors.password = 'Password must be at least 8 characters';
    }

    if (!confirmPassword) {
      newErrors.confirmPassword = 'Confirm your password';
    } else if (password !== confirmPassword) {
      newErrors.confirmPassword = 'Passwords do not match';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;

    setIsSubmitting(true);
    setErrors({});

    try {
      await register({ email: email.trim(), password });
      navigate('/dashboard', { replace: true });
    } catch (err: any) {
      setErrors({
        general: err.message || 'Registration failed. Email may already be in use.',
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <form className="auth-form animate-fade-in" onSubmit={handleSubmit} noValidate>
      <div className="auth-header">
        <h2 className="auth-title">Create an account</h2>
        <p className="auth-subtitle">
          Start processing financial documents and receipts with DocuMind AI
        </p>
      </div>

      {errors.general && (
        <div className="auth-error-banner animate-shake" role="alert">
          <AlertCircle size={18} className="error-icon" />
          <span>{errors.general}</span>
        </div>
      )}

      <div className="auth-fields">
        <Input
          label="Email address"
          type="email"
          placeholder="name@company.com"
          autoComplete="email"
          value={email}
          onChange={(e) => {
            setEmail(e.target.value);
            if (errors.email) setErrors((prev) => ({ ...prev, email: undefined }));
          }}
          error={errors.email}
          leftIcon={<Mail size={18} />}
          disabled={isSubmitting}
          required
        />

        <div className="password-group">
          <Input
            label="Password"
            type="password"
            placeholder="Minimum 8 characters"
            autoComplete="new-password"
            value={password}
            onChange={(e) => {
              setPassword(e.target.value);
              if (errors.password) setErrors((prev) => ({ ...prev, password: undefined }));
            }}
            error={errors.password}
            leftIcon={<Lock size={18} />}
            showPasswordToggle
            disabled={isSubmitting}
            required
          />

          {password && (
            <div className="password-strength-container">
              <div className="strength-meter">
                {[1, 2, 3, 4].map((step) => (
                  <div
                    key={step}
                    className="strength-bar"
                    style={{
                      backgroundColor: step <= strength.score ? strength.color : 'rgba(255, 255, 255, 0.1)',
                    }}
                  />
                ))}
              </div>
              <span className="strength-label" style={{ color: strength.color }}>
                {strength.label} password
              </span>
            </div>
          )}
        </div>

        <Input
          label="Confirm password"
          type="password"
          placeholder="Re-enter your password"
          autoComplete="new-password"
          value={confirmPassword}
          onChange={(e) => {
            setConfirmPassword(e.target.value);
            if (errors.confirmPassword) setErrors((prev) => ({ ...prev, confirmPassword: undefined }));
          }}
          error={errors.confirmPassword}
          leftIcon={<CheckCircle2 size={18} />}
          showPasswordToggle
          disabled={isSubmitting}
          required
        />
      </div>

      <Button
        type="submit"
        variant="primary"
        size="lg"
        isLoading={isSubmitting}
        className="auth-submit-btn"
        icon={<ArrowRight size={18} />}
      >
        Create Account & Get Started
      </Button>

      <p className="auth-footer-text">
        Already have an account?{' '}
        <Link to="/login" className="auth-link">
          Sign in
        </Link>
      </p>
    </form>
  );
};
