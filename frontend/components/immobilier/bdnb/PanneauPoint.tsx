'use client';

import type { PointReponse } from '@/lib/immobilierBdnbApi';
import { formatEntier } from '@/lib/immobilier';
import type { PointCarte } from './CarteClic';

interface Props {
  point: PointCarte | null;
  donnees: PointReponse | null;
  enCours: boolean;
  erreur: string | null;
}

// Adresse, parcelle cadastrale et zone d'urbanisme du point cliqué (API ouvertes de l'IGN)
export default function PanneauPoint({ point, donnees, enCours, erreur }: Props) {
  if (!point) return null;
  const parcelle = donnees?.parcelle ?? null;
  const adresse = donnees?.adresse ?? null;
  const zones = donnees?.zones_urbanisme ?? [];

  return (
    <div className="mt-4" aria-live="polite">
      {enCours && <p className="text-sm text-gray-500 animate-pulse">Recherche de l’adresse, de la parcelle et du zonage…</p>}
      {erreur && <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{erreur}</p>}

      {donnees && !enCours && (
        <div className="border rounded-lg bg-gray-50 p-3 space-y-2">
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Adresse la plus proche</p>
            <p className="text-sm text-gray-900">
              {adresse ? adresse.libelle : 'non trouvée'}
              {adresse?.distance_m != null && <span className="text-gray-500"> (à {adresse.distance_m} m)</span>}
            </p>
          </div>

          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Parcelle cadastrale</p>
            {parcelle ? (
              <p className="text-sm text-gray-900">
                Section {parcelle.section ?? '?'}, numéro {parcelle.numero ?? '?'}
                {parcelle.contenance_m2 != null && (
                  <span className="text-gray-500"> · {formatEntier(parcelle.contenance_m2)} m²</span>
                )}
              </p>
            ) : (
              <p className="text-sm text-gray-600">
                Ce point n’est dans aucune parcelle (voie publique ?). Zoomez et cliquez à l’intérieur d’un immeuble.
              </p>
            )}
          </div>

          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Zone d’urbanisme (PLU)</p>
            {zones.length > 0 ? (
              zones.map((zone, i) => (
                <p key={i} className="text-sm text-gray-900">
                  {zone.code ?? '?'}
                  {zone.libelle && <span className="text-gray-600"> — {zone.libelle}</span>}
                </p>
              ))
            ) : (
              <p className="text-sm text-gray-600">Aucune zone trouvée.</p>
            )}
            <p className="text-xs text-gray-500">À titre indicatif : le règlement de la zone fait foi.</p>
          </div>

          {donnees.donnees_partielles && (
            <p className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded px-2 py-1">
              Une partie des informations de l’IGN n’a pas pu être récupérée.
            </p>
          )}
          <p className="text-[11px] text-gray-400">
            Source : IGN (Géoplateforme pour l’adresse, API Carto pour le cadastre et le Géoportail de l’urbanisme).
          </p>
        </div>
      )}
    </div>
  );
}

