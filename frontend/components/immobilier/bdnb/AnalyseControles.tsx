'use client';

import { cn } from '@/lib/utils';
import type { DimensionAnalyse, FiltresAnalyse, SourceAnalyse } from '@/lib/immobilierBdnbApi';
import { DIMENSIONS_ANALYSE, SOURCES_ANALYSE, libelleDimension, libelleModalite } from '@/lib/immobilierBdnb';

interface Props {
  source: SourceAnalyse;
  onSource: (source: SourceAnalyse) => void;
  axe: DimensionAnalyse;
  onAxe: (axe: DimensionAnalyse) => void;
  croiser: DimensionAnalyse | null;
  onCroiser: (axe: DimensionAnalyse | null) => void;
  modalites: Partial<Record<DimensionAnalyse, string[]>>;   // valeurs proposées : meta.modalites de la dernière réponse
  filtres: FiltresAnalyse;
  onFiltres: (filtres: FiltresAnalyse) => void;
}

function nbFiltresActifs(filtres: FiltresAnalyse): number {
  return Object.values(filtres).filter(valeurs => valeurs && valeurs.length > 0).length;
}

// Ajoute ou retire une valeur ; une dimension sans valeur quitte les filtres
function basculer(filtres: FiltresAnalyse, dimension: DimensionAnalyse, valeur: string): FiltresAnalyse {
  const actuelles = filtres[dimension] ?? [];
  const suivantes = actuelles.includes(valeur) ? actuelles.filter(v => v !== valeur) : [...actuelles, valeur];
  const reste = { ...filtres };
  if (suivantes.length === 0) delete reste[dimension];
  else reste[dimension] = suivantes;
  return reste;
}

function Selecteur({
  libelle,
  valeur,
  options,
  onChange,
}: {
  libelle: string;
  valeur: string;
  options: { id: string; libelle: string }[];
  onChange: (valeur: string) => void;
}) {
  return (
    <label className="block text-sm text-gray-600">
      {libelle}
      <select
        value={valeur}
        onChange={e => onChange(e.target.value)}
        className="mt-1 w-full border rounded-lg bg-white px-3 py-2 text-sm text-gray-700"
      >
        {options.map(o => (
          <option key={o.id} value={o.id}>
            {o.libelle}
          </option>
        ))}
      </select>
    </label>
  );
}

export default function AnalyseControles({
  source, onSource, axe, onAxe, croiser, onCroiser, modalites, filtres, onFiltres,
}: Props) {
  const dimensions = DIMENSIONS_ANALYSE[source];
  const nbActifs = nbFiltresActifs(filtres);

  return (
    <div className="border rounded-lg bg-white p-4 space-y-4">
      <div className="inline-flex overflow-hidden rounded border border-gray-200" role="group" aria-label="Source">
        {SOURCES_ANALYSE.map(({ id, libelle }) => (
          <button
            key={id}
            type="button"
            onClick={() => onSource(id)}
            aria-pressed={source === id}
            className={cn(
              'px-4 py-1.5 text-sm transition-colors',
              source === id ? 'bg-blue-50 text-blue-700' : 'bg-white text-gray-600 hover:bg-gray-50',
            )}
          >
            {libelle}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <Selecteur
          libelle="Regrouper par"
          valeur={axe}
          options={dimensions.map(d => ({ id: d, libelle: libelleDimension(d, source) }))}
          onChange={valeur => onAxe(valeur as DimensionAnalyse)}
        />
        <Selecteur
          libelle="Croiser avec"
          valeur={croiser ?? ''}
          options={[
            { id: '', libelle: 'Aucun' },
            ...dimensions.filter(d => d !== axe).map(d => ({ id: d, libelle: libelleDimension(d, source) })),
          ]}
          onChange={valeur => onCroiser(valeur === '' ? null : (valeur as DimensionAnalyse))}
        />
      </div>

      <details>
        <summary className="cursor-pointer text-sm text-blue-700 hover:underline select-none">
          Filtres{nbActifs > 0 ? ` (${nbActifs} actif${nbActifs > 1 ? 's' : ''})` : ''}
        </summary>
        <div className="mt-3 space-y-3">
          {dimensions.map(dimension => {
            const valeurs = modalites[dimension] ?? [];
            if (valeurs.length === 0) return null;
            return (
              <fieldset key={dimension}>
                <legend className="text-xs font-medium text-gray-500 mb-1">{libelleDimension(dimension, source)}</legend>
                <div className="flex flex-wrap gap-1.5">
                  {valeurs.map(valeur => {
                    const actif = filtres[dimension]?.includes(valeur) ?? false;
                    return (
                      <button
                        key={valeur}
                        type="button"
                        onClick={() => onFiltres(basculer(filtres, dimension, valeur))}
                        aria-pressed={actif}
                        className={cn(
                          'px-2.5 py-1 text-xs rounded-full border transition-colors',
                          actif
                            ? 'bg-blue-50 border-blue-300 text-blue-700'
                            : 'bg-white border-gray-200 text-gray-600 hover:bg-gray-50',
                        )}
                      >
                        {libelleModalite(dimension, valeur)}
                      </button>
                    );
                  })}
                </div>
              </fieldset>
            );
          })}
          {nbActifs > 0 && (
            <button
              type="button"
              onClick={() => onFiltres({})}
              className="text-xs text-blue-700 hover:underline"
            >
              Réinitialiser les filtres
            </button>
          )}
        </div>
      </details>
    </div>
  );
}
