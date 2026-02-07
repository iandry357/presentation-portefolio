
import { v4 as uuidv4 } from 'uuid';
import { Session } from '@/types';

const SESSION_KEY = 'cv_rag_session';
const MAX_QUESTIONS = 3;
// const COOLDOWN_MS = 60 * 60 * 1000; // 1 heure
const COOLDOWN_MS = 30;

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

export function formatRemainingTime(ms: number): string {
  const minutes = Math.ceil(ms / (60 * 1000));
  if (minutes < 60) {
    return `${minutes} min`;
  }
  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  return remainingMinutes > 0 ? `${hours}h ${remainingMinutes}min` : `${hours}h`;
}