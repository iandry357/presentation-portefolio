'use client';

import { useEffect, useState } from 'react';
import { BdnbStatsResponse, getBdnbStats } from '@/lib/immobilierBdnbApi';

function formatDateLongue(iso: string | null): string {
  if (!iso) return '';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' });
}

function Tuile({
  label,
  valeur,
  detail,
  info,
}: {
  label: string;
  valeur: number;
  detail: string;
  info?: string;
}) {
  return (
    <div className="border rounded-lg bg-white p-4" title={info}>
      <p className="text-sm text-gray-500">{label}</p>
      <p className="text-3xl font-semibold text-gray-900 mt-1">{valeur.toLocaleString('fr-FR')}</p>
      <p className="text-xs text-gray-500 mt-1">{detail}</p>
    </div>
  );
}

export default function BdnbStats() {
  const [stats, setStats] = useState<BdnbStatsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getBdnbStats()
      .then(setStats)
      .catch(e => setError(e instanceof Error ? e.message : 'Erreur de chargement'));
  }, []);

  if (error) {
    return <div className="text-sm text-red-600 bg-red-50 px-4 py-3 rounded-lg">{error}</div>;
  }

  if (!stats) {
    return (
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[1, 2, 3, 4].map(i => (
          <div key={i} className="h-24 border rounded-lg bg-white animate-pulse" />
        ))}
      </div>
    );
  }

  const dateMaj = formatDateLongue(stats.date_maj);

  return (
    <div>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Tuile
          label="Bâtiments"
          valeur={stats.nb_batiments}
          detail="groupes de bâtiments, Paris"
          info="Groupes de bâtiments de la BDNB pour le département 75"
        />
        <Tuile
          label="DPE retenus"
          valeur={stats.nb_dpe}
          detail="arrêté 2021, logements"
          info="DPE de l'arrêté 2021, de type logement, méthode 3CL, surface habitable renseignée"
        />
        <Tuile label="Adresses" valeur={stats.nb_adresses} detail="adresses rattachées à un bâtiment" />
        <Tuile
          label="Transactions"
          valeur={stats.nb_transactions}
          detail="DVF, une par bâtiment"
          info="Transaction représentative de chaque bâtiment (DVF open)"
        />
      </div>
      <p className="text-xs text-gray-500 mt-2">
        {stats.millesime ? `BDNB (CSTB), millésime ${stats.millesime}.` : 'BDNB (CSTB).'}
        {dateMaj && ` Agrégats calculés le ${dateMaj}.`}
      </p>
    </div>
  );
}
