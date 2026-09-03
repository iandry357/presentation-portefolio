'use client';

import { useEffect, useRef, useState } from 'react';
import { envoyerMessage, ArticleCite, Profil } from '@/lib/gestionPatrimoineApi';

interface Props {
  sessionId: string;
  profil: Profil;
}

interface Message {
  role: 'user' | 'assistant';
  texte: string;
  articles_cites?: ArticleCite[];
}

const THEMATIQUE_LABELS: Record<string, string> = {
  donations_successions: 'Donations / Successions',
  ifi: 'IFI',
  plus_values: 'Plus-values',
  assurance_vie: 'Assurance-vie',
  per: 'PER / épargne retraite',
};

export default function ChatAssistant({ sessionId, profil }: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const premierTourDeclenche = useRef(false);

  // Premier tour : déclenché automatiquement, sans saisie utilisateur —
  // la synthèse initiale se base uniquement sur le profil.
  useEffect(() => {
    if (premierTourDeclenche.current) return;
    premierTourDeclenche.current = true;
    setLoading(true);
    envoyerMessage(sessionId)
      .then(res => setMessages([{ role: 'assistant', texte: res.texte, articles_cites: res.articles_cites }]))
      .catch(e => setError(e instanceof Error ? e.message : 'Erreur inconnue'))
      .finally(() => setLoading(false));
  }, [sessionId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async () => {
    const message = input.trim();
    if (!message || loading) return;
    setMessages(prev => [...prev, { role: 'user', texte: message }]);
    setInput('');
    setLoading(true);
    setError(null);
    try {
      const res = await envoyerMessage(sessionId, message);
      setMessages(prev => [...prev, { role: 'assistant', texte: res.texte, articles_cites: res.articles_cites }]);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Erreur inconnue');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col md:flex-row gap-6 items-start">
      {/* Carte profil — contexte persistant */}
      <aside className="w-full md:w-72 shrink-0 border rounded-lg bg-white p-4">
        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">Profil client</p>
        <dl className="space-y-2 text-sm">
          <div>
            <dt className="text-gray-400 text-xs">Thématique</dt>
            <dd className="text-gray-800 font-medium">
              {THEMATIQUE_LABELS[profil.thematique] ?? profil.thematique}
            </dd>
          </div>
          <div>
            <dt className="text-gray-400 text-xs">Âge</dt>
            <dd className="text-gray-800">{profil.age} ans</dd>
          </div>
          <div>
            <dt className="text-gray-400 text-xs">Situation familiale</dt>
            <dd className="text-gray-800">{profil.situation_familiale}</dd>
          </div>
          <div>
            <dt className="text-gray-400 text-xs">Patrimoine global</dt>
            <dd className="text-gray-800">{profil.patrimoine_global.toLocaleString('fr-FR')} €</dd>
          </div>
          <div>
            <dt className="text-gray-400 text-xs">Objectif</dt>
            <dd className="text-gray-800">{profil.objectif}</dd>
          </div>
        </dl>
      </aside>

      {/* Conversation */}
      <div className="flex-1 min-w-0 border rounded-lg bg-white flex flex-col h-[600px]">
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.map((m, i) => (
            <div key={i} className={m.role === 'user' ? 'flex justify-end' : 'flex justify-start'}>
              <div
                className={
                  m.role === 'user'
                    ? 'max-w-[80%] bg-emerald-600 text-white rounded-lg px-4 py-2 text-sm'
                    : 'max-w-[80%] bg-gray-50 border rounded-lg px-4 py-3 text-sm'
                }
              >
                <p className="whitespace-pre-wrap leading-relaxed">{m.texte}</p>

                {m.articles_cites && m.articles_cites.length > 0 && (
                  <div className="flex flex-wrap gap-2 mt-3 pt-3 border-t border-gray-200">
                    {m.articles_cites.map((a, j) => (
                      <a
                        key={j}
                        href={a.url_source}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs px-2 py-1 bg-emerald-100 text-emerald-700 rounded-full border border-emerald-200 hover:bg-emerald-200 transition-colors"
                      >
                        Art. {a.numero_article} ↗
                      </a>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}

          {loading && (
            <div className="flex justify-start">
              <div className="bg-gray-50 border rounded-lg px-4 py-3 text-sm text-gray-400 animate-pulse">
                Recherche dans le référentiel...
              </div>
            </div>
          )}

          {error && (
            <div className="text-red-500 text-sm p-3 border border-red-200 rounded-lg">{error}</div>
          )}

          <div ref={bottomRef} />
        </div>

        <div className="border-t p-3 flex gap-2">
          <input
            type="text"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSend()}
            placeholder="Posez une question sur ce profil..."
            disabled={loading}
            className="flex-1 border rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-300 disabled:opacity-50"
          />
          <button
            onClick={handleSend}
            disabled={loading || !input.trim()}
            className="px-4 py-2 bg-emerald-600 text-white rounded-lg text-sm font-medium hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            Envoyer
          </button>
        </div>
      </div>
    </div>
  );
}