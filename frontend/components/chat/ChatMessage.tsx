'use client';

import { Message } from '@/types';
import { formatTimestamp, getSourceUrl } from '@/lib/utils';
import { ExternalLink } from 'lucide-react';
import Link from 'next/link';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface ChatMessageProps {
  message: Message;
}

export default function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === 'user';

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>
      <div className={`max-w-[80%] ${isUser ? 'order-2' : 'order-1'}`}>
        {/* Bulle message */}
        <div
          className={`rounded-lg px-4 py-3 ${
            isUser
              ? 'bg-blue-600 text-white'
              : 'bg-gray-100 text-gray-900 dark:bg-gray-800 dark:text-gray-100'
          }`}
        >
          {isUser ? (
            // Messages utilisateur → texte brut (ou pre-wrap si tu veux conserver les sauts de ligne)
            <p className="text-sm whitespace-pre-wrap break-words">
              {message.content}
            </p>
          ) : (
            // Messages assistant → rendu Markdown
            <div className="text-sm prose prose-sm prose-gray dark:prose-invert max-w-none">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {message.content}
              </ReactMarkdown>
            </div>
          )}
        </div>

        {/* Timestamp */}
        <div
          className={`text-xs text-gray-500 mt-1 px-1 ${
            isUser ? 'text-right' : 'text-left'
          }`}
        >
          {formatTimestamp(message.timestamp)}
        </div>

        {/* Sources (assistant uniquement) */}
        {!isUser && message.sources && message.sources.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {message.sources.map((source, idx) => (
              <Link
                key={idx}
                href={getSourceUrl(source.type, source.id)}
                target="_blank"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white border border-gray-200 rounded-full text-xs text-gray-700 hover:bg-gray-50 transition-colors dark:bg-gray-800 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-700"
              >
                <ExternalLink className="w-3 h-3" />
                <span className="font-medium">{source.title}</span>
                <span className="text-gray-400 dark:text-gray-500">
                  ({Math.round(source.score * 100)}%)
                </span>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}