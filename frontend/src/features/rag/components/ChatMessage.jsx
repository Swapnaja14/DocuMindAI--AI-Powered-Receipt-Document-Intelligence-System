import React, { useState } from 'react';
import {
  Bot,
  User as UserIcon,
  Copy,
  Check,
  RotateCw,
  AlertCircle,
  Clock,
  LogIn,
  WifiOff,
} from 'lucide-react';
import { EvidenceDrawer } from './EvidenceDrawer';
import { InsufficientEvidenceBanner } from './InsufficientEvidenceBanner';
import { useNavigate } from 'react-router-dom';
import './ChatMessage.css';

// Simple lightweight markdown/citation formatter for rich answer rendering
const formatAnswerText = (text) => {
  if (!text) return null;

  // Split into paragraphs / lines
  const lines = text.split('\n');

  return lines.map((line, lineIdx) => {
    // Bullet point lines
    const isBullet = line.trim().startsWith('* ') || line.trim().startsWith('- ');
    const cleanedLine = isBullet ? line.trim().substring(2) : line;

    // Highlight citations like [1], [2] and bold **text**
    const parts = cleanedLine.split(/(\[\d+\]|\*\*.*?\*\*)/g);

    const renderedParts = parts.map((part, partIdx) => {
      if (/^\[\d+\]$/.test(part)) {
        return (
          <span key={partIdx} className="inline-citation-tag">
            {part}
          </span>
        );
      }
      if (part.startsWith('**') && part.endsWith('**')) {
        return (
          <strong key={partIdx} className="inline-strong">
            {part.slice(2, -2)}
          </strong>
        );
      }
      return part;
    });

    if (isBullet) {
      return (
        <li key={lineIdx} className="chat-bullet-item">
          {renderedParts}
        </li>
      );
    }

    if (!line.trim()) {
      return <div key={lineIdx} className="chat-empty-spacer" />;
    }

    return (
      <p key={lineIdx} className="chat-paragraph">
        {renderedParts}
      </p>
    );
  });
};

export const ChatMessage = ({ message, onRetry, onOpenSettings }) => {
  const isUser = message.role === 'user';
  const [isCopied, setIsCopied] = useState(false);
  const navigate = useNavigate();

  const handleCopy = async () => {
    if (!message.content) return;
    try {
      await navigator.clipboard.writeText(message.content);
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), 2000);
    } catch (err) {
      console.warn('Copy failed:', err);
    }
  };

  const formattedTime = message.timestamp
    ? new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : '';

  return (
    <div
      className={`chat-message-row ${isUser ? 'user-row' : 'assistant-row'} animate-fade-in`}
      role="article"
      aria-label={`${isUser ? 'User question' : 'Assistant answer'}`}
    >
      <div className={`message-avatar ${isUser ? 'user-avatar' : 'assistant-avatar'}`}>
        {isUser ? <UserIcon size={17} /> : <Bot size={18} className="bot-glow-icon" />}
      </div>

      <div className={`message-bubble-wrapper ${isUser ? 'user-bubble-wrapper' : 'assistant-bubble-wrapper'}`}>
        {/* Author & Timestamp Header */}
        <div className="message-header">
          <span className="author-name">{isUser ? 'You' : 'DocuMind Intelligence'}</span>
          <span className="message-timestamp">{formattedTime}</span>
          {message.latencyMs && (
            <span className="latency-badge" title="Response generation latency">
              <Clock size={11} />
              {(message.latencyMs / 1000).toFixed(1)}s
            </span>
          )}
        </div>

        {/* Message Content Bubble */}
        <div
          className={`message-bubble ${
            isUser
              ? 'user-bubble'
              : message.status === 'error'
              ? 'error-bubble'
              : 'assistant-bubble'
          }`}
        >
          {/* Loading / Generating State */}
          {message.status === 'loading' && (
            <div className="thinking-indicator">
              <div className="pulsing-dots">
                <span className="dot" />
                <span className="dot" />
                <span className="dot" />
              </div>
              <span className="thinking-text">
                Searching vector index and grounding answer with Gemini...
              </span>
            </div>
          )}

          {/* Cancelled State */}
          {message.status === 'cancelled' && (
            <p className="cancelled-text">{message.content}</p>
          )}

          {/* Error State */}
          {message.status === 'error' && (
            <div className="error-message-content">
              <div className="error-header-row">
                {message.error?.isNetworkError ? (
                  <WifiOff size={18} className="error-icon" />
                ) : (
                  <AlertCircle size={18} className="error-icon" />
                )}
                <span className="error-title">
                  {message.error?.isSessionExpired
                    ? 'Session Expired'
                    : message.error?.isNetworkError
                    ? 'Connection Error'
                    : message.error?.isRateLimit
                    ? 'Rate Limit Reached'
                    : 'Query Failed'}
                </span>
              </div>
              <p className="error-description">{message.error?.message}</p>

              <div className="error-actions-row">
                {message.error?.isSessionExpired ? (
                  <button
                    type="button"
                    className="error-action-btn primary"
                    onClick={() => navigate('/login')}
                  >
                    <LogIn size={14} />
                    <span>Sign In Again</span>
                  </button>
                ) : (
                  onRetry && (
                    <button
                      type="button"
                      className="error-action-btn retry"
                      onClick={() => onRetry(message.id)}
                    >
                      <RotateCw size={14} />
                      <span>Retry Question</span>
                    </button>
                  )
                )}
              </div>
            </div>
          )}

          {/* Success Content State */}
          {message.status === 'success' && (
            <>
              <div className="formatted-answer-body">
                {formatAnswerText(message.content)}
              </div>

              {/* Insufficient Evidence Notice */}
              {message.isInsufficientEvidence && (
                <InsufficientEvidenceBanner onOpenSettings={onOpenSettings} />
              )}

              {/* Grounded Evidence Drawer */}
              {message.sources && message.sources.length > 0 && (
                <EvidenceDrawer
                  sources={message.sources}
                  retrieval={message.retrieval}
                />
              )}
            </>
          )}
        </div>

        {/* Action Toolbar on Assistant Messages */}
        {!isUser && message.status === 'success' && (
          <div className="message-toolbar">
            <button
              type="button"
              className="toolbar-btn"
              onClick={handleCopy}
              title="Copy answer text"
              aria-label="Copy answer text"
            >
              {isCopied ? (
                <>
                  <Check size={13} className="text-success" />
                  <span>Copied</span>
                </>
              ) : (
                <>
                  <Copy size={13} />
                  <span>Copy answer</span>
                </>
              )}
            </button>
          </div>
        )}
      </div>
    </div>
  );
};
