'use client';

import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { AssistantReponse, MessageHistorique, postAssistantChat } from '@/lib/immobilierBdnbApi';
import { CarteGraphique } from '../ImmobilierCharts';
import Lecture from './Lecture';

// Paramètres
const QUESTIONS_SUGGEREES = [
  'Puis-je louer un logement classé G ?',
  'Combien de temps un diagnostic de performance énergétique est-il valable ?',
  'Quel audit énergétique faut-il pour vendre un logement classé F ou G ?',
];
const NB_ECHANGES_HISTORIQUE = 2;     // derniers échanges renvoyés au backend (limite : 6 messages)
const LONGUEUR_MAX_QUESTION = 500;    // backend/routers/immobilier/assistant_schemas.py
const LONGUEUR_MAX_MESSAGE = 2000;

interface Echange {
  question: string;
  reponse?: AssistantReponse;
  erreur?: string;
}

type EchangeRepondu = Echange & { reponse: AssistantReponse };

function dateFr(iso: string): string {
  return iso.split('-').reverse().join('/');
}

// Les [n] de la réponse deviennent des liens vers l'article officiel (la source n°n)
function avecLiens(reponse: AssistantReponse): string {
  return reponse.reponse.replace(/\[(\d+)\]/g, (_, n) => {
    const source = reponse.sources[Number(n) - 1];
    return source ? `[\\[${n}\\]](${source.url})` : '';
  });
}

function historiqueDe(echanges: Echange[]): MessageHistorique[] {
  return echanges
    .filter((e): e is EchangeRepondu => !!e.reponse)
    .slice(-NB_ECHANGES_HISTORIQUE)
    .flatMap(e => [
      { role: 'user' as const, content: e.question },
      { role: 'assistant' as const, content: e.reponse.reponse.replace(/\[\d+\]/g, '').slice(0, LONGUEUR_MAX_MESSAGE) },
    ]);
}

function BlocReponse({ reponse }: { reponse: AssistantReponse }) {
  return (
    <div className={reponse.refus ? 'bg-amber-50 border border-amber-200 rounded-lg p-3' : 'bg-gray-50 border rounded-lg p-3'}>
      <div className="text-sm text-gray-800">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            a: ({ href, children }) => (
              <a href={href} target="_blank" rel="noopener noreferrer" className="text-blue-600 align-super text-xs font-semibold no-underline">
                {children}
              </a>
            ),
            ul: ({ children }) => <ul className="list-disc pl-5 space-y-1 my-2">{children}</ul>,
            ol: ({ children }) => <ol className="list-decimal pl-5 space-y-1 my-2">{children}</ol>,
            p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
          }}
        >
          {avecLiens(reponse)}
        </ReactMarkdown>
      </div>
      {reponse.sources.length > 0 && (
        <ol className="mt-3 pt-2 border-t space-y-1 text-xs text-gray-600">
          {reponse.sources.map((s, i) => (
            <li key={i}>
              <span className="font-semibold text-gray-900">[{i + 1}] </span>
              <a href={s.url} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
                {s.reference}
              </a>
              {` · ${s.statut}`}
              {s.date_version && ` · version du ${dateFr(s.date_version)}`}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

export default function AssistantView() {
  const [echanges, setEchanges] = useState<Echange[]>([]);
  const [saisie, setSaisie] = useState('');
  const [enCours, setEnCours] = useState(false);

  async function poser(question: string) {
    const texte = question.trim();
    if (texte.length < 3 || enCours) return;
    const historique = historiqueDe(echanges);
    setSaisie('');
    setEnCours(true);
    setEchanges(prev => [...prev, { question: texte }]);
    const maj = (partiel: Partial<Echange>) =>
      setEchanges(prev => prev.map((e, i) => (i === prev.length - 1 ? { ...e, ...partiel } : e)));
    try {
      maj({ reponse: await postAssistantChat(texte, historique) });
    } catch (e) {
      maj({ erreur: e instanceof Error ? e.message : 'Erreur inattendue' });
    } finally {
      setEnCours(false);
    }
  }

  return (
    <CarteGraphique
      titre="Assistant immobilier"
      sousTitre="Performance énergétique, fiscalité et aides : des réponses tirées de textes officiels cités"
    >
      <Lecture
        voir="Un assistant qui répond uniquement à partir de textes officiels (Légifrance, BOFiP) et cite la source de chaque affirmation."
        retenir="Chaque réponse renvoie à l’article, à son statut et à sa date de version ; sans source dans le corpus, l’assistant refuse de répondre."
        attention="Information générale, pas un conseil juridique ou fiscal. La réponse peut prendre une vingtaine de secondes."
      />

      {echanges.length === 0 && (
        <div className="flex flex-wrap gap-2 mb-4">
          {QUESTIONS_SUGGEREES.map(q => (
            <button
              key={q}
              onClick={() => setSaisie(q)}
              disabled={enCours}
              className="text-left text-sm px-3 py-2 rounded-lg border bg-white text-gray-700 hover:bg-gray-50 disabled:opacity-50"
            >
              {q}
            </button>
          ))}
        </div>
      )}

      <div className="space-y-4">
        {echanges.map((e, i) => (
          <div key={i} className="space-y-2">
            <p className="text-sm font-medium text-gray-900 bg-blue-50 rounded-lg px-3 py-2 w-fit max-w-full">{e.question}</p>
            {e.reponse && <BlocReponse reponse={e.reponse} />}
            {e.erreur && <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{e.erreur}</p>}
            {!e.reponse && !e.erreur && (
              <p className="text-sm text-gray-500 animate-pulse">L’assistant consulte les textes officiels…</p>
            )}
          </div>
        ))}
      </div>

      <form
        onSubmit={ev => {
          ev.preventDefault();
          poser(saisie);
        }}
        className="flex gap-2 mt-4"
      >
        <input
          value={saisie}
          onChange={ev => setSaisie(ev.target.value)}
          maxLength={LONGUEUR_MAX_QUESTION}
          disabled={enCours}
          placeholder="Posez votre question immobilière…"
          className="flex-1 min-w-0 border rounded-lg px-3 py-2 text-sm disabled:bg-gray-50"
        />
        <button
          type="submit"
          disabled={enCours || saisie.trim().length < 3}
          className="px-4 py-2 text-sm font-medium rounded-lg bg-blue-600 text-white disabled:opacity-50"
        >
          Envoyer
        </button>
      </form>

      {echanges.length > 0 && (
        <button
          onClick={() => setEchanges([])}
          disabled={enCours}
          className="mt-3 text-xs text-gray-500 hover:text-gray-800 disabled:opacity-50"
        >
          Nouvelle conversation
        </button>
      )}
    </CarteGraphique>
  );
}
