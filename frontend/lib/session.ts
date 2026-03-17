
import { v4 as uuidv4 } from 'uuid';
import { Session, Message } from '@/types';
import { initializeSession } from '@/lib/api';

const SESSION_KEY = 'cv_rag_session';
const MAX_QUESTIONS = 5;
// const COOLDOWN_MS = 60 * 60 * 1000; // 1 heure
const COOLDOWN_MS = 30;

export async function getOrCreateSession(): Promise<Session> {
  if (typeof window === 'undefined') {
    return createNewSession();
  }

  const stored = localStorage.getItem(SESSION_KEY);
  
  if (!stored) {
    const session = createNewSession();
    saveSession(session);
    
    // Initialiser en base
    console.log('🔄 Initializing session:', session.sessionId);
    await initializeSession(session.sessionId);
    console.log('✅ Session initialized');
    
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
    
    // Initialiser la nouvelle session en base
    const { initializeSession } = await import('@/lib/api');
    await initializeSession(newSession.sessionId);
    
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

export async function incrementQuestionCount(): Promise<void> {
  const session = getSessionSync();
  session.questionsCount += 1;
  session.lastQuestionAt = Date.now();
  saveSession(session);
}

export async function canAskQuestion(): Promise<boolean> {
  const session = getSessionSync();
  return session.questionsCount < MAX_QUESTIONS;
}

export async function getRemainingTime(): Promise<number | null> {
  const session = await getOrCreateSession();
  
  if (session.questionsCount < MAX_QUESTIONS) {
    return null;
  }
  
  const now = Date.now();
  const timeSinceLastQuestion = now - session.lastQuestionAt;
  const remaining = COOLDOWN_MS - timeSinceLastQuestion;
  
  return remaining > 0 ? remaining : null;
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

export async function getSessionId(): Promise<string> {
  const session = getSessionSync();
  return session.sessionId;
}

/**
 * Récupère la session sans initialiser en base (synchrone)
 */
export function getSessionSync(): Session {
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
    return session;
  }
  
  // Reset si cooldown passé
  if (session.questionsCount >= MAX_QUESTIONS && timeSinceLastQuestion >= COOLDOWN_MS) {
    const newSession = createNewSession();
    saveSession(newSession);
    return newSession;
  }
  
  return session;
}