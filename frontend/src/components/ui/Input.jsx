import React, { forwardRef, useState } from 'react';
import { Eye, EyeOff } from 'lucide-react';
import './Input.css';

export const Input = forwardRef(({
  label,
  error,
  helperText,
  leftIcon,
  showPasswordToggle = false,
  type = 'text',
  className = '',
  id,
  ...props
}, ref) => {
  const [showPassword, setShowPassword] = useState(false);
  const inputId = id || (label ? label.toLowerCase().replace(/\s+/g, '-') : undefined);
  const inputType = showPasswordToggle ? (showPassword ? 'text' : 'password') : type;

  return (
    <div className={`input-field-group ${error ? 'has-error' : ''} ${className}`}>
      {label && (
        <label htmlFor={inputId} className="input-label">
          {label}
        </label>
      )}

      <div className="input-wrapper">
        {leftIcon && <span className="input-icon-left">{leftIcon}</span>}

        <input
          ref={ref}
          id={inputId}
          type={inputType}
          className={`input-control ${leftIcon ? 'with-left-icon' : ''} ${showPasswordToggle ? 'with-right-icon' : ''}`}
          aria-invalid={!!error}
          aria-describedby={error ? `${inputId}-error` : undefined}
          {...props}
        />

        {showPasswordToggle && (
          <button
            type="button"
            className="input-password-toggle"
            onClick={() => setShowPassword(!showPassword)}
            aria-label={showPassword ? 'Hide password' : 'Show password'}
          >
            {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
          </button>
        )}
      </div>

      {error ? (
        <p id={`${inputId}-error`} className="input-error-msg animate-shake">
          {error}
        </p>
      ) : helperText ? (
        <p className="input-helper-msg">{helperText}</p>
      ) : null}
    </div>
  );
});

Input.displayName = 'Input';
