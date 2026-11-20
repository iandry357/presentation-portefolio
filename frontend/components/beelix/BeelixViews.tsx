'use client';

import { useEffect, useState } from 'react';
import {
  fetchBeelixSecteurs, fetchBeelixComptes, fetchBeelixOffres, fetchBeelixConcurrence,
  fetchBeelixBesoins, fetchBeelixTendance, fetchBeelixNews, fetchBeelixRag,
  SecteurItem, ComptesResponse, OffreItem, ConcurrenceResponse, BesoinsResponse,
  TendancePoint, NewsResponse, RagResponse,
} from '@/lib/beelixApi';

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

function Barre({ valeur, max, accent = false }: { valeur: number; max: number; accent?: boolean }) {
  const largeur = max > 0 ? Math.max(2, Math.round((100 * valeur) / max)) : 0;
  return (
    <div className="h-2 bg-gray-100 rounded">
      <div
        className={`h-2 rounded ${accent ? 'bg-amber-500' : 'bg-blue-500'}`}
        style={{ width: `${largeur}%` }}
      />
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

function useSecteursCibles(): SecteurItem[] {
  const [secteurs, setSecteurs] = useState<SecteurItem[]>([]);
  useEffect(() => {
    fetchBeelixSecteurs()
      .then(r => setSecteurs(r.items.filter(s => s.cible)))
      .catch(() => setSecteurs([]));
  }, []);
  return secteurs;
}

// ─────────────────────────────────────────
// Tendance hebdomadaire
// ─────────────────────────────────────────

function Tendance() {
  const [points, setPoints] = useState<TendancePoint[] | null>(null);

  useEffect(() => {
    fetchBeelixTendance().then(r => setPoints(r.points)).catch(() => setPoints([]));
  }, []);

  if (!points || points.length === 0) return null;
  const max = Math.max(...points.map(p => Math.max(p.offres_cibles, p.offres_concurrence)));

  return (
    <div className="border rounded-lg p-4 bg-white mb-6">
      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">Offres par semaine</p>
      <div className="space-y-2">
        {points.map(p => (
          <div key={p.semaine} className="grid grid-cols-[90px_1fr] gap-3 items-center text-xs">
            <span className="text-gray-500">{formatDate(p.semaine)}</span>
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <div className="flex-1"><Barre valeur={p.offres_cibles} max={max} /></div>
                <span className="w-10 text-right text-gray-600">{p.offres_cibles}</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="flex-1"><Barre valeur={p.offres_concurrence} max={max} accent /></div>
                <span className="w-10 text-right text-gray-600">{p.offres_concurrence}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
      <div className="flex gap-4 mt-3 text-xs text-gray-500">
        <span className="flex items-center gap-1"><span className="w-3 h-2 bg-blue-500 rounded" /> Secteurs Beelix</span>
        <span className="flex items-center gap-1"><span className="w-3 h-2 bg-amber-500 rounded" /> Concurrence</span>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────
// Comptes qui recrutent
// ─────────────────────────────────────────

export function ComptesView() {
  const secteurs = useSecteursCibles();
  const [secteur, setSecteur] = useState<string | null>(null);
  const [data, setData] = useState<ComptesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [ouvert, setOuvert] = useState<string | null>(null);
  const [offres, setOffres] = useState<OffreItem[]>([]);

  useEffect(() => {
    setLoading(true);
    setError(null);
    setOuvert(null);
    fetchBeelixComptes(secteur ?? undefined, 30)
      .then(setData)
      .catch(e => setError(messageErreur(e)))
      .finally(() => setLoading(false));
  }, [secteur]);

  const basculer = (cle: string, secteurCompte: string) => {
    if (ouvert === cle) {
      setOuvert(null);
      return;
    }
    setOuvert(cle);
    setOffres([]);
    fetchBeelixOffres({ secteur: secteurCompte, entreprise: cle, limit: 20 })
      .then(r => setOffres(r.items))
      .catch(() => setOffres([]));
  };

  const max = data && data.items.length ? data.items[0].nb_offres : 0;
  const options = [
    { id: null, label: 'Tous les secteurs Beelix' },
    ...secteurs.map(s => ({ id: s.secteur, label: `${s.libelle} (${s.nb_entreprises})` })),
  ];

  return (
    <div>
      <p className="text-sm text-gray-500 mb-4">
        Entreprises des secteurs visés par Beelix qui publient des offres data / IA : chaque offre est un signal de besoin.
      </p>
      <Tendance />
      <Puces options={options} valeur={secteur} onChange={setSecteur} />
      {loading && <Chargement />}
      {error && <Erreur message={error} />}
      {data && !loading && (
        <>
          <p className="text-xs text-gray-400 mb-3">
            {data.items.length} comptes affichés sur {data.total}
          </p>
          <div className="space-y-2">
            {data.items.map(c => (
              <div key={c.entreprise_normalise} className="border rounded-lg bg-white">
                <button
                  onClick={() => basculer(c.entreprise_normalise, c.secteur)}
                  className="w-full text-left p-4 hover:bg-gray-50 transition-colors"
                >
                  <div className="flex items-start justify-between gap-4 mb-2">
                    <div className="min-w-0">
                      <p className="font-medium text-gray-900">{c.entreprise_nom}</p>
                      <p className="text-xs text-gray-500">
                        {c.secteur_libelle}{c.naf_libelle ? ` · ${c.naf_libelle}` : ''}
                      </p>
                    </div>
                    <div className="text-right shrink-0">
                      <p className="text-sm font-semibold text-gray-900">{c.nb_offres} offre{c.nb_offres > 1 ? 's' : ''}</p>
                      <p className="text-xs text-gray-400">dernière : {formatDate(c.derniere_offre)}</p>
                    </div>
                  </div>
                  <Barre valeur={c.nb_offres} max={max} />
                  {c.titres_recents.length > 0 && (
                    <p className="text-xs text-gray-500 mt-2 truncate">{c.titres_recents.join(' · ')}</p>
                  )}
                </button>
                {ouvert === c.entreprise_normalise && (
                  <div className="border-t px-4 py-3 space-y-2">
                    {offres.length === 0 && <p className="text-xs text-gray-400">Chargement des offres…</p>}
                    {offres.map(o => (
                      <div key={o.id_unique} className="text-xs flex flex-wrap gap-x-3">
                        <span className="text-gray-400">{formatDate(o.date)}</span>
                        {o.url ? (
                          <a href={o.url} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
                            {o.titre}
                          </a>
                        ) : (
                          <span className="text-gray-700">{o.titre}</span>
                        )}
                        <span className="text-gray-400">
                          {[o.localisation_libelle, o.type_contrat_libelle].filter(Boolean).join(' · ')}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

// ─────────────────────────────────────────
// Concurrence
// ─────────────────────────────────────────

export function ConcurrenceView() {
  const [data, setData] = useState<ConcurrenceResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchBeelixConcurrence(25).then(setData).catch(e => setError(messageErreur(e)));
  }, []);

  if (error) return <Erreur message={error} />;
  if (!data) return <Chargement />;
  const max = data.items.length ? data.items[0].nb_offres : 0;

  return (
    <div>
      <p className="text-sm text-gray-500 mb-4">
        ESN, cabinets de conseil et d&apos;ingénierie qui publient des offres data / IA sur la période :
        {' '}{data.nb_concurrents} sociétés, {data.total_offres.toLocaleString('fr-FR')} offres.
        {data.rang_beelix !== null && <> Beelix est au rang <strong>{data.rang_beelix}</strong>.</>}
      </p>
      <div className="border rounded-lg bg-white divide-y">
        {data.items.map(c => (
          <div
            key={`${c.rang}-${c.entreprise_nom}`}
            className={`grid grid-cols-[40px_1fr_70px_60px] gap-3 items-center px-4 py-2 text-sm ${
              c.est_beelix ? 'bg-amber-50 font-semibold' : ''
            }`}
          >
            <span className="text-gray-400 text-xs">#{c.rang}</span>
            <div className="min-w-0">
              <p className="truncate text-gray-900">{c.entreprise_nom}</p>
              <Barre valeur={c.nb_offres} max={max} accent={c.est_beelix} />
            </div>
            <span className="text-right text-gray-700">{c.nb_offres}</span>
            <span className="text-right text-xs text-gray-400">{c.part} %</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────
// Besoins
// ─────────────────────────────────────────

export function BesoinsView() {
  const secteurs = useSecteursCibles();
  const [secteur, setSecteur] = useState<string | null>(null);
  const [data, setData] = useState<BesoinsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setData(null);
    setError(null);
    fetchBeelixBesoins(secteur ?? undefined).then(setData).catch(e => setError(messageErreur(e)));
  }, [secteur]);

  const options = [
    { id: null, label: 'Tous les secteurs Beelix' },
    ...secteurs.map(s => ({ id: s.secteur, label: s.libelle })),
    { id: 'concurrence', label: 'Concurrence' },
  ];
  const max = data && data.items.length ? data.items[0].nb_offres : 0;

  return (
    <div>
      <p className="text-sm text-gray-500 mb-4">
        Profils recherchés, détectés dans les titres des offres.
      </p>
      <Puces options={options} valeur={secteur} onChange={setSecteur} />
      {error && <Erreur message={error} />}
      {!data && !error && <Chargement />}
      {data && (
        <div className="border rounded-lg bg-white p-4 space-y-3">
          <p className="text-xs text-gray-400">{data.total.toLocaleString('fr-FR')} offres</p>
          {data.items.map(b => (
            <div key={b.famille} className="grid grid-cols-[180px_1fr_90px] gap-3 items-center text-sm">
              <span className="text-gray-700">{b.famille}</span>
              <Barre valeur={b.nb_offres} max={max} accent={secteur === 'concurrence'} />
              <span className="text-right text-xs text-gray-500">{b.nb_offres} · {b.part} %</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────
// Actualités
// ─────────────────────────────────────────

export function NewsView() {
  const [data, setData] = useState<NewsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchBeelixNews(20).then(setData).catch(e => setError(messageErreur(e)));
  }, []);

  if (error) return <Erreur message={error} />;
  if (!data) return <Chargement />;

  return (
    <div className="space-y-2">
      <p className="text-sm text-gray-500 mb-2">Beelix dans la presse (Google News).</p>
      {data.items.map(n => (
        <div key={n.id} className="border rounded-lg p-4 bg-white">
          <p className="text-xs text-gray-400 mb-1">{formatDate(n.date)}</p>
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
  );
}

// ─────────────────────────────────────────
// Ask AI
// ─────────────────────────────────────────

const SUGGESTED_QUESTIONS = [
  "Quelles entreprises de la banque ou de l'assurance recrutent des profils data en ce moment ?",
  "Quels acteurs du luxe et du retail publient des offres data ou IA ?",
  "Quelles entreprises de l'énergie recrutent en data ?",
  "Quels comptes médias et télécoms recherchent des profils data ou produit ?",
  "Quels grands comptes recherchent des compétences en IA générative ou LLM ?",
  "Quelles ESN ou cabinets de conseil recrutent des data engineers ?",
  "Que dit la presse sur Beelix ?",
];

export function RagView() {
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
      setResult(await fetchBeelixRag(query, 8));
    } catch (e: unknown) {
      setError(messageErreur(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <p className="text-sm text-gray-500 mb-4">
        Posez une question sur les comptes qui recrutent, la concurrence ou Beelix. Les réponses citent les offres utilisées.
      </p>

      <div className="flex gap-2 mb-4">
        <input
          type="text"
          value={question}
          onChange={e => setQuestion(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleSubmit()}
          placeholder="Ex : Quelles banques recrutent des data engineers ?"
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
                    <span className="text-gray-400 w-5">[{i + 1}]</span>
                    <div className="flex-1 min-w-0">
                      {src.url ? (
                        <a href={src.url} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
                          {src.title}
                        </a>
                      ) : (
                        <p className="text-gray-700">{src.title}</p>
                      )}
                      <p className="text-gray-400">
                        {src.source === 'offre' ? 'Offre' : 'Actualité'}
                        {src.date ? ` · ${src.date}` : ''}
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
