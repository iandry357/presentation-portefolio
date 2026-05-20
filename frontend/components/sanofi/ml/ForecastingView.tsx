'use client';

import { ForecastingResponse } from '@/lib/sanofiApi';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, BarChart, Bar, Cell } from 'recharts';

const COLORS = [
  '#3b82f6','#8b5cf6','#ec4899','#f59e0b','#10b981',
  '#06b6d4','#f97316','#84cc16','#6366f1','#14b8a6','#e11d48',
];

interface Props {
  data: ForecastingResponse;
}

export default function ForecastingView({ data }: Props) {
  const volumeData = data.volume_by_year.filter(d => d.year >= 2010);

  const durationData = data.duration_by_cluster.map((c, i) => ({
    name: c.label.length > 25 ? c.label.slice(0, 25) + '…' : c.label,
    duration: Math.round(c.avg_duration_months),
    color: COLORS[i % COLORS.length],
  })).sort((a, b) => b.duration - a.duration);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white border rounded-lg p-4">
        <h3 className="font-semibold text-gray-900 mb-1">Forecasting du pipeline clinique</h3>
        <p className="text-sm text-gray-500">
          {data.total_trials} essais analysés — volume annuel et durée par thérapeutique
        </p>
      </div>

      {/* Volume par année */}
      <div className="bg-white border rounded-lg p-4">
        <h4 className="text-sm font-semibold text-gray-700 mb-4">Volume d'essais par année</h4>
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={volumeData} margin={{ left: 0, right: 16 }}>
            <XAxis dataKey="year" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip
            //   formatter={(val: number) => [`${val} essais`, 'Volume']}
              formatter={(val) => [`${val} essais`, 'Essais']}
              contentStyle={{ fontSize: 12 }}
            />
            <Line
              type="monotone"
              dataKey="count"
              stroke="#3b82f6"
              strokeWidth={2}
              dot={{ r: 3 }}
              activeDot={{ r: 5 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Durée par cluster */}
      <div className="bg-white border rounded-lg p-4">
        <h4 className="text-sm font-semibold text-gray-700 mb-4">Durée moyenne des essais par thérapeutique (mois)</h4>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={durationData} layout="vertical" margin={{ left: 8, right: 24 }}>
            <XAxis type="number" tick={{ fontSize: 11 }} unit=" mois" />
            <YAxis type="category" dataKey="name" width={180} tick={{ fontSize: 11 }} />
            <Tooltip
            //   formatter={(val: number) => [`${val} mois`, 'Durée moyenne']}
              formatter={(val) => [`${val} mois`, 'Durée moyenne']}
              contentStyle={{ fontSize: 12 }}
            />
            <Bar dataKey="duration" radius={[0, 4, 4, 0]}>
              {durationData.map((entry, i) => (
                <Cell key={i} fill={entry.color} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Insights clés */}
      <div className="bg-white border rounded-lg p-4">
        <h4 className="text-sm font-semibold text-gray-700 mb-3">Insights clés</h4>
        <div className="grid grid-cols-2 gap-3">
          <div className="bg-blue-50 rounded p-3">
            <p className="text-xs text-blue-600 font-medium">Thérapeutique la plus longue</p>
            <p className="text-sm font-semibold text-blue-900 mt-1">
              {durationData[0]?.name} — {durationData[0]?.duration} mois
            </p>
          </div>
          <div className="bg-green-50 rounded p-3">
            <p className="text-xs text-green-600 font-medium">Thérapeutique la plus courte</p>
            <p className="text-sm font-semibold text-green-900 mt-1">
              {durationData[durationData.length - 1]?.name} — {durationData[durationData.length - 1]?.duration} mois
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}