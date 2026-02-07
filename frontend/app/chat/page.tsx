
'use client';

import { useState, useEffect, useRef } from 'react';
import { Message } from '@/types';
import { sendMessage } from '@/lib/api';
import {
  getOrCreateSession,
  canAskQuestion,
  incrementQuestionCount,
  getRemainingTime,
  formatRemainingTime,
} from '@/lib/session';
import ChatMessage from '@/components/chat/ChatMessage';
import ChatInput from '@/components/chat/ChatInput';
import SessionLimitBanner from '@/components/chat/SessionLimitBanner';
import { Loader2 } from 'lucide-react';

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [streamingMessage, setStreamingMessage] = useState<Message | null>(null); // ← nouveau
  const [session, setSession] = useState(getOrCreateSession());
  const [remainingTime, setRemainingTime] = useState<number | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll vers le bas
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, streamingMessage?.content]);

  // Vérifier cooldown toutes les 10s
  useEffect(() => {
    const interval = setInterval(() => {
      const remaining = getRemainingTime();
      setRemainingTime(remaining);
      
      if (remaining === null) {
        // Cooldown terminé, rafraîchir session
        setSession(getOrCreateSession());
      }
    }, 10000);

    return () => clearInterval(interval);
  }, []);

  // Message initial
  useEffect(() => {
    if (messages.length === 0) {
      setMessages([
        {
          role: 'assistant',
          content:
            "Bonjour ! Je suis l'assistant virtuel d'Iandry (prononcé Ian'ch) RAKOTONIAINA. Posez-moi des questions sur son experience professionnelle, sa formation ou ses projets. Vous pouvez poser 3 questions",
          timestamp: Date.now(),
        },
      ]);
    }
  }, []);

  const handleSend = async (messageText: string) => {
    if (!canAskQuestion()) return;

    // Ajouter message user
    const userMessage: Message = {
      role: 'user',
      content: messageText,
      timestamp: Date.now(),
    };
    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);

    try {
      // Appel API
      const response = await sendMessage(messageText, session.sessionId);

      // Incrémenter compteur
      incrementQuestionCount();
      setSession(getOrCreateSession());

      // Ajouter réponse assistant
      const assistantMessage: Message = {
        role: 'assistant',
        content: response.response,
        sources: response.sources,
        timestamp: Date.now(),
      };
      setMessages((prev) => [...prev, assistantMessage]);

      // Vérifier cooldown
      const remaining = getRemainingTime();
      setRemainingTime(remaining);
    } catch (error) {
      console.error('Erreur chat:', error);
      const errorMessage: Message = {
        role: 'assistant',
        content:
          "Désolé, une erreur s'est produite. Veuillez réessayer dans quelques instants.",
        timestamp: Date.now(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const isLimitReached = !canAskQuestion();

  return (
    <div className="flex flex-col h-[calc(100vh-64px)]">
      {/* Messages container */}
      <div className="flex-1 overflow-y-auto">
        <div className="container mx-auto px-4 py-6 max-w-4xl">
          {/* Banner limite */}
          {isLimitReached && remainingTime && (
            <SessionLimitBanner
              remainingTime={formatRemainingTime(remainingTime)}
            />
          )}

          {/* Messages */}
          {messages.map((msg, idx) => (
            <ChatMessage key={idx} message={msg} />
          ))}

          {/* Loading */}
          {isLoading && (
            <div className="flex justify-start mb-4">
              <div className="bg-gray-100 rounded-lg px-4 py-3 flex items-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin text-gray-600" />
                <span className="text-sm text-gray-600">
                  Réflexion en cours...
                </span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input fixe en bas */}
      <ChatInput
        onSend={handleSend}
        disabled={isLimitReached || isLoading}
        questionsCount={session.questionsCount}
        questionsRemaining={3 - session.questionsCount}
      />
    </div>
  );
}