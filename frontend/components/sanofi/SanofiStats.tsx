'use client';

import { SanofiStats as Stats } from '@/lib/sanofiApi';

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

export default function SanofiStats({ stats, loading }: Props) {
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
      <StatCard icon="🔬" label="Essais cliniques" value={stats.total_clinical_trials} />
      <StatCard icon="📄" label="Publications R&D" value={stats.total_pubmed} />
      <StatCard icon="📰" label="Actualités" value={stats.total_news} />
    </div>
  );
}