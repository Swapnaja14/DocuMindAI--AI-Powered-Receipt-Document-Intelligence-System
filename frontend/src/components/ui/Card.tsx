import React from 'react';
import './Card.css';

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  variant?: 'glass' | 'solid';
  glow?: boolean;
}

export const Card: React.FC<CardProps> = ({
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
