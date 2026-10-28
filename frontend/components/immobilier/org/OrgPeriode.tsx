'use client';

import { useEffect, useState } from 'react';
import { OrgParametres, getOrgParametres } from '@/lib/immobilierOrgApi';
import { formatDate } from '@/lib/immobilier';

// Période paramétrée commune à toutes les parties (lue dans org_parametres, jamais en dur)
export default function OrgPeriode() {
  const [parametres, setParametres] = useState<OrgParametres | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getOrgParametres()
      .then(setParametres)
      .catch(e => setError(e instanceof Error ? e.message : 'Erreur de chargement'));
  }, []);

  if (error) {
    return <div className="text-sm text-red-600 bg-red-50 px-4 py-3 rounded-lg">{error}</div>;
  }

  if (!parametres) {
    return <div className="h-12 border rounded-lg bg-white animate-pulse" />;
  }

  return (
    <p className="text-sm text-gray-600 bg-gray-50 border rounded-lg px-4 py-3">
      <span className="font-medium text-gray-900">Période commune</span> : depuis le {formatDate(parametres.date_debut)}{' '}
      {parametres.date_fin ? `jusqu’au ${formatDate(parametres.date_fin)}` : 'jusqu’aux dernières données'}.
      Ventes couvertes : du {formatDate(parametres.premiere_vente)} au {formatDate(parametres.derniere_vente)}.
      Les immeubles (BDNB) sont un état du parc au millésime, sans période.
    </p>
  );
}
