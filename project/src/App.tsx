import React, { useState, useRef, useEffect, Fragment } from 'react';
import { ArrowRight, LineChart, Bot, User, Loader2 } from 'lucide-react';

interface Message {
  type: 'user' | 'bot';
  content: string;
  timestamp: Date;
}

const sampleQueries = [
  "What were Apple's revenue numbers in the latest 10-K?",
  "Show me Microsoft's latest earnings call highlights",
  "What did immix biopharma report as revenue for the quarter ended September 30, 2024",
  "Compare Amazon and Walmart's profit margins"
];

// Helper function to render content with clickable links (using matchAll)
const renderMessageContent = (content: string) => {
  const urlRegex = /(https?:\/\/[^\s]+)/g;
  const matches = Array.from(content.matchAll(urlRegex));
  const result: React.ReactNode[] = [];
  let lastIndex = 0;

  matches.forEach((match, i) => {
    const url = match[0];
    const index = match.index!;

    // Add the text segment before the URL
    if (index > lastIndex) {
      result.push(<Fragment key={`text-${i}`}>{content.substring(lastIndex, index)}</Fragment>);
    }

    // Add the clickable URL
    result.push(
      <a
        key={`url-${i}`}
        href={url}
        target="_blank"
        rel="noopener noreferrer"
        className="text-blue-400 hover:text-blue-300 underline"
      >
        Link
      </a>
    );

    lastIndex = index + url.length;
  });

  // Add any remaining text after the last URL
  if (lastIndex < content.length) {
    result.push(<Fragment key="text-last">{content.substring(lastIndex)}</Fragment>);
  }

  // If no matches were found, return the original content
  if (result.length === 0) {
    return content;
  }

  return <>{result}</>; // Wrap multiple nodes in a single Fragment
};

function App() {
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;
    sendMessage(input);
  };

  const sendMessage = async (text: string) => {
    const newUserMessage: Message = { type: 'user', content: text, timestamp: new Date() };
    setInput('');
    setMessages(prev => [...prev, newUserMessage]);
    setIsLoading(true);

    const historyForApi = messages;

    const apiUrl = '/ask'; // Always use the real endpoint

    try {
      const response = await fetch(apiUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          input: text,
          chat_history: historyForApi.map(msg => ({
            type: msg.type,
            content: msg.content,
            timestamp: msg.timestamp.toISOString()
          }))
        }),
      });

      if (!response.ok) {
        let errorDetail = `HTTP error! status: ${response.status}`;
        try {
          const errorJson = await response.json();
          errorDetail = errorJson.detail || errorDetail;
        } catch (jsonError) {
          console.error("Could not parse error JSON:", jsonError);
        }
        throw new Error(errorDetail);
      }

      const data: { output: string } = await response.json();

      setMessages(prev => [...prev, {
        type: 'bot',
        content: data.output,
        timestamp: new Date()
      }]);

    } catch (error) {
      console.error("Failed to fetch response:", error);
      setMessages(prev => [...prev, {
        type: 'bot',
        content: `Sorry, I encountered an error: ${error instanceof Error ? error.message : String(error)}`,
        timestamp: new Date()
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0A0A0A] flex flex-col text-gray-100">
      {/* Header */}
      <div className="bg-[#111111] border-b border-[#222222] p-4 backdrop-blur-xl bg-opacity-80 sticky top-0 z-10">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="bg-gradient-to-br from-blue-500 to-blue-600 p-2 rounded-2xl shadow-lg shadow-blue-500/20">
              <LineChart className="h-6 w-6 text-white" />
            </div>
            <h1 className="text-2xl font-bold bg-gradient-to-r from-blue-400 to-blue-500 text-transparent bg-clip-text">
              FinanceGPT
            </h1>
          </div>
        </div>
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-5xl mx-auto">
          {messages.length === 0 ? (
            <div className="p-6 space-y-8">
              <div className="text-center space-y-6">
                <div className="bg-gradient-to-br from-blue-500/10 to-blue-600/10 p-6 rounded-3xl inline-block backdrop-blur-xl">
                  <LineChart className="h-12 w-12 text-blue-400" />
                </div>
                <h2 className="text-3xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-gray-100 to-gray-300">
                  Financial Research Assistant
                </h2>
                <p className="text-gray-400 max-w-lg mx-auto text-lg leading-relaxed">
                  Ask me anything about SEC filings, earnings calls, financial metrics, or company research.
                </p>
              </div>
              
              <div className="space-y-4">
                <h3 className="text-lg font-medium text-gray-300 text-center">Try asking about:</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {sampleQueries.map((query, index) => (
                    <button
                      key={index}
                      onClick={() => sendMessage(query)}
                      className="p-4 text-left rounded-2xl bg-[#111111] border border-[#222222] hover:border-blue-500/50 hover:bg-[#151515] transition-all duration-200"
                    >
                      <p className="text-sm text-gray-300">{query}</p>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="p-4 space-y-6">
              {messages.map((message, index) => (
                <div
                  key={index}
                  className={`flex items-start space-x-4 animate-in fade-in slide-in-from-bottom duration-300 ${
                    message.type === 'user' ? 'flex-row-reverse space-x-reverse' : ''
                  }`}
                  style={{ animationDelay: `${index * 100}ms` }}
                >
                  <div className={`flex-shrink-0 rounded-full p-2 ${
                    message.type === 'user' 
                      ? 'bg-blue-500' 
                      : 'bg-[#222222]'
                  }`}>
                    {message.type === 'user' 
                      ? <User className="h-4 w-4" /> 
                      : <Bot className="h-4 w-4" />
                    }
                  </div>
                  <div
                    className={`flex-1 rounded-2xl p-4 whitespace-pre-wrap ${
                      message.type === 'user'
                        ? 'bg-blue-500 text-white ml-12'
                        : 'bg-[#111111] border border-[#222222] mr-12'
                    }`}
                  >
                    <div className="text-base leading-relaxed break-words">
                      {renderMessageContent(message.content)}
                    </div>
                    <p className={`text-xs mt-2 ${message.type === 'user' ? 'text-blue-200' : 'text-gray-500'}`}>
                      {message.timestamp.toLocaleTimeString()}
                    </p>
                  </div>
                </div>
              ))}
              {isLoading && (
                <div className="flex items-start space-x-4 animate-in fade-in duration-300">
                  <div className="flex-shrink-0 rounded-full p-2 bg-[#222222]">
                    <Bot className="h-4 w-4" />
                  </div>
                  <div className="flex-1 rounded-2xl p-4 bg-[#111111] border border-[#222222] mr-12 flex items-center space-x-2">
                    <Loader2 className="h-4 w-4 animate-spin text-blue-400" />
                    <span className='text-sm text-gray-400'>Thinking...</span>
                  </div>
                </div>
              )}
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input Area */}
      <div className="border-t border-[#222222] p-4 bg-[#111111] backdrop-blur-xl bg-opacity-80 sticky bottom-0">
        <form onSubmit={handleSubmit} className="max-w-5xl mx-auto">
          <div className="relative">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about any company, financial data, or market research..."
              className="w-full pl-6 pr-12 py-4 bg-[#0A0A0A] border border-[#222222] rounded-2xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-[#333333] transition-all text-gray-100 placeholder-gray-500"
              disabled={isLoading}
            />
            <button
              type="submit"
              disabled={isLoading}
              className="absolute right-3 top-1/2 -translate-y-1/2 p-2 text-gray-400 hover:text-blue-400 transition-colors disabled:opacity-50"
            >
              <ArrowRight className="h-5 w-5" />
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default App;