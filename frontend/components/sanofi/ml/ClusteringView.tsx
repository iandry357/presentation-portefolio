'use client';

import { ClusteringResponse } from '@/lib/sanofiApi';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';

const COLORS = [
  '#3b82f6','#8b5cf6','#ec4899','#f59e0b','#10b981',
  '#06b6d4','#f97316','#84cc16','#6366f1','#14b8a6','#e11d48',
];

// Calcul répartition phases
const PHASE_COLORS: Record<string, string> = {
  PHASE1: '#93c5fd',
  PHASE2: '#6ee7b7',
  PHASE3: '#fcd34d',
  PHASE4: '#f9a8d4',
  OTHER: '#d1d5db',
};


interface Props {
  data: ClusteringResponse;
}

export default function ClusteringView({ data }: Props) {
//   const chartData = data.clusters.map((c, i) => ({
//     name: c.label.length > 25 ? c.label.slice(0, 25) + '…' : c.label,
//     trials: c.trial_count,
//     duration: Math.round(c.avg_duration_months),
//     color: COLORS[i % COLORS.length],
//   }));
  // const chartData = data.clusters.map((c, i) => ({
  //   // name: c.label.length > 20 ? c.label.slice(0, 20) + '…' : c.label,
  //   name: c.label,
  //   trials: c.count,
  //   color: COLORS[i % COLORS.length],
  //   }));

    const chartData = [...data.clusters]
    .sort((a, b) => b.count - a.count)
    .map((c, i) => ({
        name: c.label,
        trials: c.count,
        color: COLORS[i % COLORS.length],
    }));

    const phaseByCluster = data.clusters.map(c => {
    const trials = data.trials.filter(t => t.cluster_id === c.cluster_id);
    const phases: Record<string, number> = {};
        trials.forEach(t => {
            const p = t.phase?.startsWith('PHASE') ? t.phase.split(',')[0].trim() : 'OTHER';
            phases[p] = (phases[p] || 0) + 1;
        });
        return { label: c.label, total: trials.length, phases };
        });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white border rounded-lg p-4">
        <h3 className="font-semibold text-gray-900 mb-1">Clustering des essais cliniques</h3>
        <p className="text-sm text-gray-500">
          {data.total_trials} essais → {data.n_clusters} clusters — KMeans mixte TF-IDF + embeddings VoyageAI
        </p>
      </div>

      {/* Bar chart trials par cluster */}
      <div className="bg-white border rounded-lg p-4">
        <h4 className="text-sm font-semibold text-gray-700 mb-4">Essais par cluster</h4>
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={chartData} layout="vertical" margin={{ left: 8, right: 24 }}>
            <XAxis type="number" tick={{ fontSize: 11 }} />
            <YAxis type="category" dataKey="name" width={220} tick={{ fontSize: 11 }} />
            <Tooltip
            //   formatter={(val: number) => [`${val} essais`, 'Essais']}
              formatter={(val) => [`${val} essais`, 'Essais']}
              contentStyle={{ fontSize: 12 }}
            />
            <Bar dataKey="trials" radius={[0, 4, 4, 0]}>
              {chartData.map((entry, i) => (
                <Cell key={i} fill={entry.color} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="bg-white border rounded-lg overflow-hidden">
        <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b">
            <tr>
                <th className="text-left px-4 py-2 text-gray-600 font-medium">Cluster</th>
                <th className="text-right px-4 py-2 text-gray-600 font-medium">P1</th>
                <th className="text-right px-4 py-2 text-gray-600 font-medium">P2</th>
                <th className="text-right px-4 py-2 text-gray-600 font-medium">P3</th>
                <th className="text-right px-4 py-2 text-gray-600 font-medium">P4</th>
                <th className="text-right px-4 py-2 text-gray-600 font-medium">Autre</th>
            </tr>
            </thead>
            <tbody>
            {phaseByCluster.map((c, i) => (
                <tr key={i} className="border-b last:border-0 hover:bg-gray-50">
                <td className="px-4 py-2 flex items-center gap-2">
                    <span className="w-3 h-3 rounded-full shrink-0" style={{ backgroundColor: COLORS[i % COLORS.length] }} />
                    {c.label}
                </td>
                <td className="px-4 py-2 text-right text-blue-400">{c.phases['PHASE1'] || '-'}</td>
                <td className="px-4 py-2 text-right text-green-400">{c.phases['PHASE2'] || '-'}</td>
                <td className="px-4 py-2 text-right text-yellow-400">{c.phases['PHASE3'] || '-'}</td>
                <td className="px-4 py-2 text-right text-pink-400">{c.phases['PHASE4'] || '-'}</td>
                <td className="px-4 py-2 text-right text-gray-400">{c.phases['OTHER'] || '-'}</td>
                </tr>
            ))}
            </tbody>
        </table>
      </div>

      {/* Durée moyenne par cluster
      <div className="bg-white border rounded-lg p-4">
        <h4 className="text-sm font-semibold text-gray-700 mb-4">Durée moyenne (mois) par cluster</h4>
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={chartData} layout="vertical" margin={{ left: 8, right: 24 }}>
            <XAxis type="number" tick={{ fontSize: 11 }} unit=" mois" />
            <YAxis type="category" dataKey="name" width={180} tick={{ fontSize: 11 }} />
            <Tooltip
            //   formatter={(val: number) => [`${val} mois`, 'Durée moyenne']}
              formatter={(val) => [`${val} mois`, 'Durée moyenne']}
              contentStyle={{ fontSize: 12 }}
            />
            <Bar dataKey="duration" radius={[0, 4, 4, 0]}>
              {chartData.map((entry, i) => (
                <Cell key={i} fill={entry.color} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div> */}

      {/* Table clusters */}
      {/* <div className="bg-white border rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="text-left px-4 py-2 text-gray-600 font-medium">Cluster</th>
              <th className="text-right px-4 py-2 text-gray-600 font-medium">Essais</th>
            </tr>
          </thead>
          <tbody>
            {data.clusters.map((c, i) => (
              <tr key={c.cluster_id} className="border-b last:border-0 hover:bg-gray-50">
                <td className="px-4 py-2 flex items-center gap-2">
                  <span
                    className="w-3 h-3 rounded-full shrink-0"
                    style={{ backgroundColor: COLORS[i % COLORS.length] }}
                  />
                  {c.label}
                </td>
                <td className="px-4 py-2 text-right text-gray-700">{c.count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div> */}
    </div>
  );
}