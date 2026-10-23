'use client';

import { useEffect, useState } from 'react';
import { ImmobilierStatsResponse, getImmobilierStats } from '@/lib/immobilierApi';

function pct(part: number, total: number): string {
  return total ? `${(Math.round((1000 * part) / total) / 10).toLocaleString('fr-FR')} %` : '—';
}

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

export default function ImmobilierStats() {
  const [stats, setStats] = useState<ImmobilierStatsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getImmobilierStats()
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

  // Dernière mise à jour des deux sources (dates ISO : l'ordre alphabétique est chronologique)
  const dateMaj = [stats.date_maj_dpe, stats.date_maj_dvf].filter(Boolean).sort().pop() ?? null;

  return (
    <div>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Tuile
          label="DPE établis"
          valeur={stats.nb_dpe}
          detail="logements existants, Paris, depuis juillet 2021"
          info="Diagnostics établis à la vente, à la location ou pour un logement neuf : ce n'est pas l'ensemble du parc"
        />
        <Tuile
          label="Passoires thermiques (F et G)"
          valeur={stats.nb_passoires}
          detail={`${pct(stats.nb_passoires, stats.nb_dpe)} des DPE`}
          info="DPE d'étiquette F ou G"
        />
        <Tuile
          label="DPE refaits"
          valeur={stats.nb_remplacants}
          detail={`${pct(stats.nb_remplacants, stats.nb_dpe)} des DPE`}
          info="DPE qui en remplacent un autre"
        />
        <Tuile
          label="Ventes de logement"
          valeur={stats.nb_ventes}
          detail="DVF, un seul logement par vente"
        />
      </div>
      {dateMaj && (
        <p className="text-xs text-gray-500 mt-2">Données mises à jour le {formatDateLongue(dateMaj)}.</p>
      )}
    </div>
  );
}
