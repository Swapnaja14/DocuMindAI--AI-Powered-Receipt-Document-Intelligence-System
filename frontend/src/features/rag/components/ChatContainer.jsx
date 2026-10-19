import React, { useState, useEffect, useRef } from 'react';
import {
  Sparkles,
  SlidersHorizontal,
  Trash2,
  AlertCircle,
  UploadCloud,
  FileText,
  ShieldCheck,
} from 'lucide-react';
import { useRAGChat } from '../hooks/useRAGChat';
import { ChatMessage } from './ChatMessage';
import { ChatInput } from './ChatInput';
import { ChatSettingsModal } from './ChatSettingsModal';
import { documentsApi } from '../../../api/documents';
import { useNavigate } from 'react-router-dom';
import './ChatContainer.css';

export const ChatContainer = () => {
  const {
    messages,
    isLoading,
    topK,
    setTopK,
    sendMessage,
    retryMessage,
    cancelRequest,
    clearHistory,
  } = useRAGChat();

  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [docCount, setDocCount] = useState(null);
  const [isCheckingDocs, setIsCheckingDocs] = useState(true);
  const messagesEndRef = useRef(null);
  const navigate = useNavigate();

  // Check document availability to provide guidance if 0 documents exist
  useEffect(() => {
    let isMounted = true;
    const fetchDocCount = async () => {
      try {
        const docs = await documentsApi.listDocuments();
        if (isMounted) {
          setDocCount(docs.length);
        }
      } catch (err) {
        console.warn('Could not check document count for chat guidance:', err);
      } finally {
        if (isMounted) {
          setIsCheckingDocs(false);
        }
      }
    };

    fetchDocCount();
    return () => {
      isMounted = false;
    };
  }, []);

  // Smooth auto-scroll to the bottom of the conversation
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  return (
    <div className="chat-container-card animate-fade-in">
      {/* Top Chat Bar */}
      <header className="chat-header">
        <div className="chat-header-left">
          <div className="chat-brand-icon">
            <Sparkles size={20} className="sparkle-primary" />
          </div>
          <div className="chat-title-info">
            <div className="title-row">
              <h1 className="chat-title">DocuMind Intelligence Chat</h1>
              <span className="grounded-badge" title="Grounded RAG active">
                <ShieldCheck size={12} />
                <span>Grounded RAG</span>
              </span>
            </div>
            <p className="chat-subtitle">
              Answers are strictly grounded in your indexed receipts and source documents.
            </p>
          </div>
        </div>

        <div className="chat-header-actions">
          <button
            type="button"
            className="action-icon-btn"
            onClick={() => setIsSettingsOpen(true)}
            title="Retrieval Settings (Top-K)"
            aria-label="Retrieval Settings"
          >
            <SlidersHorizontal size={16} />
            <span className="action-btn-text">Top-{topK}</span>
          </button>

          {messages.length > 0 && (
            <button
              type="button"
              className="action-icon-btn danger"
              onClick={clearHistory}
              title="Clear Conversation History"
              aria-label="Clear Conversation History"
            >
              <Trash2 size={16} />
              <span className="action-btn-text">Clear</span>
            </button>
          )}
        </div>
      </header>

      {/* Zero Documents Banner Warning */}
      {!isCheckingDocs && docCount === 0 && (
        <div className="no-docs-banner animate-fade-in" role="alert">
          <div className="no-docs-content">
            <AlertCircle size={18} className="no-docs-icon" />
            <div className="no-docs-text">
              <span className="no-docs-title">No Documents Uploaded Yet</span>
              <p className="no-docs-desc">
                DocuMind answers questions using evidence from your receipts. Upload your first document to start extracting insights.
              </p>
            </div>
          </div>
          <button
            type="button"
            className="btn-upload-redirect"
            onClick={() => navigate('/documents')}
          >
            <UploadCloud size={15} />
            <span>Go to Documents</span>
          </button>
        </div>
      )}

      {/* Chat Messages Stream Viewport */}
      <div className="chat-viewport" role="log" aria-live="polite">
        {messages.length === 0 ? (
          <div className="chat-empty-hero animate-fade-in">
            <div className="hero-icon-ring">
              <Sparkles size={36} className="hero-sparkle" />
            </div>
            <h2 className="hero-heading">Ask Anything About Your Documents</h2>
            <p className="hero-subheading">
              Our Retrieval-Augmented Generation (RAG) pipeline indexes your receipts into high-dimensional vector embeddings, retrieves exact matches, and provides citations with full transparency.
            </p>

            <div className="hero-features-grid">
              <div className="hero-feature-card">
                <FileText size={20} className="feature-icon" />
                <h3 className="feature-title">Source Citations</h3>
                <p className="feature-desc">Every answer cites the exact receipt filename, page number, and chunk excerpt.</p>
              </div>

              <div className="hero-feature-card">
                <ShieldCheck size={20} className="feature-icon" />
                <h3 className="feature-title">Anti-Hallucination</h3>
                <p className="feature-desc">When evidence is insufficient, DocuMind explicitly refuses to guess false figures.</p>
              </div>

              <div className="hero-feature-card">
                <Sparkles size={20} className="feature-icon" />
                <h3 className="feature-title">Fast Semantic Search</h3>
                <p className="feature-desc">Powered by persistent FAISS vector mapping and Redis acceleration.</p>
              </div>
            </div>
          </div>
        ) : (
          <div className="messages-stream">
            {messages.map((message) => (
              <ChatMessage
                key={message.id}
                message={message}
                onRetry={retryMessage}
                onOpenSettings={() => setIsSettingsOpen(true)}
              />
            ))}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Bottom Sticky Input Dock */}
      <footer className="chat-footer-dock">
        <ChatInput
          onSend={sendMessage}
          isLoading={isLoading}
          onCancel={cancelRequest}
          onOpenSettings={() => setIsSettingsOpen(true)}
          topK={topK}
        />
      </footer>

      {/* Settings Modal */}
      <ChatSettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        topK={topK}
        onChangeTopK={setTopK}
        onClearHistory={clearHistory}
        messageCount={messages.length}
      />
    </div>
  );
};
