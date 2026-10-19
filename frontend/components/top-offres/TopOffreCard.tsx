'use client';

import { ExternalLink, TriangleAlert } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { TopDecisionType, TopOffre, TypeEntrepriseCorrigeable } from '@/types';
import {
  LIBELLES_ALERTE,
  LIBELLES_CATEGORIE,
  LIBELLES_TYPE_ENTREPRISE,
  formatDateCourte,
  libelle,
  libelleSource,
  lienOffre,
} from '@/lib/topOffres';

const AUTO = '__auto__';   // valeur du sélecteur : supprimer la correction

interface TopOffreCardProps {
  offre: TopOffre;
  busy: boolean;                                       // une action est en cours sur cette offre
  onDecision: (offre: TopOffre, decision: TopDecisionType) => void;
  onTypeChange: (offre: TopOffre, type: TypeEntrepriseCorrigeable | null) => void;   // null : retour à l'automatique
}

export default function TopOffreCard({ offre, busy, onDecision, onTypeChange }: TopOffreCardProps) {
  const lien = lienOffre(offre);
  const entreprise = [offre.entreprise_nom, offre.localisation_libelle].filter(Boolean).join(' · ');
  const details = [libelleSource(offre.source), offre.type_contrat_libelle, offre.salaire_libelle]
    .filter(Boolean)
    .join(' · ');
  const secteur = offre.secteur && offre.secteur !== 'NON DETERMINE' ? offre.secteur : null;

  const handleType = (valeur: string) => {
    onTypeChange(offre, valeur === AUTO ? null : (valeur as TypeEntrepriseCorrigeable));
  };

  return (
    <div className="border rounded-lg bg-white p-4 space-y-3 min-w-0">

      {/* En-tête : titre, entreprise, score */}
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-base font-semibold text-gray-900 break-words">{offre.titre}</h3>
          <p className="text-sm text-gray-600">{entreprise || 'Entreprise non renseignée'}</p>
          {details && <p className="text-xs text-gray-500 mt-0.5">{details}</p>}
        </div>
        <div className="shrink-0 text-right">
          <p className="text-2xl font-bold text-gray-900 leading-none">{offre.score ?? '—'}</p>
          <p className="text-xs text-gray-500 mt-1">{libelle(LIBELLES_CATEGORIE, offre.categorie)}</p>
        </div>
      </div>

      {/* Raison du score */}
      {offre.raison && (
        <p className="text-sm text-gray-600 italic break-words">« {offre.raison} »</p>
      )}

      {/* Alertes, secteur, entreprise exclue */}
      {(offre.alertes.length > 0 || secteur || offre.entreprise_exclue) && (
        <div className="flex flex-wrap items-center gap-2">
          {offre.alertes.map(alerte => (
            <span key={alerte} className="inline-flex items-center gap-1 text-xs text-gray-600">
              <TriangleAlert className="w-3.5 h-3.5" />
              {libelle(LIBELLES_ALERTE, alerte)}
            </span>
          ))}
          {secteur && <Badge variant="outline" className="text-xs max-w-full h-auto whitespace-normal text-left">{secteur}</Badge>}
          {offre.entreprise_exclue && <Badge variant="secondary" className="text-xs">Entreprise exclue</Badge>}
        </div>
      )}

      {/* Type d'entreprise (correction sur la carte) */}
      <label className="inline-flex items-center gap-1.5 text-xs text-gray-500">
        Type d&apos;entreprise
        <select
          value={offre.type_entreprise}
          onChange={e => handleType(e.target.value)}
          disabled={busy || !offre.entreprise_normalise}
          className="text-xs border border-gray-200 rounded px-1.5 py-1 bg-white text-gray-700 disabled:opacity-60"
        >
          {Object.entries(LIBELLES_TYPE_ENTREPRISE).map(([valeur, nom]) => (
            <option key={valeur} value={valeur} disabled={valeur === 'non_identifie'}>
              {nom}
            </option>
          ))}
          {offre.type_entreprise_corrige && <option value={AUTO}>↩ Revenir à l&apos;automatique</option>}
        </select>
        {offre.type_entreprise_corrige && <span className="text-gray-400">(corrigé)</span>}
      </label>

      {/* Pied : date, lien, décisions */}
      <div className="flex flex-col sm:flex-row sm:flex-wrap sm:items-center sm:justify-between gap-3 pt-3 border-t">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-gray-500">
          {offre.date_publication && <span>Publiée le {formatDateCourte(offre.date_publication)}</span>}
          {lien ? (
            <a
              href={lien}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-blue-600 hover:underline"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              Voir l&apos;offre
            </a>
          ) : (
            <span className="text-gray-400">Lien indisponible</span>
          )}
        </div>
        <div className="flex gap-2 w-full sm:w-auto">
          <button
            onClick={() => onDecision(offre, 'pas_interesse')}
            disabled={busy}
            className="px-3 py-1.5 text-sm border rounded-lg text-gray-700 hover:bg-gray-50 transition-colors disabled:opacity-50"
          >
            Pas intéressé
          </button>
          <button
            onClick={() => onDecision(offre, 'interesse')}
            disabled={busy}
            className="px-3 py-1.5 text-sm rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-medium transition-colors disabled:opacity-50"
          >
            Intéressé
          </button>
        </div>
      </div>
    </div>
  );
}
