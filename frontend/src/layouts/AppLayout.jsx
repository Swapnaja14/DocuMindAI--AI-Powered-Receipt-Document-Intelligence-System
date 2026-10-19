import React, { useState } from 'react';
import { useNavigate, NavLink } from 'react-router-dom';
import { useAuth } from '../features/auth/AuthContext';
import { FileText, LogOut, User as UserIcon, Shield, LayoutDashboard, Files, Sparkles, TrendingUp } from 'lucide-react';
import { Button } from '../components/ui/Button';
import './AppLayout.css';

export const AppLayout = ({ children }) => {
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
          <div className="navbar-left-group">
            <div className="navbar-brand" onClick={() => navigate('/dashboard')} style={{ cursor: 'pointer' }}>
              <div className="navbar-logo-icon">
                <FileText size={20} />
              </div>
              <span className="navbar-brand-text">DocuMind AI</span>
            </div>

            {/* Application Main Navigation Links */}
            <nav className="navbar-nav-links" aria-label="Main Navigation">
              <NavLink
                to="/dashboard"
                className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
              >
                <LayoutDashboard size={16} />
                <span>Dashboard</span>
              </NavLink>
              <NavLink
                to="/documents"
                className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
              >
                <Files size={16} />
                <span>Documents</span>
              </NavLink>
              <NavLink
                to="/chat"
                className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
              >
                <Sparkles size={16} />
                <span>AI Chat</span>
              </NavLink>
              <NavLink
                to="/expenses"
                className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
              >
                <TrendingUp size={16} />
                <span>Expenses</span>
              </NavLink>
            </nav>
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

export default AppLayout;
