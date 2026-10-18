'use client';

import { useEffect, useState } from 'react';
import { ExternalLink } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { getOffresEntreprise } from '@/lib/api';
import {
  LIBELLES_CATEGORIE,
  formatDateCourte,
  libelle,
  libelleSource,
  lienOffre,
} from '@/lib/topOffres';
import { OffreEntreprise } from '@/types';

const LIBELLES_LISTE: Record<string, string> = {
  a_lire: 'À lire',
  zone_grise: 'Zone grise',
  masque: 'Masquée',
};

interface EntrepriseOffresProps {
  entreprise: string;   // nom normalisé
  jours: number;
}

// Offres scorées d'une entreprise, chargées au dépliage de sa ligne
export default function EntrepriseOffres({ entreprise, jours }: EntrepriseOffresProps) {
  const [offres, setOffres] = useState<OffreEntreprise[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let annule = false;
    getOffresEntreprise(entreprise, jours)
      .then(data => {
        if (!annule) setOffres(data.offres);
      })
      .catch(e => {
        if (!annule) setError(e instanceof Error ? e.message : 'Erreur de chargement');
      });
    return () => {
      annule = true;
    };
  }, [entreprise, jours]);

  if (error) return <p className="text-sm text-red-600">{error}</p>;
  if (!offres) return <div className="h-16 rounded bg-white animate-pulse" aria-busy="true" />;
  if (offres.length === 0) {
    return <p className="text-sm text-gray-500">Aucune offre scorée sur la période.</p>;
  }

  return (
    <ul className="divide-y">
      {offres.map(offre => {
        const lien = lienOffre(offre);
        const details = [
          offre.localisation_libelle,
          offre.type_contrat_libelle,
          offre.salaire_libelle,
          libelleSource(offre.source),
        ]
          .filter(Boolean)
          .join(' · ');
        return (
          <li key={offre.id_unique} className="py-2 flex items-start gap-3">
            <span className="w-8 shrink-0 text-right text-base font-semibold text-gray-900 tabular-nums">
              {offre.score ?? '—'}
            </span>

            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-gray-900 break-words">{offre.titre}</p>
              {details && <p className="text-xs text-gray-500">{details}</p>}
              {offre.raison && (
                <p className="text-xs text-gray-500 italic line-clamp-1" title={offre.raison}>
                  « {offre.raison} »
                </p>
              )}
            </div>

            <div className="shrink-0 text-right space-y-1">
              <div className="flex flex-wrap justify-end gap-1">
                <Badge variant="outline" className="text-xs">
                  {libelle(LIBELLES_CATEGORIE, offre.categorie)}
                </Badge>
                <Badge variant={offre.liste === 'a_lire' ? 'default' : 'secondary'} className="text-xs">
                  {libelle(LIBELLES_LISTE, offre.liste)}
                </Badge>
              </div>
              <p className="text-xs text-gray-500">
                {formatDateCourte(offre.date_publication ?? offre.date_collecte)}
              </p>
              {lien ? (
                <a
                  href={lien}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-xs text-blue-600 hover:underline"
                >
                  <ExternalLink className="w-3.5 h-3.5" />
                  Voir l&apos;offre
                </a>
              ) : (
                <span className="text-xs text-gray-400">Lien indisponible</span>
              )}
            </div>
          </li>
        );
      })}
    </ul>
  );
}
