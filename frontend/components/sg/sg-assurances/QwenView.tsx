'use client';

import { useState } from 'react';
import { fetchSgQwen, QwenResponse } from '@/lib/sgApi';

const SUGGESTED_PROMPTS = [
  "Qu'est-ce qu'une franchise en assurance auto ?",
  "Quelles sont les garanties d'un contrat multirisque habitation ?",
  "Comment déclarer un sinistre automobile ?",
  "Qu'est-ce que la responsabilité civile en assurance ?",
];

export default function QwenView() {
  const [prompt, setPrompt]   = useState('');
  const [result, setResult]   = useState<QwenResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState<string | null>(null);

  const handleSubmit = async (p?: string) => {
    const query = p ?? prompt;
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await fetchSgQwen(query, 200);
      setResult(res);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Erreur inconnue');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      {/* Header */}
      <div className="mb-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-1">Qwen Demo — Modèle fine-tuné SG</h2>
        <p className="text-sm text-gray-500">
          Modèle Qwen2.5-1.5B fine-tuné sur les documents SG Assurances via QLoRA. Posez une question sur le domaine assurance.
        </p>
        <div className="flex items-center gap-2 mt-2">
          <span className="text-xs px-2 py-1 bg-amber-100 text-amber-700 rounded-full border border-amber-200 font-medium">
            ✨ Fine-tuné QLoRA
          </span>
          <span className="text-xs px-2 py-1 bg-gray-100 text-gray-500 rounded-full border">
            Vertex AI — T4
          </span>
        </div>
      </div>

      {/* Input */}
      <div className="flex gap-2 mb-4">
        <input
          type="text"
          value={prompt}
          onChange={e => setPrompt(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleSubmit()}
          placeholder="Ex: Qu'est-ce qu'une franchise en assurance ?"
          className="flex-1 border rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-300"
        />
        <button
          onClick={() => handleSubmit()}
          disabled={loading || !prompt.trim()}
          className="px-4 py-2 bg-amber-500 text-white rounded-lg text-sm font-medium hover:bg-amber-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? '...' : 'Générer'}
        </button>
      </div>

      {/* Prompts suggérés */}
      {!result && !loading && (
        <div className="mb-6">
          <p className="text-xs text-gray-500 mb-2">Exemples de prompts :</p>
          <div className="flex flex-wrap gap-2">
            {SUGGESTED_PROMPTS.map(p => (
              <button
                key={p}
                onClick={() => { setPrompt(p); handleSubmit(p); }}
                className="text-xs px-3 py-1.5 border rounded-full text-gray-600 hover:bg-gray-50 transition-colors"
              >
                {p}
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
          <div className="border rounded-lg p-5 bg-white">
            <div className="flex items-center justify-between mb-3">
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Réponse générée</p>
              <span className="text-xs px-2 py-1 bg-amber-100 text-amber-700 rounded-full border border-amber-200">
                ✨ {result.model_type}
              </span>
            </div>
            <p className="text-sm text-gray-800 whitespace-pre-wrap leading-relaxed">{result.generated_text}</p>
          </div>

          <button
            onClick={() => { setResult(null); setPrompt(''); }}
            className="text-xs text-gray-400 hover:text-gray-600 transition-colors"
          >
            ← Nouveau prompt
          </button>
        </div>
      )}
    </div>
  );
}