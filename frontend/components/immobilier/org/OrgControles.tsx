'use client';

import { cn } from '@/lib/utils';
import type { CubeOrg, FiltresOrg } from '@/lib/immobilierOrgApi';
import { CUBES_ORG, descriptionDimensionOrg, libelleDimensionOrg, libelleModaliteOrg, trierModalites } from '@/lib/immobilierOrgCubes';

interface Props {
  cube: CubeOrg;
  axe: string;
  onAxe: (axe: string) => void;
  croiser: string | null;
  onCroiser: (axe: string | null) => void;
  modalites: Record<string, string[]>;   // valeurs proposées : meta.modalites de la dernière réponse
  filtres: FiltresOrg;
  onFiltres: (filtres: FiltresOrg) => void;
}

function nbFiltresActifs(filtres: FiltresOrg): number {
  return Object.values(filtres).filter(valeurs => valeurs.length > 0).length;
}

// Ajoute ou retire une valeur ; une dimension sans valeur quitte les filtres
function basculer(filtres: FiltresOrg, dimension: string, valeur: string): FiltresOrg {
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
  aide,
}: {
  libelle: string;
  valeur: string;
  options: { id: string; libelle: string }[];
  onChange: (valeur: string) => void;
  aide: string;
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
      <span className="block mt-1 text-xs text-gray-500">{aide}</span>
    </label>
  );
}

export default function OrgControles({ cube, axe, onAxe, croiser, onCroiser, modalites, filtres, onFiltres }: Props) {
  const dimensions = CUBES_ORG[cube].dimensions;
  const nbActifs = nbFiltresActifs(filtres);

  return (
    <div className="border rounded-lg bg-white p-4 space-y-4">
      <p className="text-sm text-gray-600">
        <span className="font-medium text-gray-900">Regrouper par</span> : ce qui forme les barres du graphique, une par
        valeur. <span className="font-medium text-gray-900">Croiser avec</span> : ajoute un second critère, le graphique
        devient un tableau à deux entrées.
      </p>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <Selecteur
          libelle="Regrouper par"
          valeur={axe}
          options={dimensions.map(d => ({ id: d, libelle: libelleDimensionOrg(d, cube) }))}
          onChange={onAxe}
          aide={descriptionDimensionOrg(axe, cube)}
        />
        <Selecteur
          libelle="Croiser avec"
          valeur={croiser ?? ''}
          options={[
            { id: '', libelle: 'Aucun' },
            ...dimensions.filter(d => d !== axe).map(d => ({ id: d, libelle: libelleDimensionOrg(d, cube) })),
          ]}
          onChange={valeur => onCroiser(valeur === '' ? null : valeur)}
          aide={croiser ? descriptionDimensionOrg(croiser, cube) : 'Facultatif : sans second critère, le résultat est un graphique.'}
        />
      </div>

      <details>
        <summary className="cursor-pointer text-sm text-blue-700 hover:underline select-none">
          Explication de chaque critère
        </summary>
        <dl className="mt-3 space-y-2 text-sm text-gray-600">
          {dimensions.map(d => (
            <div key={d}>
              <dt className="font-medium text-gray-800">{libelleDimensionOrg(d, cube)}</dt>
              <dd>{descriptionDimensionOrg(d, cube)}</dd>
            </div>
          ))}
        </dl>
        <p className="mt-3 text-sm text-gray-600">
          <span className="font-medium text-gray-800">Filtres</span> : ne garder que certaines valeurs d’un critère, par
          exemple seulement le 9e et le 10e arrondissement.
        </p>
      </details>

      <details>
        <summary className="cursor-pointer text-sm text-blue-700 hover:underline select-none">
          Filtres{nbActifs > 0 ? ` (${nbActifs} actif${nbActifs > 1 ? 's' : ''})` : ''}
        </summary>
        <div className="mt-3 space-y-3">
          {dimensions.map(dimension => {
            const valeurs = trierModalites(dimension, modalites[dimension] ?? []);
            if (valeurs.length === 0) return null;
            return (
              <fieldset key={dimension}>
                <legend className="text-xs font-medium text-gray-500 mb-1">{libelleDimensionOrg(dimension, cube)}</legend>
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
                        {libelleModaliteOrg(dimension, valeur)}
                      </button>
                    );
                  })}
                </div>
              </fieldset>
            );
          })}
          {nbActifs > 0 && (
            <button type="button" onClick={() => onFiltres({})} className="text-xs text-blue-700 hover:underline">
              Réinitialiser les filtres
            </button>
          )}
        </div>
      </details>
    </div>
  );
}
