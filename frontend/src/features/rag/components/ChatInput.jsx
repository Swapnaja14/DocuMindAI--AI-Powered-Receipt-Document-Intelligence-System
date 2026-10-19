import React, { useState, useRef, useEffect } from 'react';
import { Send, Square, SlidersHorizontal, Sparkles } from 'lucide-react';
import './ChatInput.css';

const STARTER_PROMPTS = [
  'Which receipt had the highest total amount?',
  'List all purchases related to hardware or laptops.',
  'What is the total expenditure across all my receipts?',
  'Summarize the payment methods and tax amounts found.',
];

export const ChatInput = ({
  onSend,
  isLoading,
  onCancel,
  onOpenSettings,
  topK,
}) => {
  const [question, setQuestion] = useState('');
  const textareaRef = useRef(null);

  // Auto-resize textarea height based on content
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      const scrollHeight = textareaRef.current.scrollHeight;
      textareaRef.current.style.height = `${Math.min(Math.max(scrollHeight, 44), 140)}px`;
    }
  }, [question]);

  const handleSubmit = (e) => {
    if (e) e.preventDefault();
    const trimmed = question.trim();
    if (!trimmed || trimmed.length < 3 || trimmed.length > 2000 || isLoading) return;

    onSend(trimmed);
    setQuestion('');
    if (textareaRef.current) {
      textareaRef.current.style.height = '44px';
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleSelectStarter = (prompt) => {
    if (isLoading) return;
    onSend(prompt);
  };

  const charCount = question.length;
  const isTooShort = charCount > 0 && charCount < 3;
  const isTooLong = charCount > 2000;
  const isValid = charCount >= 3 && charCount <= 2000 && !isLoading;

  return (
    <div className="chat-input-wrapper">
      {/* Starter Prompts Bar (visible when input is empty and not loading) */}
      {!isLoading && question.length === 0 && (
        <div className="starter-prompts-row animate-fade-in" aria-label="Suggested Prompts">
          <div className="starter-label">
            <Sparkles size={13} className="sparkle-icon" />
            <span>Try asking:</span>
          </div>
          <div className="starter-chips-scroll">
            {STARTER_PROMPTS.map((prompt, idx) => (
              <button
                key={idx}
                type="button"
                className="starter-chip"
                onClick={() => handleSelectStarter(prompt)}
              >
                {prompt}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Main Input Form */}
      <form onSubmit={handleSubmit} className="chat-input-form">
        <div className="chat-input-container">
          <textarea
            ref={textareaRef}
            className="chat-textarea"
            placeholder="Ask a question about your uploaded receipts &amp; documents... (Enter to send, Shift+Enter for new line)"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isLoading}
            rows={1}
            maxLength={2100}
            aria-label="Ask a question"
          />

          <div className="chat-input-controls">
            <div className="controls-left">
              <button
                type="button"
                className="settings-toggle-btn"
                onClick={onOpenSettings}
                title="Configure Retrieval Settings (Top-K)"
                aria-label="Configure Retrieval Settings"
              >
                <SlidersHorizontal size={15} />
                <span className="topk-label">Top-{topK}</span>
              </button>

              <span
                className={`char-counter ${
                  isTooLong ? 'char-danger' : isTooShort ? 'char-warning' : ''
                }`}
              >
                {charCount}/2000
              </span>
            </div>

            <div className="controls-right">
              {isLoading ? (
                <button
                  type="button"
                  className="cancel-btn"
                  onClick={onCancel}
                  title="Cancel Generation"
                  aria-label="Cancel Generation"
                >
                  <Square size={14} className="stop-icon" />
                  <span>Stop</span>
                </button>
              ) : (
                <button
                  type="submit"
                  className="send-btn"
                  disabled={!isValid}
                  title={isTooShort ? 'Minimum 3 characters required' : 'Send Question'}
                  aria-label="Send Question"
                >
                  <Send size={16} />
                </button>
              )}
            </div>
          </div>
        </div>
      </form>
    </div>
  );
};
