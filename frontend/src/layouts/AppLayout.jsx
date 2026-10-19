import React, { useState, useEffect } from 'react';
import { useNavigate, NavLink, useLocation } from 'react-router-dom';
import { useAuth } from '../features/auth/AuthContext';
import {
  FileText,
  LogOut,
  User as UserIcon,
  Shield,
  LayoutDashboard,
  Files,
  Sparkles,
  TrendingUp,
  Menu,
  X,
} from 'lucide-react';
import { Button } from '../components/ui/Button';
import './AppLayout.css';

export const AppLayout = ({ children }) => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  // Close mobile drawer on route change
  useEffect(() => {
    setIsMobileMenuOpen(false);
  }, [location.pathname]);

  // Close mobile menu on Escape key
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && isMobileMenuOpen) {
        setIsMobileMenuOpen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isMobileMenuOpen]);

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
      {/* Accessible Skip Navigation Link */}
      <a href="#main-content" className="skip-nav-link">
        Skip to main content
      </a>

      {/* Top Navigation Bar */}
      <header className="app-navbar" role="banner">
        <div className="navbar-container">
          <div className="navbar-left-group">
            <div
              className="navbar-brand"
              onClick={() => navigate('/dashboard')}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  navigate('/dashboard');
                }
              }}
              aria-label="DocuMind AI Workspace Home"
            >
              <div className="navbar-logo-icon" aria-hidden="true">
                <FileText size={20} />
              </div>
              <span className="navbar-brand-text">DocuMind AI</span>
            </div>

            {/* Desktop Navigation Links */}
            <nav className="navbar-nav-links desktop-only" aria-label="Main Navigation">
              <NavLink
                to="/dashboard"
                className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
              >
                <LayoutDashboard size={16} aria-hidden="true" />
                <span>Dashboard</span>
              </NavLink>
              <NavLink
                to="/documents"
                className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
              >
                <Files size={16} aria-hidden="true" />
                <span>Documents</span>
              </NavLink>
              <NavLink
                to="/chat"
                className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
              >
                <Sparkles size={16} aria-hidden="true" />
                <span>AI Chat</span>
              </NavLink>
              <NavLink
                to="/expenses"
                className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
              >
                <TrendingUp size={16} aria-hidden="true" />
                <span>Expenses</span>
              </NavLink>
            </nav>
          </div>

          <div className="navbar-right-group">
            {/* Desktop User Actions */}
            <div className="navbar-user-actions desktop-only">
              {user && (
                <div className="user-profile-badge" aria-label={`Logged in as ${user.email}`}>
                  <div className="user-avatar" aria-hidden="true">
                    <UserIcon size={16} />
                  </div>
                  <div className="user-details">
                    <span className="user-email">{user.email}</span>
                    <span className="user-role-chip">
                      <Shield size={10} aria-hidden="true" />
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
                aria-label="Sign out of your session"
              >
                Sign out
              </Button>
            </div>

            {/* Mobile Hamburger Toggle Button */}
            <button
              type="button"
              className="mobile-menu-toggle"
              onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
              aria-label={isMobileMenuOpen ? 'Close navigation menu' : 'Open navigation menu'}
              aria-expanded={isMobileMenuOpen}
              aria-controls="mobile-navigation-drawer"
            >
              {isMobileMenuOpen ? <X size={22} /> : <Menu size={22} />}
            </button>
          </div>
        </div>

        {/* Mobile Navigation Drawer */}
        {isMobileMenuOpen && (
          <div
            id="mobile-navigation-drawer"
            className="mobile-nav-drawer animate-slide-up"
            role="navigation"
            aria-label="Mobile Navigation"
          >
            <div className="mobile-nav-links">
              <NavLink
                to="/dashboard"
                className={({ isActive }) => `mobile-nav-link ${isActive ? 'active' : ''}`}
              >
                <LayoutDashboard size={18} aria-hidden="true" />
                <span>Dashboard</span>
              </NavLink>
              <NavLink
                to="/documents"
                className={({ isActive }) => `mobile-nav-link ${isActive ? 'active' : ''}`}
              >
                <Files size={18} aria-hidden="true" />
                <span>Documents</span>
              </NavLink>
              <NavLink
                to="/chat"
                className={({ isActive }) => `mobile-nav-link ${isActive ? 'active' : ''}`}
              >
                <Sparkles size={18} aria-hidden="true" />
                <span>AI Chat</span>
              </NavLink>
              <NavLink
                to="/expenses"
                className={({ isActive }) => `mobile-nav-link ${isActive ? 'active' : ''}`}
              >
                <TrendingUp size={18} aria-hidden="true" />
                <span>Expenses</span>
              </NavLink>
            </div>

            <div className="mobile-nav-footer">
              {user && (
                <div className="mobile-user-info">
                  <div className="user-avatar" aria-hidden="true">
                    <UserIcon size={16} />
                  </div>
                  <div className="user-details">
                    <span className="user-email">{user.email}</span>
                    <span className="user-role-chip">
                      <Shield size={10} aria-hidden="true" />
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
                className="mobile-logout-btn"
              >
                Sign out
              </Button>
            </div>
          </div>
        )}
      </header>

      {/* Main Content Viewport */}
      <main id="main-content" className="app-main-content" tabIndex={-1}>
        <div className="content-container animate-fade-in">
          {children}
        </div>
      </main>
    </div>
  );
};

export default AppLayout;
