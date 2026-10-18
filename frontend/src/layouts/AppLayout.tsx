import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../features/auth/AuthContext';
import { FileText, LogOut, User as UserIcon, Shield } from 'lucide-react';
import { Button } from '../components/ui/Button';
import './AppLayout.css';

export const AppLayout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [isLoggingOut, setIsLoggingOut] = useState(false);

  const handleLogout = async () => {
    setIsLoggingOut(true);
    try {
      await logout();
      navigate('/login', { replace: true });
    } finally {
      setIsLoggingOut(false);
    }
  };

  return (
    <div className="app-shell">
      {/* Top Navigation Bar */}
      <header className="app-navbar">
        <div className="navbar-container">
          <div className="navbar-brand" onClick={() => navigate('/dashboard')} style={{ cursor: 'pointer' }}>
            <div className="navbar-logo-icon">
              <FileText size={20} />
            </div>
            <span className="navbar-brand-text">DocuMind AI</span>
          </div>

          <div className="navbar-user-actions">
            {user && (
              <div className="user-profile-badge">
                <div className="user-avatar">
                  <UserIcon size={16} />
                </div>
                <div className="user-details">
                  <span className="user-email">{user.email}</span>
                  <span className="user-role-chip">
                    <Shield size={10} />
                    {user.role}
                  </span>
                </div>
              </div>
            )}

            <Button
              variant="outline"
              size="sm"
              onClick={handleLogout}
              isLoading={isLoggingOut}
              icon={<LogOut size={16} />}
              title="Sign out of your session"
            >
              Sign out
            </Button>
          </div>
        </div>
      </header>

      {/* Main Content Viewport */}
      <main className="app-main-content">
        <div className="content-container animate-fade-in">
          {children}
        </div>
      </main>
    </div>
  );
};
