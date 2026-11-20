'use client';

import { useCallback, useEffect, useState } from 'react';
import {
  fetchWavestoneNews, fetchWavestoneRag, fetchWavestoneTopicModeling, fetchWavestoneRecrutement,
  NewsItem, RagResponse, TopicModelingResponse, RecrutementResponse, PosteItem,
} from '@/lib/wavestoneApi';

// ─────────────────────────────────────────
// Utilitaires
// ─────────────────────────────────────────

export function formatDate(d: string | null | undefined): string {
  if (!d) return '—';
  const [y, m, j] = d.slice(0, 10).split('-');
  return y && m && j ? `${j}/${m}/${y}` : d;
}

function messageErreur(e: unknown): string {
  return e instanceof Error ? e.message : 'Erreur inconnue';
}

export const SECTION_LIBELLES: Record<string, string> = {
  news: 'Communiqué',
  insight: 'Publication',
  clients_story: 'Cas client',
  presse: 'Presse',
};

const SECTION_COULEURS: Record<string, string> = {
  news: 'bg-blue-50 text-blue-700',
  insight: 'bg-violet-50 text-violet-700',
  clients_story: 'bg-emerald-50 text-emerald-700',
  presse: 'bg-amber-50 text-amber-700',
};

function Badge({ texte, classe }: { texte: string; classe: string }) {
  return <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${classe}`}>{texte}</span>;
}

function BadgeSection({ section }: { section: string | null | undefined }) {
  const s = section ?? 'presse';
  return <Badge texte={SECTION_LIBELLES[s] ?? s} classe={SECTION_COULEURS[s] ?? 'bg-gray-100 text-gray-600'} />;
}

function Barre({ valeur, max }: { valeur: number; max: number }) {
  const largeur = max > 0 ? Math.max(2, Math.round((100 * valeur) / max)) : 0;
  return (
    <div className="h-2 bg-gray-100 rounded">
      <div className="h-2 rounded bg-blue-500" style={{ width: `${largeur}%` }} />
    </div>
  );
}

function Chargement() {
  return <div className="text-sm text-gray-400 p-4">Chargement…</div>;
}

function Erreur({ message }: { message: string }) {
  return <div className="text-red-500 text-sm p-4 border border-red-200 rounded-lg">{message}</div>;
}

function Puces({
  options, valeur, onChange,
}: {
  options: { id: string | null; label: string }[];
  valeur: string | null;
  onChange: (v: string | null) => void;
}) {
  return (
    <div className="flex flex-wrap gap-2 mb-4">
      {options.map(o => (
        <button
          key={o.id ?? 'tous'}
          onClick={() => onChange(o.id)}
          className={`text-xs px-3 py-1.5 border rounded-full transition-colors ${
            valeur === o.id ? 'bg-blue-600 text-white border-blue-600' : 'text-gray-600 hover:bg-gray-50'
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

const OPTIONS_LANGUE = [
  { id: null, label: 'FR et EN' },
  { id: 'fr', label: 'Français' },
  { id: 'en', label: 'English' },
];

// ─────────────────────────────────────────
// Actualités (site + presse)
// ─────────────────────────────────────────

const PAGE_NEWS = 20;

export function NewsView() {
  const [langue, setLangue] = useState<string | null>(null);
  const [section, setSection] = useState<string | null>(null);
  const [items, setItems] = useState<NewsItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const charger = useCallback((offset: number) => {
    setLoading(true);
    setError(null);
    fetchWavestoneNews({ langue: langue ?? undefined, section: section ?? undefined, limit: PAGE_NEWS, offset })
      .then(r => {
        setTotal(r.total);
        setItems(prev => (offset === 0 ? r.items : [...prev, ...r.items]));
      })
      .catch(e => setError(messageErreur(e)))
      .finally(() => setLoading(false));
  }, [langue, section]);

  useEffect(() => { charger(0); }, [charger]);

  const optionsSection = [
    { id: null, label: 'Tout' },
    ...Object.entries(SECTION_LIBELLES).map(([id, label]) => ({ id, label })),
  ];

  return (
    <div>
      <p className="text-sm text-gray-500 mb-4">
        Communiqués, publications et cas clients du site de Wavestone, et articles de presse (Google News), les plus récents d&apos;abord.
      </p>
      <Puces options={OPTIONS_LANGUE} valeur={langue} onChange={setLangue} />
      <Puces options={optionsSection} valeur={section} onChange={setSection} />
      {error && <Erreur message={error} />}
      <p className="text-xs text-gray-400 mb-3">{items.length} affichés sur {total}</p>
      <div className="space-y-2">
        {items.map(n => (
          <div key={n.id} className="border rounded-lg p-4 bg-white">
            <div className="flex flex-wrap items-center gap-2 mb-1 text-xs text-gray-400">
              <span>{formatDate(n.date)}</span>
              <BadgeSection section={n.section} />
              {n.langue && <span className="uppercase">{n.langue}</span>}
              {n.section === 'presse' && n.source_name && <span>· {n.source_name}</span>}
            </div>
            {n.url ? (
              <a href={n.url} target="_blank" rel="noopener noreferrer" className="text-sm text-blue-600 hover:underline">
                {n.title}
              </a>
            ) : (
              <p className="text-sm text-gray-800">{n.title}</p>
            )}
          </div>
        ))}
      </div>
      {loading && <Chargement />}
      {!loading && items.length < total && (
        <button
          onClick={() => charger(items.length)}
          className="mt-4 text-xs px-4 py-2 border rounded-lg text-gray-600 hover:bg-gray-50 transition-colors"
        >
          Afficher plus
        </button>
      )}
    </div>
  );
}

// ─────────────────────────────────────────
// Ask AI
// ─────────────────────────────────────────

const SUGGESTED_QUESTIONS = [
  "Que fait Wavestone dans l'énergie et auprès des territoires ?",
  "Quels cas clients illustrent l'accompagnement du management dans une transformation ?",
  "Comment Wavestone aide-t-il ses clients à améliorer la relation client et la performance commerciale ?",
  "Quelle est la stratégie IA de Wavestone et quelles acquisitions récentes l'accompagnent ?",
  "Que dit la presse de la situation financière de Wavestone ?",
  "Que publie Wavestone sur la cybersécurité et l'IA ?",
  "Quels postes data ou IA Wavestone recrute-t-il en ce moment ?",
  "Quels postes ouverts correspondent le mieux à un profil data scientist ?",
];

export function RagView() {
  const [question, setQuestion] = useState('');
  const [result, setResult] = useState<RagResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (q?: string) => {
    const texte = q ?? question;
    if (!texte.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(await fetchWavestoneRag(texte, 8));
    } catch (e: unknown) {
      setError(messageErreur(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <p className="text-sm text-gray-500 mb-4">
        Posez une question sur Wavestone : expertises, cas clients, actualité, postes ouverts. Les réponses sont en français, même
        quand les sources sont en anglais, et citent les documents utilisés.
      </p>

      <div className="flex gap-2 mb-4">
        <input
          type="text"
          value={question}
          onChange={e => setQuestion(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleSubmit()}
          placeholder="Ex : Quels cas clients Wavestone dans l'énergie ?"
          className="flex-1 min-w-0 border rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
        />
        <button
          onClick={() => handleSubmit()}
          disabled={loading || !question.trim()}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? '...' : 'Envoyer'}
        </button>
      </div>

      {!result && !loading && (
        <div className="mb-6">
          <p className="text-xs text-gray-500 mb-2">Questions suggérées :</p>
          <div className="flex flex-wrap gap-2">
            {SUGGESTED_QUESTIONS.map(q => (
              <button
                key={q}
                onClick={() => { setQuestion(q); handleSubmit(q); }}
                className="text-xs px-3 py-1.5 border rounded-full text-gray-600 hover:bg-gray-50 transition-colors text-left"
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      )}

      {loading && (
        <div className="border rounded-lg p-6 bg-white animate-pulse">
          <div className="h-4 bg-gray-200 rounded w-3/4 mb-2" />
          <div className="h-4 bg-gray-200 rounded w-1/2 mb-2" />
          <div className="h-4 bg-gray-200 rounded w-2/3" />
        </div>
      )}

      {error && <Erreur message={error} />}

      {result && (
        <div className="space-y-4">
          <div className="border rounded-lg p-5 bg-white">
            <div className="flex items-center justify-between mb-3">
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Réponse</p>
              <span className="text-xs text-gray-400">{result.model_used.split('/').pop()}</span>
            </div>
            <p className="text-sm text-gray-800 whitespace-pre-wrap leading-relaxed">{result.answer}</p>
          </div>

          {result.sources.length > 0 && (
            <div className="border rounded-lg p-4 bg-white">
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">Sources</p>
              <div className="space-y-2">
                {result.sources.map((src, i) => (
                  <div key={src.id} className="flex items-start gap-3 text-xs">
                    <span className="text-gray-400 w-5 shrink-0">[{i + 1}]</span>
                    <div className="flex-1 min-w-0">
                      {src.url ? (
                        <a href={src.url} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
                          {src.title}
                        </a>
                      ) : (
                        <p className="text-gray-700">{src.title}</p>
                      )}
                      <p className="text-gray-400 flex flex-wrap items-center gap-2 mt-0.5">
                        {src.source === 'offre'
                          ? <Badge texte="Offre" classe="bg-gray-100 text-gray-700" />
                          : <BadgeSection section={src.section} />}
                        {src.langue && <span className="uppercase">{src.langue}</span>}
                        {src.date && <span>{src.date}</span>}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

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

// ─────────────────────────────────────────
// Thèmes (topic modeling LDA par langue)
// ─────────────────────────────────────────

const COLORS = ['#3b82f6', '#8b5cf6', '#ec4899', '#f59e0b', '#10b981', '#06b6d4'];

export function TopicView() {
  const [data, setData] = useState<TopicModelingResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [langue, setLangue] = useState<string | null>('fr');
  const [expanded, setExpanded] = useState<Record<number, boolean>>({});

  useEffect(() => {
    fetchWavestoneTopicModeling()
      .then(setData)
      .catch(() => setError('Impossible de charger les thèmes (topic modeling non encore calculé ?).'));
  }, []);

  if (error) return <Erreur message={error} />;
  if (!data) return <Chargement />;

  const topics = data.topics
    .filter(t => t.lang === langue)
    .map(t => ({
      ...t,
      docs: data.docs
        .filter(d => d.dominant_topic === t.topic_id)
        .sort((a, b) => b.confidence - a.confidence),
    }));
  const nbDocs = topics.reduce((n, t) => n + t.docs.length, 0);

  return (
    <div className="space-y-6 w-full max-w-full overflow-hidden">
      <div>
        <p className="text-sm text-gray-500 mb-4">
          Thèmes dégagés automatiquement (LDA, un modèle par langue) des publications, cas clients et communiqués de Wavestone ;
          libellés et résumés générés par un LLM à partir des titres.
        </p>
        <Puces
          options={[{ id: 'fr', label: 'Français' }, { id: 'en', label: 'English' }]}
          valeur={langue}
          onChange={setLangue}
        />
        <p className="text-xs text-gray-400">{nbDocs} documents → {topics.length} thèmes</p>
      </div>

      {topics.map((topic, i) => (
        <div key={topic.topic_id} className="bg-white border rounded-lg overflow-hidden">
          <div
            className="flex items-center gap-3 px-4 py-3 border-b border-l-4"
            style={{ borderLeftColor: COLORS[i % COLORS.length] }}
          >
            <span className="text-lg font-bold" style={{ color: COLORS[i % COLORS.length] }}>#{i + 1}</span>
            <div>
              <p className="font-semibold text-gray-900 text-sm">{topic.label}</p>
              <p className="text-xs text-gray-400">{topic.docs.length} documents</p>
            </div>
          </div>

          <div className="px-4 py-2 border-b bg-gray-50 flex flex-wrap gap-1 overflow-hidden">
            {topic.keywords.slice(0, 8).map(kw => (
              <span key={kw} className="text-xs bg-white border rounded px-2 py-0.5 text-gray-600">{kw}</span>
            ))}
          </div>

          {topic.summary && (
            <div className="px-4 py-3 border-b">
              <p className="text-sm text-gray-700 leading-relaxed">{topic.summary}</p>
            </div>
          )}

          <div className="divide-y">
            {topic.docs.slice(0, expanded[topic.topic_id] ? topic.docs.length : 5).map(doc => (
              <div key={doc.id ?? doc.title} className="px-4 py-2 flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0 w-0">
                  {doc.url ? (
                    <a href={doc.url} target="_blank" rel="noopener noreferrer" className="text-sm text-blue-700 hover:underline truncate block">
                      {doc.title}
                    </a>
                  ) : (
                    <p className="text-sm text-gray-800 truncate">{doc.title}</p>
                  )}
                  <p className="text-xs text-gray-400 mt-0.5">{formatDate(doc.date)}</p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <span className="hidden sm:inline"><BadgeSection section={doc.section} /></span>
                  <span className="text-xs text-gray-400">{Math.round(doc.confidence * 100)} %</span>
                </div>
              </div>
            ))}
            {topic.docs.length > 5 && (
              <button
                onClick={() => setExpanded(e => ({ ...e, [topic.topic_id]: !e[topic.topic_id] }))}
                className="px-4 py-2 text-xs text-blue-600 hover:underline text-left w-full"
              >
                {expanded[topic.topic_id] ? '− Réduire' : `+ ${topic.docs.length - 5} autres documents`}
              </button>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

// ─────────────────────────────────────────
// Recrutement
// ─────────────────────────────────────────

const CATEGORIE_LIBELLES: Record<string, string> = {
  coeur: 'cœur de cible',
  adjacent: 'adjacent',
  hors_cible: 'hors cible',
};

function BadgeScore({ score }: { score: number | null }) {
  if (score === null) return <span className="text-xs text-gray-400">—</span>;
  const classe = score >= 75
    ? 'bg-emerald-100 text-emerald-800'
    : score >= 60 ? 'bg-amber-100 text-amber-800' : 'bg-gray-100 text-gray-600';
  return <span className={`text-sm font-semibold px-2 py-0.5 rounded ${classe}`}>{score}</span>;
}

function LignePoste({ p }: { p: PosteItem }) {
  return (
    <div className="border rounded-lg p-4 bg-white">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          {p.url ? (
            <a href={p.url} target="_blank" rel="noopener noreferrer" className="text-sm font-medium text-blue-600 hover:underline">
              {p.titre}
            </a>
          ) : (
            <p className="text-sm font-medium text-gray-900">{p.titre}</p>
          )}
          <p className="text-xs text-gray-500 mt-1">
            {[p.famille, p.lieu, p.contrat].filter(Boolean).join(' · ')}
          </p>
          <p className="text-xs text-gray-400 mt-1">
            {p.nb_publications} publication{p.nb_publications > 1 ? 's' : ''} · du {formatDate(p.premiere_date)} au {formatDate(p.derniere_date)}
          </p>
        </div>
        <div className="text-right shrink-0">
          <BadgeScore score={p.score_max} />
          {p.categorie && <p className="text-xs text-gray-500 mt-1">{CATEGORIE_LIBELLES[p.categorie] ?? p.categorie}</p>}
          {p.cible_intitule && <p className="text-xs text-gray-400 mt-0.5 max-w-[180px]">{p.cible_intitule}</p>}
        </div>
      </div>
    </div>
  );
}

export function RecrutementView() {
  const [data, setData] = useState<RecrutementResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [famille, setFamille] = useState<string | null>(null);

  useEffect(() => {
    fetchWavestoneRecrutement().then(setData).catch(e => setError(messageErreur(e)));
  }, []);

  if (error) return <Erreur message={error} />;
  if (!data) return <Chargement />;

  const max = data.familles.length ? Math.max(...data.familles.map(f => f.nb_publications)) : 0;
  const postes = famille ? data.postes.filter(p => p.famille === famille) : data.postes;

  return (
    <div>
      <p className="text-sm text-gray-500 mb-4">
        Offres Wavestone repérées par ma collecte quotidienne (France Travail et alertes de sites d&apos;emploi) du{' '}
        {formatDate(data.periode_debut)} au {formatDate(data.periode_fin)} : {data.total_offres} publications pour{' '}
        {data.intitules_distincts} postes distincts (les republications d&apos;un même intitulé sont regroupées).
        Le score indique l&apos;adéquation du poste à mon profil data / IA (0 à 100), calculée chaque jour par un LLM local.
      </p>

      <div className="border rounded-lg bg-white p-4 space-y-3 mb-6">
        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Familles de postes</p>
        {data.familles.map(f => (
          <div key={f.famille} className="grid grid-cols-[minmax(0,180px)_1fr_110px] gap-3 items-center text-sm">
            <span className="text-gray-700 truncate">{f.famille}</span>
            <Barre valeur={f.nb_publications} max={max} />
            <span className="text-right text-xs text-gray-500">
              {f.nb_intitules} poste{f.nb_intitules > 1 ? 's' : ''} · {f.nb_publications}
            </span>
          </div>
        ))}
      </div>

      <Puces
        options={[{ id: null, label: 'Toutes les familles' }, ...data.familles.map(f => ({ id: f.famille, label: f.famille }))]}
        valeur={famille}
        onChange={setFamille}
      />
      <div className="space-y-2">
        {postes.map(p => <LignePoste key={`${p.titre}-${p.derniere_date}`} p={p} />)}
      </div>
    </div>
  );
}
