'use client';

import { SavenciaStats as Stats } from '@/lib/savenciaApi';

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

export default function SavenciaStats({ stats, loading }: Props) {
  if (loading) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
        {[1, 2, 3].map(i => (
          <div key={i} className="border rounded-lg p-4 bg-white animate-pulse h-20" />
        ))}
      </div>
    );
  }

  if (!stats) return null;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
      <StatCard icon="📰" label="Total articles" value={stats.total_news} />
      <StatCard icon="🏭" label="Savencia" value={stats.total_savencia_news} />
      <StatCard icon="🌾" label="Agroalimentaire IA" value={stats.total_agroalimentaire_ia} />
    </div>
  );
}