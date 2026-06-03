'use client';

import { useState } from 'react';
import { fetchRag, RagResponse } from '@/lib/savenciaApi';

const SUGGESTED_QUESTIONS = [
  "Quelles sont les dernières actualités de Savencia ?",
  "Quels sont les enjeux de l'IA dans l'industrie agroalimentaire ?",
  "Quelle est la stratégie de Savencia dans le secteur fromager ?",
  "Quelles innovations technologiques impactent l'agroalimentaire en France ?",
];

export default function AskAiView() {
  const [question, setQuestion] = useState('');
  const [result, setResult] = useState<RagResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (q?: string) => {
    const query = q ?? question;
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await fetchRag(query, 5);
      setResult(res);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Erreur inconnue');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div className="mb-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-1">Ask AI — Savencia Investigation</h2>
        <p className="text-sm text-gray-500">
          Posez une question sur Savencia et l'industrie agroalimentaire. Le modèle interroge les actualités collectées.
        </p>
      </div>

      {/* Input */}
      <div className="flex gap-2 mb-4">
        <input
          type="text"
          value={question}
          onChange={e => setQuestion(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleSubmit()}
          placeholder="Ex: Quelle est la stratégie de Savencia ?"
          className="flex-1 border rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
        />
        <button
          onClick={() => handleSubmit()}
          disabled={loading || !question.trim()}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? '...' : 'Envoyer'}
        </button>
      </div>

      {/* Questions suggérées */}
      {!result && !loading && (
        <div className="mb-6">
          <p className="text-xs text-gray-500 mb-2">Questions suggérées :</p>
          <div className="flex flex-wrap gap-2">
            {SUGGESTED_QUESTIONS.map(q => (
              <button
                key={q}
                onClick={() => { setQuestion(q); handleSubmit(q); }}
                className="text-xs px-3 py-1.5 border rounded-full text-gray-600 hover:bg-gray-50 transition-colors"
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="border rounded-lg p-6 bg-white animate-pulse">
          <div className="h-4 bg-gray-200 rounded w-3/4 mb-2" />
          <div className="h-4 bg-gray-200 rounded w-1/2 mb-2" />
          <div className="h-4 bg-gray-200 rounded w-2/3" />
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="text-red-500 text-sm p-4 border border-red-200 rounded-lg">{error}</div>
      )}

      {/* Résultat */}
      {result && (
        <div className="space-y-4">
          {/* Réponse */}
          <div className="border rounded-lg p-5 bg-white">
            <div className="flex items-center justify-between mb-3">
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Réponse</p>
              <div className="flex gap-2 text-xs text-gray-400">
                <span>🤖 {result.model_used.split('/').pop()}</span>
                <span>🔢 {result.tokens_used} tokens</span>
              </div>
            </div>
            <p className="text-sm text-gray-800 whitespace-pre-wrap leading-relaxed">{result.answer}</p>
          </div>

          {/* Sources */}
          {result.sources.length > 0 && (
            <div className="border rounded-lg p-4 bg-white">
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">Sources utilisées</p>
              <div className="space-y-2">
                {result.sources.map((src, i) => (
                  <div key={src.id} className="flex items-start gap-3">
                    <span className="text-xs text-gray-400 mt-0.5 w-4">[{i + 1}]</span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-0.5">
                        <span className="text-xs px-2 py-0.5 rounded bg-gray-100 text-gray-600">
                          📰 Actualité
                        </span>
                        {src.score !== null && (
                          <span className="text-xs text-gray-400">score: {src.score}</span>
                        )}
                      </div>
                      {src.url ? (
                        <a href={src.url} target="_blank" rel="noopener noreferrer"
                          className="text-xs text-blue-600 hover:underline truncate block">
                          {src.title}
                        </a>
                      ) : (
                        <p className="text-xs text-gray-600 truncate">{src.title}</p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Reset */}
          <button
            onClick={() => { setResult(null); setQuestion(''); }}
            className="text-xs text-gray-400 hover:text-gray-600 transition-colors"
          >
            ← Nouvelle question
          </button>
        </div>
      )}
    </div>
  );
}