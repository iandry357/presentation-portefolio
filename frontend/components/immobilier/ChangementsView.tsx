'use client';

import { useEffect, useState } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import {
  ChangementsResponse,
  Chauffage,
  ETIQUETTES,
  EtiquetteDpe,
  getChangements,
} from '@/lib/immobilierApi';
import {
  ARRONDISSEMENTS,
  CLASSE_CHAMP,
  LIBELLES_CHAUFFAGE,
  LIBELLES_LECTURE,
  formatDate,
  formatEntier,
  libelleArrondissement,
} from '@/lib/immobilier';

// Paramètres
const TAILLE_PAGE = 20;

interface Filtres {
  arrondissement: number | null;
  etiquette: EtiquetteDpe | '';
  chauffage: Chauffage | '';
  postReforme: '' | 'oui' | 'non';
  dateMin: string;
  dateMax: string;
}

const FILTRES_VIDES: Filtres = {
  arrondissement: null,
  etiquette: '',
  chauffage: '',
  postReforme: '',
  dateMin: '',
  dateMax: '',
};

export default function ChangementsView() {
  const [filtres, setFiltres] = useState<Filtres>(FILTRES_VIDES);
  const [page, setPage] = useState(1);
  const [data, setData] = useState<ChangementsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Un changement de filtre ramène à la première page
  const changer = (partiel: Partial<Filtres>) => {
    setFiltres(f => ({ ...f, ...partiel }));
    setPage(1);
  };

  useEffect(() => {
    let annule = false;   // ignore la réponse d'une requête dépassée par une plus récente
    setLoading(true);
    setError(null);
    getChangements({
      page,
      taille: TAILLE_PAGE,
      arrondissement: filtres.arrondissement ?? undefined,
      etiquette: filtres.etiquette || undefined,
      chauffage: filtres.chauffage || undefined,
      postReforme: filtres.postReforme === '' ? undefined : filtres.postReforme === 'oui',
      dateMin: filtres.dateMin || undefined,
      dateMax: filtres.dateMax || undefined,
    })
      .then(r => {
        if (!annule) setData(r);
      })
      .catch(e => {
        if (!annule) setError(e instanceof Error ? e.message : 'Erreur de chargement');
      })
      .finally(() => {
        if (!annule) setLoading(false);
      });
    return () => {
      annule = true;
    };
  }, [filtres, page]);

  const filtresActifs = JSON.stringify(filtres) !== JSON.stringify(FILTRES_VIDES);

  return (
    <div className="space-y-4">

      {/* Filtres : une seule ligne, au-dessus de ce qu'ils portent */}
      <div className="flex flex-wrap items-center gap-4 text-sm text-gray-600">
        <label className="inline-flex items-center gap-2">
          Arrondissement
          <select
            value={filtres.arrondissement ?? ''}
            onChange={e => changer({ arrondissement: e.target.value ? Number(e.target.value) : null })}
            className={CLASSE_CHAMP}
          >
            <option value="">Tous</option>
            {ARRONDISSEMENTS.map(n => (
              <option key={n} value={n}>{libelleArrondissement(n)}</option>
            ))}
          </select>
        </label>
        <label className="inline-flex items-center gap-2">
          Étiquette
          <select
            value={filtres.etiquette}
            onChange={e => changer({ etiquette: e.target.value as EtiquetteDpe | '' })}
            className={CLASSE_CHAMP}
          >
            <option value="">Toutes</option>
            {ETIQUETTES.map(et => (
              <option key={et} value={et}>{et}</option>
            ))}
          </select>
        </label>
        <label className="inline-flex items-center gap-2">
          Chauffage
          <select
            value={filtres.chauffage}
            onChange={e => changer({ chauffage: e.target.value as Chauffage | '' })}
            className={CLASSE_CHAMP}
          >
            <option value="">Tous</option>
            {(Object.keys(LIBELLES_CHAUFFAGE) as Chauffage[]).map(c => (
              <option key={c} value={c}>{LIBELLES_CHAUFFAGE[c]}</option>
            ))}
          </select>
        </label>
        <label className="inline-flex items-center gap-2">
          Depuis 2026
          <select
            value={filtres.postReforme}
            onChange={e => changer({ postReforme: e.target.value as Filtres['postReforme'] })}
            className={CLASSE_CHAMP}
          >
            <option value="">Indifférent</option>
            <option value="oui">Oui</option>
            <option value="non">Non</option>
          </select>
        </label>
        <label className="inline-flex items-center gap-2">
          Du
          <input
            type="date"
            value={filtres.dateMin}
            onChange={e => changer({ dateMin: e.target.value })}
            className={CLASSE_CHAMP}
          />
        </label>
        <label className="inline-flex items-center gap-2">
          Au
          <input
            type="date"
            value={filtres.dateMax}
            onChange={e => changer({ dateMax: e.target.value })}
            className={CLASSE_CHAMP}
          />
        </label>
        {filtresActifs && (
          <button
            onClick={() => changer(FILTRES_VIDES)}
            className="text-sm text-blue-700 hover:underline"
          >
            Réinitialiser
          </button>
        )}
      </div>

      {error && (
        <div className="text-sm text-red-600 bg-red-50 px-4 py-3 rounded-lg">{error}</div>
      )}

      {!data && loading && <div className="h-64 border rounded-lg bg-white animate-pulse" />}

      {data && (
        // Pendant un rechargement, le contenu précédent reste affiché en atténué
        <div className={cn('space-y-4 transition-opacity', loading && 'opacity-60')}>

          <p className="text-sm text-gray-600">
            <span className="font-semibold text-gray-900">{formatEntier(data.total)}</span> DPE refaits
            {data.total > 0 && (
              <>
                , dont{' '}
                <span className="font-semibold text-gray-900">{formatEntier(data.nb_recalcul_probable)}</span>{' '}
                en recalcul 2026 probable
              </>
            )}
          </p>

          {data.lignes.length === 0 ? (
            <p className="text-sm text-gray-400 py-8 text-center border rounded-lg bg-white">
              Aucun DPE refait pour ces filtres.
            </p>
          ) : (
            <div className="border rounded-lg bg-white overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-gray-500 border-b">
                    <th className="px-3 py-2 font-medium">Date</th>
                    <th className="px-3 py-2 font-medium">Adresse</th>
                    <th className="px-3 py-2 font-medium">Arr.</th>
                    <th className="px-3 py-2 font-medium">Étiquette</th>
                    <th className="px-3 py-2 font-medium">Chauffage</th>
                    <th className="px-3 py-2 font-medium">Lecture</th>
                  </tr>
                </thead>
                <tbody>
                  {data.lignes.map(l => (
                    <tr key={l.numero_dpe} className="border-b last:border-0">
                      <td className="px-3 py-2 text-gray-700 whitespace-nowrap">
                        {formatDate(l.date_etablissement_dpe)}
                      </td>
                      <td className="px-3 py-2 text-gray-900">{l.adresse_ban ?? '—'}</td>
                      <td className="px-3 py-2 text-gray-700 whitespace-nowrap">
                        {libelleArrondissement(l.arrondissement)}
                      </td>
                      <td className="px-3 py-2">
                        <Badge variant="outline">{l.etiquette_dpe}</Badge>
                      </td>
                      <td className="px-3 py-2 text-gray-700">{l.type_energie_principale_chauffage ?? '—'}</td>
                      <td className="px-3 py-2">
                        <Badge
                          variant="outline"
                          className={cn(
                            'whitespace-nowrap',
                            l.lecture === 'recalcul_2026_probable' && 'bg-blue-50 text-blue-700 border-blue-200',
                          )}
                        >
                          {LIBELLES_LECTURE[l.lecture] ?? l.lecture}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {data.nb_pages > 1 && (
            <div className="flex items-center justify-between text-sm text-gray-600">
              <button
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={data.page <= 1 || loading}
                className="inline-flex items-center gap-1 px-3 py-1.5 border rounded bg-white hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <ChevronLeft className="w-4 h-4" />
                Précédent
              </button>
              <span>
                Page {data.page} sur {data.nb_pages}
              </span>
              <button
                onClick={() => setPage(p => p + 1)}
                disabled={data.page >= data.nb_pages || loading}
                className="inline-flex items-center gap-1 px-3 py-1.5 border rounded bg-white hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                Suivant
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          )}

          <p className="text-xs text-gray-500">
            « Recalcul 2026 probable » : chauffage électrique et DPE établi depuis le 1er janvier 2026
            (nouveau coefficient de l’électricité). Les autres DPE sont simplement refaits : l’étiquette
            précédente n’est pas disponible dans les données ouvertes.
          </p>
        </div>
      )}
    </div>
  );
}
