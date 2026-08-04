'use client';

import { BdfStats as Stats } from '@/lib/banqueApi';

interface Props {
  stats: Stats | null;
  loading: boolean;
}

function StatCard({ label, value, icon }: { label: string; value: number | string; icon: string }) {
  return (
    <div className="border rounded-lg p-4 bg-white flex items-center gap-4">
      <span className="text-2xl">{icon}</span>
      <div>
        <p className="text-2xl font-bold text-gray-900">{value}</p>
        <p className="text-sm text-gray-500">{label}</p>
      </div>
    </div>
  );
}

export default function BanqueStats({ stats, loading }: Props) {
  if (loading) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
        {[1, 2].map(i => (
          <div key={i} className="border rounded-lg p-4 bg-white animate-pulse h-20" />
        ))}
      </div>
    );
  }

  if (!stats) return null;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
      <StatCard icon="📰" label="Articles de veille" value={stats.total_news} />
      <StatCard
        icon="🕒"
        label="Dernière mise à jour"
        value={stats.last_updated ? new Date(stats.last_updated).toLocaleDateString('fr-FR') : '—'}
      />
    </div>
  );
}