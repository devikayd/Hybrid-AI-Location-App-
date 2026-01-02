import React, { useState, useRef, useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { MessageCircle, X, Send, Loader2 } from 'lucide-react';
import { useMapStore } from '../stores/mapStore';
import { sendChatMessage } from '../services/api';
import { executeActions } from '../services/actionExecutor';

// Chat bubble button when collapsed
function ChatBubbleButton({ onClick }) {
  return (
    <button
      onClick={onClick}
      className="fixed bottom-4 right-4 w-14 h-14 bg-primary-600 hover:bg-primary-700 text-white rounded-full shadow-lg flex items-center justify-center z-[1000] transition-all hover:scale-105"
      aria-label="Open chat"
    >
      <MessageCircle size={24} />
    </button>
  );
}

// Chat header with title and close button
function ChatHeader({ onClose }) {
  return (
    <div className="flex items-center justify-between px-4 py-3 bg-primary-600 text-white rounded-t-lg">
      <div className="flex items-center gap-2">
        <MessageCircle size={18} />
        <span className="font-medium">Location Assistant</span>
      </div>
      <button
        onClick={onClose}
        className="p-1 hover:bg-primary-700 rounded transition-colors"
        aria-label="Close chat"
      >
        <X size={18} />
      </button>
    </div>
  );
}

// Individual message bubble
function MessageBubble({ message }) {
  const isUser = message.role === 'user';

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-3`}>
      <div
        className={`max-w-[85%] px-3 py-2 rounded-lg text-sm ${
          isUser
            ? 'bg-primary-600 text-white rounded-br-none'
            : 'bg-gray-100 text-gray-800 rounded-bl-none'
        }`}
      >
        {message.content}
      </div>
    </div>
  );
}

// Loading indicator
function TypingIndicator() {
  return (
    <div className="flex justify-start mb-3">
      <div className="bg-gray-100 text-gray-600 px-3 py-2 rounded-lg rounded-bl-none flex items-center gap-2">
        <Loader2 size={14} className="animate-spin" />
        <span className="text-sm">Thinking...</span>
      </div>
    </div>
  );
}

// Message list container
function MessageList({ messages, isLoading }) {
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-1">
      {messages.length === 0 && (
        <div className="text-center text-gray-500 text-sm py-8">
          <p>Ask me about this location!</p>
          <p className="text-xs mt-2 text-gray-400">
            Try: "Is this area safe?" or "What restaurants are nearby?"
          </p>
        </div>
      )}
      {messages.map((msg, idx) => (
        <MessageBubble key={idx} message={msg} />
      ))}
      {isLoading && <TypingIndicator />}
      <div ref={bottomRef} />
    </div>
  );
}

// Chat input field
function ChatInput({ value, onChange, onSend, disabled }) {
  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      onSend();
    }
  };

  return (
    <div className="p-3 border-t border-gray-200">
      <div className="flex items-center gap-2">
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about this location..."
          disabled={disabled}
          className="flex-1 px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent disabled:bg-gray-100 disabled:cursor-not-allowed"
        />
        <button
          onClick={onSend}
          disabled={disabled || !value.trim()}
          className="p-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
          aria-label="Send message"
        >
          <Send size={18} />
        </button>
      </div>
    </div>
  );
}

// Main ChatPanel component
export default function ChatPanel() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [conversationId, setConversationId] = useState(null);

  const { center, zoom, getBbox } = useMapStore();
  const store = useMapStore();
  const queryClient = useQueryClient();

  const handleSend = async () => {
    const trimmedInput = input.trim();
    if (!trimmedInput || isLoading) return;

    // Add user message to history
    const userMessage = { role: 'user', content: trimmedInput };
    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    try {
      // Get current map context
      const bbox = getBbox();
      const mapCenter = { lat: center.lat, lng: center.lon };

      // Call chat API
      const response = await sendChatMessage({
        message: trimmedInput,
        mapCenter,
        bbox,
        zoom,
        conversationId,
      });

      // Save conversation ID for continuity
      if (response.conversation_id) {
        setConversationId(response.conversation_id);
      }

      // Add assistant response to history
      const assistantMessage = {
        role: 'assistant',
        content: response.assistant_text,
      };
      setMessages((prev) => [...prev, assistantMessage]);

      // Execute UI actions if any
      if (response.ui_actions && response.ui_actions.length > 0) {
        executeActions(response.ui_actions, store, queryClient);
      }
    } catch (error) {
      console.error('Chat error:', error);

      // Add error message
      const errorMessage = {
        role: 'assistant',
        content: 'Sorry, I encountered an error. Please try again.',
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  // Collapsed state - show bubble button
  if (!isOpen) {
    return <ChatBubbleButton onClick={() => setIsOpen(true)} />;
  }

  // Expanded state - show chat panel
  return (
    <div className="fixed bottom-4 right-4 w-80 h-[28rem] bg-white rounded-lg shadow-2xl flex flex-col z-[1000] border border-gray-200">
      <ChatHeader onClose={() => setIsOpen(false)} />
      <MessageList messages={messages} isLoading={isLoading} />
      <ChatInput
        value={input}
        onChange={setInput}
        onSend={handleSend}
        disabled={isLoading}
      />
    </div>
  );
}
