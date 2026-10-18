import React from 'react';
import './Card.css';

export const Card = ({
  children,
  variant = 'glass',
  glow = false,
  className = '',
  ...props
}) => {
  return (
    <div
      className={`card card-${variant} ${glow ? 'card-glow' : ''} ${className}`}
      {...props}
    >
      {children}
    </div>
  );
};
