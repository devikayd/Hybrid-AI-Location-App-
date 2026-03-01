import React, { useState, useRef, useEffect } from 'react';
import { useMapStore } from '../stores/mapStore';
import { sendChatMessage } from '../services/api';

const ChatPanel = () => {
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: "Hello! I'm your location assistant. Ask me about any UK location - safety, events, restaurants, or general information!",
      timestamp: new Date()
    }
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const messagesEndRef = useRef(null);

  // Get current location from map store
  const center = useMapStore((s) => s.center);
  const selectedLocation = useMapStore((s) => s.selectedLocation) || center;
  const setLayerVisibility = useMapStore((s) => s.setLayerVisibility);
  const setTripPlan = useMapStore((s) => s.setTripPlan);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage = {
      role: 'user',
      content: input.trim(),
      timestamp: new Date()
    };

    // Add user message to chat
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    try {
      // Send message to backend
      const response = await sendChatMessage({
        message: userMessage.content,
        lat: selectedLocation?.lat ?? center?.lat,
        lon: selectedLocation?.lon ?? center?.lon,
        location_name: selectedLocation?.name
      });

      // Add assistant response
      const assistantMessage = {
        role: 'assistant',
        content: response.response,
        intent: response.intent,
        confidence: response.confidence,
        dataSources: response.data_sources,
        timestamp: new Date()
      };

      setMessages(prev => [...prev, assistantMessage]);

      // Execute any actions (e.g., show map layers)
      if (response.actions && response.actions.length > 0) {
        executeActions(response.actions);
      }

    } catch (error) {
      console.error('Chat error:', error);
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Sorry, I encountered an error. Please try again.',
        isError: true,
        timestamp: new Date()
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  const executeActions = (actions) => {
    actions.forEach(action => {
      if (action.type === 'show_layer' && action.target) {
        const layerMap = {
          'crimes': 'crimes',
          'events': 'events',
          'news': 'news',
          'pois': 'pois'
        };
        const layerName = layerMap[action.target];
        if (layerName && setLayerVisibility) {
          setLayerVisibility(layerName, true);
        }
      } else if (action.type === 'show_trip_plan' && action.params?.stops) {
        // Trip plan returned from chat — push to map store so TripPlanner + TripRouteLayer render it
        setTripPlan({
          stops: action.params.stops,
          total_stops: action.params.stops.length,
          total_duration_text: action.params.total_duration_text || '',
          location_name: action.params.location_name || '',
        });
      }
    });
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const formatTime = (date) => {
    return new Date(date).toLocaleTimeString('en-GB', {
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  // Quick suggestion buttons
  const suggestions = selectedLocation ? [
    "Is this area safe?",
    "What events are nearby?",
    "Find restaurants",
    "Recent news"
  ] : [
    "Is Camden safe at night?",
    "What's happening in Manchester?",
    "Find cafes in Edinburgh",
    "Tell me about Bristol"
  ];

  const handleSuggestion = (suggestion) => {
    setInput(suggestion);
  };

  return (
    <>
      {/* Chat Toggle Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="fixed bottom-4 right-4 z-50 bg-blue-600 hover:bg-blue-700 text-white rounded-full p-4 shadow-lg transition-all duration-300"
        aria-label="Toggle chat"
      >
        {isOpen ? (
          <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        ) : (
          <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="currentColor" viewBox="0 0 24 24">
            <rect x="6" y="7" width="12" height="11" rx="2" fill="currentColor"/>
            <rect x="3" y="10" width="2" height="4" rx="1" fill="currentColor"/>
            <rect x="19" y="10" width="2" height="4" rx="1" fill="currentColor"/>
            <circle cx="9" cy="11" r="1.5" fill="white"/>
            <circle cx="15" cy="11" r="1.5" fill="white"/>
            <rect x="10" y="14" width="4" height="1.5" rx="0.75" fill="white"/>
            <rect x="11" y="4" width="2" height="3" rx="1" fill="currentColor"/>
            <circle cx="12" cy="4" r="1" fill="currentColor"/>
          </svg>
        )}
      </button>

      {/* Chat Panel */}
      {isOpen && (
        <div className="fixed bottom-20 right-4 z-50 w-96 max-w-[calc(100vw-2rem)] bg-white rounded-lg shadow-2xl border border-gray-200 flex flex-col" style={{ height: '500px' }}>
          {/* Header */}
          <div className="bg-blue-600 text-white px-4 py-3 rounded-t-lg flex items-center justify-between">
            <div className="flex items-center gap-2">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
              <span className="font-semibold">Location Assistant</span>
            </div>
            {selectedLocation && (
              <span className="text-xs bg-blue-500 px-2 py-1 rounded">
                {selectedLocation.name || `${selectedLocation.lat?.toFixed(2)}, ${selectedLocation.lon?.toFixed(2)}`}
              </span>
            )}
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-gray-50">
            {messages.map((msg, idx) => (
              <div
                key={idx}
                className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[80%] rounded-lg px-4 py-2 ${
                    msg.role === 'user'
                      ? 'bg-blue-600 text-white'
                      : msg.isError
                      ? 'bg-red-100 text-red-800 border border-red-200'
                      : 'bg-white text-gray-800 border border-gray-200 shadow-sm'
                  }`}
                >
                  <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                  <div className={`text-xs mt-1 ${msg.role === 'user' ? 'text-blue-200' : 'text-gray-400'}`}>
                    {formatTime(msg.timestamp)}
                  </div>
                </div>
              </div>
            ))}

            {isLoading && (
              <div className="flex justify-start">
                <div className="bg-white rounded-lg px-4 py-3 border border-gray-200 shadow-sm">
                  <div className="flex items-center gap-2">
                    <div className="flex space-x-1">
                      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
                    </div>
                    <span className="text-xs text-gray-500">Thinking...</span>
                  </div>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Suggestions - Only show before user sends first message */}
          {messages.length === 1 && (
            <div className="px-4 py-3 border-t border-gray-200 bg-gradient-to-r from-blue-50 to-indigo-50">
              <p className="text-xs font-medium text-gray-600 mb-2">💡 Try asking:</p>
              <div className="flex flex-wrap gap-2">
                {suggestions.map((suggestion, idx) => (
                  <button
                    key={idx}
                    onClick={() => handleSuggestion(suggestion)}
                    className="text-xs bg-white hover:bg-blue-50 text-gray-700 px-3 py-1.5 rounded-full transition-colors shadow-sm border border-gray-200 hover:border-blue-300"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Input */}
          <div className="border-t border-gray-200 p-4 bg-white rounded-b-lg">
            <div className="flex gap-2">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Ask about any UK location..."
                disabled={isLoading}
                className="flex-1 border border-gray-300 rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
              />
              <button
                onClick={handleSend}
                disabled={isLoading || !input.trim()}
                className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white px-4 py-2 rounded-lg transition-colors"
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" transform="rotate(90 12 12)" />
                </svg>
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default ChatPanel;
