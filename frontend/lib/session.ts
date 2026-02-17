
import { v4 as uuidv4 } from 'uuid';
import { Session, Message } from '@/types';

const SESSION_KEY = 'cv_rag_session';
const MAX_QUESTIONS = 5;
// const COOLDOWN_MS = 60 * 60 * 1000; // 1 heure
const COOLDOWN_MS = 3 * 60 * 1000;

export function getOrCreateSession(): Session {
  if (typeof window === 'undefined') {
    return createNewSession();
  }

  const stored = localStorage.getItem(SESSION_KEY);
  
  if (!stored) {
    const session = createNewSession();
    saveSession(session);
    return session;
  }

  const session: Session = JSON.parse(stored);
  
  // Vérifier cooldown
  const now = Date.now();
  const timeSinceLastQuestion = now - session.lastQuestionAt;
  
  if (session.questionsCount >= MAX_QUESTIONS && timeSinceLastQuestion < COOLDOWN_MS) {
    return session; // Limite atteinte, cooldown actif
  }
  
  // Reset si cooldown passé
  if (session.questionsCount >= MAX_QUESTIONS && timeSinceLastQuestion >= COOLDOWN_MS) {
    const newSession = createNewSession();
    saveSession(newSession);
    return newSession;
  }
  
  return session;
}

export function createNewSession(): Session {
  return {
    sessionId: uuidv4(),
    createdAt: Date.now(),
    questionsCount: 0,
    lastQuestionAt: Date.now(),
  };
}

export function saveSession(session: Session): void {
  if (typeof window === 'undefined') return;
  localStorage.setItem(SESSION_KEY, JSON.stringify(session));
}

// Sauvegarder messages
export function saveMessages(messages: Message[]) {
  if (typeof window === 'undefined') return;
  localStorage.setItem('chat_messages', JSON.stringify(messages));
}

// Charger messages
export function loadMessages(): Message[] {
  if (typeof window === 'undefined') return [];
  const stored = localStorage.getItem('chat_messages');
  return stored ? JSON.parse(stored) : [];
}

// Nettoyer (quand session expire)
export function clearMessages() {
  if (typeof window === 'undefined') return;
  localStorage.removeItem('chat_messages');
}

export function incrementQuestionCount(): void {
  const session = getOrCreateSession();
  session.questionsCount += 1;
  session.lastQuestionAt = Date.now();
  saveSession(session);
}

export function canAskQuestion(): boolean {
  const session = getOrCreateSession();
  return session.questionsCount < MAX_QUESTIONS;
}

export function getRemainingTime(): number | null {
  const session = getOrCreateSession();
  
  if (session.questionsCount < MAX_QUESTIONS) {
    return null;
  }
  
  const now = Date.now();
  const timeSinceLastQuestion = now - session.lastQuestionAt;
  const remaining = COOLDOWN_MS - timeSinceLastQuestion;
  
  return remaining > 0 ? remaining : null;
}

export function shouldClearSession(): boolean {
  const session = getOrCreateSession();
  
  // Clear seulement si limite atteinte ET cooldown terminé
  if (session.questionsCount < MAX_QUESTIONS) {
    return false;
  }
  
  const now = Date.now();
  const timeSinceLastQuestion = now - session.lastQuestionAt;
  
  return timeSinceLastQuestion >= COOLDOWN_MS;
}

export function formatRemainingTime(ms: number): string {
  const minutes = Math.ceil(ms / (60 * 1000));
  if (minutes < 60) {
    return `${minutes} min`;
  }
  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  return remainingMinutes > 0 ? `${hours}h ${remainingMinutes}min` : `${hours}h`;
}