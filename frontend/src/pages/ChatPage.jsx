import React, { useEffect } from 'react';
import { AppLayout } from '../layouts/AppLayout';
import { ChatContainer } from '../features/rag/components/ChatContainer';
import './ChatPage.css';

export const ChatPage = () => {
  useEffect(() => {
    document.title = 'RAG Intelligence Chat | DocuMind AI';
  }, []);

  return (
    <AppLayout>
      <div className="chat-page-layout">
        <ChatContainer />
      </div>
    </AppLayout>
  );
};

export default ChatPage;
