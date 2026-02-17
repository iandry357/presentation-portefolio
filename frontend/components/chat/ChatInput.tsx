
'use client';

import { useState, KeyboardEvent } from 'react';
import { Send } from 'lucide-react';

interface ChatInputProps {
  onSend: (message: string) => void;
  disabled: boolean;
  questionsCount: number;
  questionsRemaining: number;
}

export default function ChatInput({
  onSend,
  disabled,
  questionsCount,
  questionsRemaining,
}: ChatInputProps) {
  const [input, setInput] = useState('');

  const handleSend = () => {
    if (!input.trim() || disabled) return;
    onSend(input.trim());
    setInput('');
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="border-t bg-white p-4">
      <div className="container mx-auto max-w-4xl">
        {/* Compteur */}
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm text-gray-600">
            Question <span className="font-semibold">{questionsCount}/5</span>
          </span>
          <span className="text-xs text-gray-500">
            {questionsRemaining} restante{questionsRemaining > 1 ? 's' : ''}
          </span>
        </div>

        {/* Input */}
        <div className="flex gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              disabled
                ? 'Limite de 5 questions atteinte'
                : 'Posez une question sur mon parcours...'
            }
            disabled={disabled}
            className="flex-1 resize-none rounded-lg border border-gray-300 px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-50 disabled:text-gray-400 disabled:cursor-not-allowed"
            rows={2}
          />
          <button
            onClick={handleSend}
            disabled={disabled || !input.trim()}
            className="px-6 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors flex items-center justify-center"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
