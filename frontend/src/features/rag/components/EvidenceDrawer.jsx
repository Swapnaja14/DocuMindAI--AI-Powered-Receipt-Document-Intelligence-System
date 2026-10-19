import React, { useState } from 'react';
import { BookOpen, ChevronDown, ChevronUp, Copy, Check, FileText } from 'lucide-react';
import './EvidenceDrawer.css';

export const EvidenceDrawer = ({ sources = [], retrieval = null }) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [copiedSnippetId, setCopiedSnippetId] = useState(null);

  if (!sources || sources.length === 0) return null;

  const handleCopySnippet = async (chunkId, text) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedSnippetId(chunkId);
      setTimeout(() => setCopiedSnippetId(null), 2000);
    } catch (err) {
      console.warn('Failed to copy snippet:', err);
    }
  };

  return (
    <div className="evidence-drawer">
      <button
        type="button"
        className="evidence-toggle-btn"
        onClick={() => setIsExpanded((prev) => !prev)}
        aria-expanded={isExpanded}
      >
        <div className="toggle-left">
          <BookOpen size={15} className="evidence-book-icon" />
          <span className="evidence-title">
            Evidence &amp; Citations ({sources.length} {sources.length === 1 ? 'source' : 'sources'})
          </span>
          {retrieval && (
            <span className="retrieval-pill">
              Top-{retrieval.top_k} retrieval
            </span>
          )}
        </div>
        <div className="toggle-right">
          <span className="toggle-hint">{isExpanded ? 'Hide Sources' : 'Show Sources'}</span>
          {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </div>
      </button>

      {isExpanded && (
        <div className="evidence-cards-container animate-fade-in">
          {sources.map((source, idx) => {
            const isCopied = copiedSnippetId === source.chunk_id;
            return (
              <div key={source.chunk_id || idx} className="evidence-card">
                <div className="evidence-card-header">
                  <div className="source-meta-group">
                    <span className="citation-badge">[{idx + 1}]</span>
                    <FileText size={14} className="doc-icon" />
                    <span className="source-filename" title={source.filename}>
                      {source.filename || 'Document'}
                    </span>
                    {source.page != null && (
                      <span className="source-page-tag">
                        Page {source.page}
                      </span>
                    )}
                  </div>

                  <button
                    type="button"
                    className="copy-snippet-btn"
                    onClick={() => handleCopySnippet(source.chunk_id, source.snippet)}
                    title="Copy source excerpt"
                  >
                    {isCopied ? (
                      <>
                        <Check size={13} className="text-success" />
                        <span>Copied</span>
                      </>
                    ) : (
                      <>
                        <Copy size={13} />
                        <span>Copy</span>
                      </>
                    )}
                  </button>
                </div>

                <div className="evidence-snippet-body">
                  <p className="snippet-quote">"{source.snippet}"</p>
                </div>

                <div className="evidence-card-footer">
                  <span className="chunk-id-tag">Chunk ID: {source.chunk_id}</span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
