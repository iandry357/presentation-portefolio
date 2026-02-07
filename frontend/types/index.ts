export interface Message {
  role: 'user' | 'assistant';
  content: string;
  sources?: Source[];
  timestamp: number;
}

export interface Source {
  type: 'experience' | 'project' | 'formation';
  id: number;
  title: string;
  score: number;
}

export interface ChatResponse {
  query_id: string;
  response: string;
  sources: Source[];
  tokens_used: number;
  cost: number;
  provider_used: string;
  questions_count: number;
  questions_remaining: number;
}

export interface Session {
  sessionId: string;
  createdAt: number;
  questionsCount: number;
  lastQuestionAt: number;
}