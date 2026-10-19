import { useState, useEffect, useRef, useCallback } from 'react';
import { ragApi } from '../../../api/rag';
import { useAuth } from '../../auth/AuthContext';

const INSUFFICIENT_EVIDENCE_PHRASES = [
  "couldn't find sufficient relevant evidence",
  "couldn't establish a sufficiently supported answer",
  "no relevant documents found",
  "insufficient evidence",
];

const checkIsInsufficientEvidence = (answer = '', sources = []) => {
  if (!sources || sources.length === 0) return true;
  const lower = answer.toLowerCase();
  return INSUFFICIENT_EVIDENCE_PHRASES.some((phrase) => lower.includes(phrase));
};

export const useRAGChat = () => {
  const { user } = useAuth();
  const storageKey = `documind_rag_chat_${user?.id || user?._id || 'default'}`;

  const [messages, setMessages] = useState(() => {
    try {
      const saved = localStorage.getItem(storageKey);
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  const [isLoading, setIsLoading] = useState(false);
  const [topK, setTopK] = useState(5);
  const abortControllerRef = useRef(null);

  // Sync messages to localStorage whenever they change
  useEffect(() => {
    try {
      localStorage.setItem(storageKey, JSON.stringify(messages));
    } catch (err) {
      console.warn('Failed to persist chat messages to localStorage:', err);
    }
  }, [messages, storageKey]);

  // Cleanup abort controller on unmount
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  const clearHistory = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setMessages([]);
    setIsLoading(false);
    try {
      localStorage.removeItem(storageKey);
    } catch {
      // ignore storage failure
    }
  }, [storageKey]);

  const cancelRequest = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
      setIsLoading(false);

      setMessages((prev) => {
        const lastMsg = prev[prev.length - 1];
        if (lastMsg && lastMsg.role === 'assistant' && lastMsg.status === 'loading') {
          return [
            ...prev.slice(0, -1),
            {
              ...lastMsg,
              status: 'cancelled',
              content: 'Question cancelled by user.',
            },
          ];
        }
        return prev;
      });
    }
  }, []);

  const sendMessage = useCallback(
    async (questionText, customTopK) => {
      const trimmed = questionText?.trim();
      if (!trimmed || trimmed.length < 3 || isLoading) return;

      const chosenTopK = customTopK !== undefined ? customTopK : topK;

      // Abort any existing in-flight request
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      const controller = new AbortController();
      abortControllerRef.current = controller;

      const userMsgId = `user_${Date.now()}`;
      const assistantMsgId = `asst_${Date.now() + 1}`;
      const now = new Date().toISOString();

      const userMsg = {
        id: userMsgId,
        role: 'user',
        content: trimmed,
        timestamp: now,
        status: 'success',
      };

      const pendingAsstMsg = {
        id: assistantMsgId,
        role: 'assistant',
        content: '',
        timestamp: now,
        status: 'loading',
        sources: [],
        retrieval: null,
        isInsufficientEvidence: false,
        questionAsked: trimmed,
        topKUsed: chosenTopK,
      };

      setMessages((prev) => [...prev, userMsg, pendingAsstMsg]);
      setIsLoading(true);

      const startTime = performance.now();

      try {
        const response = await ragApi.askQuestion(
          {
            question: trimmed,
            top_k: chosenTopK,
          },
          controller.signal
        );

        const latencyMs = Math.round(performance.now() - startTime);
        const isInsufficient = checkIsInsufficientEvidence(
          response.answer,
          response.sources
        );

        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantMsgId
              ? {
                  ...msg,
                  content: response.answer || '',
                  sources: response.sources || [],
                  retrieval: response.retrieval || {
                    top_k: chosenTopK,
                    sources_used: (response.sources || []).length,
                  },
                  isInsufficientEvidence: isInsufficient,
                  latencyMs,
                  status: 'success',
                }
              : msg
          )
        );
      } catch (err) {
        if (err.name === 'AbortError' || controller.signal.aborted) {
          // Handled in cancelRequest
          return;
        }

        const latencyMs = Math.round(performance.now() - startTime);
        const isSessionExpired = err.status === 401;
        const isNetwork = err.status === 0 || !navigator.onLine;
        const isRateLimit = err.status === 429;

        let friendlyErrorMsg = err.message || 'An unexpected error occurred while generating the answer.';
        if (isSessionExpired) {
          friendlyErrorMsg = 'Your session has expired. Please sign in again to continue asking questions.';
        } else if (isNetwork) {
          friendlyErrorMsg = 'Unable to reach the server. Please check your network connection and verify the backend is running.';
        } else if (isRateLimit) {
          friendlyErrorMsg = 'Rate limit reached. Please wait a moment before sending another query.';
        }

        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantMsgId
              ? {
                  ...msg,
                  content: '',
                  status: 'error',
                  latencyMs,
                  error: {
                    message: friendlyErrorMsg,
                    status: err.status,
                    isSessionExpired,
                    isNetworkError: isNetwork,
                    isRateLimit,
                  },
                }
              : msg
          )
        );
      } finally {
        setIsLoading(false);
        abortControllerRef.current = null;
      }
    },
    [isLoading, topK]
  );

  const retryMessage = useCallback(
    (assistantMsgId) => {
      const targetMsg = messages.find((m) => m.id === assistantMsgId);
      if (!targetMsg || !targetMsg.questionAsked) return;

      // Remove the failed assistant message and re-send the question
      setMessages((prev) => prev.filter((m) => m.id !== assistantMsgId));
      sendMessage(targetMsg.questionAsked, targetMsg.topKUsed);
    },
    [messages, sendMessage]
  );

  return {
    messages,
    isLoading,
    topK,
    setTopK,
    sendMessage,
    retryMessage,
    cancelRequest,
    clearHistory,
  };
};
