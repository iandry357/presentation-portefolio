'use client';

import { Fragment, useCallback, useEffect, useState } from 'react';
import { ArrowDown, ArrowUp, ChevronDown, ChevronRight, RefreshCw } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { deleteTypeEntreprise, getEntreprises, setTypeEntreprise } from '@/lib/api';
import { LIBELLES_TYPE_ENTREPRISE, formatDateCourte } from '@/lib/topOffres';
import { cn } from '@/lib/utils';
import {
  EntrepriseStat,
  EntreprisesResponse,
  OrdreTri,
  TriEntreprises,
  TypeEntrepriseCorrigeable,
} from '@/types';
import { COULEURS } from './TopCharts';
import EntrepriseOffres from './EntrepriseOffres';

// Paramètres
const PERIODES = [7, 14, 30];
const JOURS_DEFAUT = 30;
const LIMITE_PAS = 50;
const LIMITE_MAX = 200;
const DELAI_SAISIE_MS = 400;
const AUTO = '__auto__';   // valeur du sélecteur : supprimer la correction

// Sens du premier clic sur une colonne : alphabétique pour les textes, décroissant pour les nombres
const ORDRE_PAR_DEFAUT: Record<TriEntreprises, OrdreTri> = {
  nom: 'asc',
  secteur: 'asc',
  type: 'asc',
  offres: 'desc',
  coeur: 'desc',
  adjacent: 'desc',
  hors_cible: 'desc',
  a_lire: 'desc',
  score_max: 'desc',
  derniere_offre: 'desc',
};

// Mêmes teintes que la vue d'ensemble : rampe ordinale du bleu (cœur > adjacent > hors cible)
const SEGMENTS: { cle: 'nb_coeur' | 'nb_adjacent' | 'nb_hors_cible'; nom: string; couleur: string }[] = [
  { cle: 'nb_coeur', nom: 'cœur', couleur: COULEURS.ordinal500 },
  { cle: 'nb_adjacent', nom: 'adjacent', couleur: COULEURS.ordinal350 },
  { cle: 'nb_hors_cible', nom: 'hors cible', couleur: COULEURS.ordinal250 },
];

const CHAMP = 'text-sm border border-gray-200 rounded px-2 py-1 bg-white text-gray-700';

// Barre à 100 % de la répartition cœur / adjacent / hors cible, avec les nombres à côté
function MiniRepartition({ entreprise }: { entreprise: EntrepriseStat }) {
  const parts = SEGMENTS.filter(s => entreprise[s.cle] > 0);
  const resume = SEGMENTS.map(s => `${entreprise[s.cle]} ${s.nom}`).join(' · ');
  return (
    <div className="flex items-center gap-2" title={resume}>
      <div className="flex gap-0.5 h-3 w-28" role="img" aria-label={resume}>
        {parts.map((s, i) => (
          <div
            key={s.cle}
            className={cn(i === 0 && 'rounded-l', i === parts.length - 1 && 'rounded-r')}
            style={{ flex: `${entreprise[s.cle]} 1 0`, backgroundColor: s.couleur }}
          />
        ))}
      </div>
      <span className="text-xs text-gray-500 tabular-nums">
        {SEGMENTS.map(s => entreprise[s.cle]).join(' · ')}
      </span>
    </div>
  );
}

// Bouton d'en-tête de colonne : la colonne active affiche une flèche dans le sens du tri
function BoutonTri({
  cle,
  label,
  tri,
  ordre,
  onTri,
}: {
  cle: TriEntreprises;
  label: string;
  tri: TriEntreprises;
  ordre: OrdreTri;
  onTri: (cle: TriEntreprises) => void;
}) {
  const actif = tri === cle;
  return (
    <button
      onClick={() => onTri(cle)}
      title={`Trier : ${label.toLowerCase()}`}
      className={cn('inline-flex items-center gap-1 hover:text-gray-900 transition-colors', actif && 'text-gray-900')}
    >
      {label}
      {actif && (ordre === 'asc' ? <ArrowUp className="w-3 h-3" /> : <ArrowDown className="w-3 h-3" />)}
    </button>
  );
}

export default function EntreprisesView() {
  const [jours, setJours] = useState(JOURS_DEFAUT);
  const [tri, setTri] = useState<TriEntreprises>('coeur');
  const [ordre, setOrdre] = useState<OrdreTri>('desc');
  const [typeFiltre, setTypeFiltre] = useState('');
  const [inclureExclues, setInclureExclues] = useState(false);
  const [limite, setLimite] = useState(LIMITE_PAS);

  // Saisies de texte : appliquées après un court délai (une requête BigQuery par application)
  const [nomSaisi, setNomSaisi] = useState('');
  const [secteurSaisi, setSecteurSaisi] = useState('');
  const [q, setQ] = useState('');
  const [secteurFiltre, setSecteurFiltre] = useState('');

  const [data, setData] = useState<EntreprisesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [ouvertes, setOuvertes] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);
  const [erreurAction, setErreurAction] = useState<string | null>(null);

  useEffect(() => {
    const timer = setTimeout(() => {
      setQ(nomSaisi.trim());
      setSecteurFiltre(secteurSaisi.trim());
      setLimite(LIMITE_PAS);
    }, DELAI_SAISIE_MS);
    return () => clearTimeout(timer);
  }, [nomSaisi, secteurSaisi]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(
        await getEntreprises({
          jours,
          tri,
          ordre,
          typeEntreprise: typeFiltre || undefined,
          secteur: secteurFiltre || undefined,
          q: q || undefined,
          inclureExclues,
          limite,
        }),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erreur de chargement');
    } finally {
      setLoading(false);
    }
  }, [jours, tri, ordre, typeFiltre, secteurFiltre, q, inclureExclues, limite]);

  useEffect(() => {
    load();
  }, [load]);

  const basculer = (cle: string) => {
    setOuvertes(prev => {
      const suivant = new Set(prev);
      if (suivant.has(cle)) suivant.delete(cle);
      else suivant.add(cle);
      return suivant;
    });
  };

  // Clic sur une colonne : on la trie (sens naturel), un second clic inverse le sens
  const trier = (cle: TriEntreprises) => {
    if (cle === tri) {
      setOrdre(o => (o === 'asc' ? 'desc' : 'asc'));
    } else {
      setTri(cle);
      setOrdre(ORDRE_PAR_DEFAUT[cle]);
    }
    setLimite(LIMITE_PAS);
  };

  const changerType = async (entreprise: EntrepriseStat, valeur: string) => {
    setBusy(true);
    setErreurAction(null);
    try {
      if (valeur === AUTO) {
        await deleteTypeEntreprise(entreprise.entreprise_normalise);
      } else {
        await setTypeEntreprise(entreprise.entreprise_normalise, {
          type_entreprise: valeur as TypeEntrepriseCorrigeable,
        });
      }
      await load();
    } catch (e) {
      setErreurAction(e instanceof Error ? e.message : 'Erreur');
    } finally {
      setBusy(false);
    }
  };

  const entreprises = data?.entreprises ?? [];
  const total = data?.total ?? 0;

  const ariaSort = (...cles: TriEntreprises[]): 'ascending' | 'descending' | 'none' =>
    cles.includes(tri) ? (ordre === 'asc' ? 'ascending' : 'descending') : 'none';

  return (
    <div className="space-y-4">

      {/* Filtres : une seule ligne, au-dessus du tableau */}
      <div className="flex flex-wrap items-end gap-x-4 gap-y-3 text-sm text-gray-600">
        <label className="inline-flex flex-col gap-1">
          Période
          <select
            value={jours}
            onChange={e => {
              setJours(Number(e.target.value));
              setLimite(LIMITE_PAS);
            }}
            className={CHAMP}
          >
            {PERIODES.map(j => (
              <option key={j} value={j}>{j} jours</option>
            ))}
          </select>
        </label>

        <label className="inline-flex flex-col gap-1">
          Type
          <select
            value={typeFiltre}
            onChange={e => {
              setTypeFiltre(e.target.value);
              setLimite(LIMITE_PAS);
            }}
            className={CHAMP}
          >
            <option value="">Tous</option>
            {Object.entries(LIBELLES_TYPE_ENTREPRISE).map(([valeur, nom]) => (
              <option key={valeur} value={valeur}>{nom}</option>
            ))}
          </select>
        </label>

        <label className="inline-flex flex-col gap-1">
          Secteur
          <input
            type="text"
            list="secteurs-top-offres"
            value={secteurSaisi}
            onChange={e => setSecteurSaisi(e.target.value)}
            placeholder="ex : information"
            className={cn(CHAMP, 'w-48')}
          />
          <datalist id="secteurs-top-offres">
            {(data?.secteurs ?? []).map(secteur => (
              <option key={secteur} value={secteur} />
            ))}
          </datalist>
        </label>

        <label className="inline-flex flex-col gap-1">
          Nom
          <input
            type="text"
            value={nomSaisi}
            onChange={e => setNomSaisi(e.target.value)}
            placeholder="ex : capgemini"
            className={cn(CHAMP, 'w-40')}
          />
        </label>

        <label className="inline-flex items-center gap-2 cursor-pointer pb-1">
          <input
            type="checkbox"
            checked={inclureExclues}
            onChange={e => {
              setInclureExclues(e.target.checked);
              setLimite(LIMITE_PAS);
            }}
            className="w-4 h-4 rounded border-gray-300"
          />
          Inclure les entreprises exclues
        </label>

        <button
          onClick={() => load()}
          disabled={loading}
          title="Rafraîchir"
          className="p-1.5 mb-0.5 text-gray-500 hover:text-gray-700 transition-colors"
        >
          <RefreshCw className={cn('w-4 h-4', loading && 'animate-spin')} />
        </button>
      </div>

      {/* Légende de la barre de répartition */}
      <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-600">
        {SEGMENTS.map(s => (
          <li key={s.cle} className="inline-flex items-center gap-1.5">
            <span className="inline-block w-3 h-3 rounded-sm" style={{ backgroundColor: s.couleur }} />
            Offres {s.nom}
          </li>
        ))}
        <li className="text-gray-400">Offres scorées sur la période, une offre republiée ne compte qu&apos;une fois</li>
      </ul>

      {error && (
        <div className="text-sm text-red-600 bg-red-50 px-4 py-3 rounded-lg">{error}</div>
      )}
      {erreurAction && (
        <div className="text-sm text-red-700 bg-red-50 px-4 py-3 rounded-lg">{erreurAction}</div>
      )}

      {!data && loading && <div className="h-48 border rounded-lg bg-white animate-pulse" />}

      {data && entreprises.length === 0 && !loading && (
        <p className="text-center text-sm text-gray-500 py-12">
          Aucune entreprise ne correspond aux filtres sur cette période.
        </p>
      )}

      {entreprises.length > 0 && (
        <>
          <p className="text-xs text-gray-500">
            {entreprises.length} entreprise{entreprises.length > 1 ? 's' : ''} affichée
            {entreprises.length > 1 ? 's' : ''} sur {total}
          </p>

          {/* Pendant un rechargement, le tableau précédent reste affiché en atténué */}
          <div className={cn('border rounded-lg bg-white overflow-x-auto transition-opacity', loading && 'opacity-60')}>
            <table className="w-full text-sm min-w-[760px]">
              <thead>
                <tr className="text-left text-xs text-gray-500 border-b align-top">
                  <th className="px-3 py-2 font-medium" aria-sort={ariaSort('nom', 'derniere_offre')}>
                    <div className="flex flex-wrap items-center gap-x-3">
                      <BoutonTri cle="nom" label="Entreprise" tri={tri} ordre={ordre} onTri={trier} />
                      <BoutonTri cle="derniere_offre" label="Dernière offre" tri={tri} ordre={ordre} onTri={trier} />
                    </div>
                  </th>
                  <th className="px-3 py-2 font-medium" aria-sort={ariaSort('secteur')}>
                    <BoutonTri cle="secteur" label="Secteur" tri={tri} ordre={ordre} onTri={trier} />
                  </th>
                  <th className="px-3 py-2 font-medium" aria-sort={ariaSort('type')}>
                    <BoutonTri cle="type" label="Type" tri={tri} ordre={ordre} onTri={trier} />
                  </th>
                  <th className="px-3 py-2 font-medium" aria-sort={ariaSort('offres')}>
                    <div className="flex justify-end">
                      <BoutonTri cle="offres" label="Offres" tri={tri} ordre={ordre} onTri={trier} />
                    </div>
                  </th>
                  <th className="px-3 py-2 font-medium" aria-sort={ariaSort('coeur', 'adjacent', 'hors_cible')}>
                    <div>Répartition</div>
                    <div className="flex flex-wrap items-center gap-x-3 font-normal">
                      <BoutonTri cle="coeur" label="Cœur" tri={tri} ordre={ordre} onTri={trier} />
                      <BoutonTri cle="adjacent" label="Adjacent" tri={tri} ordre={ordre} onTri={trier} />
                      <BoutonTri cle="hors_cible" label="Hors cible" tri={tri} ordre={ordre} onTri={trier} />
                    </div>
                  </th>
                  <th className="px-3 py-2 font-medium" aria-sort={ariaSort('a_lire')}>
                    <div className="flex justify-end">
                      <BoutonTri cle="a_lire" label="À lire" tri={tri} ordre={ordre} onTri={trier} />
                    </div>
                  </th>
                  <th className="px-3 py-2 font-medium" aria-sort={ariaSort('score_max')}>
                    <div className="flex justify-end">
                      <BoutonTri cle="score_max" label="Score max" tri={tri} ordre={ordre} onTri={trier} />
                    </div>
                  </th>
                </tr>
              </thead>
              <tbody>
                {entreprises.map(entreprise => {
                  const ouverte = ouvertes.has(entreprise.entreprise_normalise);
                  const secteur =
                    entreprise.secteur && entreprise.secteur !== 'NON DETERMINE' ? entreprise.secteur : '—';
                  return (
                    <Fragment key={entreprise.entreprise_normalise}>
                      <tr className="border-b last:border-0 align-top">
                        <td className="px-3 py-2">
                          <button
                            onClick={() => basculer(entreprise.entreprise_normalise)}
                            aria-expanded={ouverte}
                            className="flex items-start gap-1.5 text-left"
                          >
                            {ouverte ? (
                              <ChevronDown className="w-4 h-4 mt-0.5 shrink-0 text-gray-500" />
                            ) : (
                              <ChevronRight className="w-4 h-4 mt-0.5 shrink-0 text-gray-500" />
                            )}
                            <span>
                              <span className="font-medium text-gray-900">
                                {entreprise.entreprise_nom ?? entreprise.entreprise_normalise}
                              </span>
                              {entreprise.entreprise_exclue && (
                                <Badge variant="secondary" className="ml-2 text-xs">Exclue</Badge>
                              )}
                              {entreprise.derniere_offre && (
                                <span className="block text-xs text-gray-500">
                                  Dernière offre {formatDateCourte(entreprise.derniere_offre)}
                                </span>
                              )}
                            </span>
                          </button>
                        </td>
                        <td className="px-3 py-2 text-gray-600" title={entreprise.naf_libelle ?? undefined}>
                          {secteur}
                        </td>
                        <td className="px-3 py-2">
                          <select
                            value={entreprise.type_entreprise}
                            onChange={e => changerType(entreprise, e.target.value)}
                            disabled={busy}
                            className="text-xs border border-gray-200 rounded px-1.5 py-1 bg-white text-gray-700 disabled:opacity-60"
                          >
                            {Object.entries(LIBELLES_TYPE_ENTREPRISE).map(([valeur, nom]) => (
                              <option key={valeur} value={valeur} disabled={valeur === 'non_identifie'}>
                                {nom}
                              </option>
                            ))}
                            {entreprise.type_entreprise_corrige && (
                              <option value={AUTO}>↩ Revenir à l&apos;automatique</option>
                            )}
                          </select>
                          {entreprise.type_entreprise_corrige && (
                            <span className="ml-1 text-xs text-gray-400">(corrigé)</span>
                          )}
                        </td>
                        <td className="px-3 py-2 text-right tabular-nums">{entreprise.nb_offres}</td>
                        <td className="px-3 py-2">
                          <MiniRepartition entreprise={entreprise} />
                        </td>
                        <td className="px-3 py-2 text-right tabular-nums">{entreprise.nb_a_lire}</td>
                        <td className="px-3 py-2 text-right tabular-nums">{entreprise.score_max ?? '—'}</td>
                      </tr>

                      {/* Offres de l'entreprise, chargées à la demande */}
                      {ouverte && (
                        <tr className="border-b last:border-0 bg-gray-50">
                          <td colSpan={7} className="px-3 py-3">
                            <EntrepriseOffres entreprise={entreprise.entreprise_normalise} jours={jours} />
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>

          {entreprises.length < total && limite < LIMITE_MAX && (
            <div className="text-center">
              <button
                onClick={() => setLimite(l => Math.min(l + LIMITE_PAS, LIMITE_MAX))}
                disabled={loading}
                className="px-4 py-2 text-sm border rounded-lg text-gray-700 hover:bg-gray-50 transition-colors disabled:opacity-50"
              >
                Afficher plus
              </button>
            </div>
          )}
          {entreprises.length < total && limite >= LIMITE_MAX && (
            <p className="text-center text-xs text-gray-500">
              Affinez les filtres pour réduire la liste.
            </p>
          )}
        </>
      )}
    </div>
  );
}
