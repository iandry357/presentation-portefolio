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
    // name: c.label.length > 25 ? c.label.slice(0, 25) + '…' : c.label,
    name: c.label,
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

      {data.bayesian_forecast && (
        <div className="bg-white border rounded-lg p-4">
          <h4 className="text-sm font-semibold text-gray-700 mb-1">
            Prédiction Bayésienne — Volume d'essais fin 2026
          </h4>
          <p className="text-xs text-gray-500 mb-4">
            Taux mensuel projeté 2026 : {data.bayesian_forecast.avg_monthly_rate} essais/mois —
            estimé via un GLM Poisson bayésien sur {data.bayesian_forecast.n_years_used} années d'historique.
          </p>

          {/* Ligne 1 — Observé + Restant = Total */}
          <div className="grid grid-cols-3 gap-3 mb-3">
            <div className="bg-gray-50 rounded p-3 text-center">
              <p className="text-xs text-gray-600 font-medium mb-1">Déjà enregistrés</p>
              <p className="text-2xl font-bold text-gray-700">
                {data.bayesian_forecast.already_observed}
              </p>
              <p className="text-xs text-gray-400">essais en 2026</p>
            </div>
            <div className="bg-blue-50 rounded p-3 text-center">
              <p className="text-xs text-blue-600 font-medium mb-1">Attendus ({data.bayesian_forecast.months_remaining} mois)</p>
              <p className="text-2xl font-bold text-blue-900">
                +{data.bayesian_forecast.predicted_remaining}
              </p>
              <p className="text-xs text-blue-400">essais prédits</p>
            </div>
            <div className="bg-indigo-50 rounded p-3 text-center">
              <p className="text-xs text-indigo-600 font-medium mb-1">Total prédit fin 2026</p>
              <p className="text-2xl font-bold text-indigo-900">
                {data.bayesian_forecast.total_predicted}
              </p>
              <p className="text-xs text-indigo-400">essais estimés</p>
            </div>
          </div>

          {/* Ligne 2 — Intervalle de crédibilité */}
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-gray-50 rounded p-3 text-center">
              <p className="text-xs text-gray-600 font-medium mb-1">Borne basse 95%</p>
              <p className="text-xl font-bold text-gray-700">
                {data.bayesian_forecast.total_ci_lower}
              </p>
              <p className="text-xs text-gray-400">intervalle de crédibilité</p>
            </div>
            <div className="bg-gray-50 rounded p-3 text-center">
              <p className="text-xs text-gray-600 font-medium mb-1">Borne haute 95%</p>
              <p className="text-xl font-bold text-gray-700">
                {data.bayesian_forecast.total_ci_upper}
              </p>
              <p className="text-xs text-gray-400">intervalle de crédibilité</p>
            </div>
          </div>

          <p className="text-xs text-gray-400 mt-3">
            Taux mensuel historique moyen : {data.bayesian_forecast.avg_monthly_rate} essais/mois —
            calculé sur {data.bayesian_forecast.n_years_used} années complètes.
          </p>
        </div>
      )}
    {/* Durée par cluster */}
      <div className="bg-white border rounded-lg p-4">
        <h4 className="text-sm font-semibold text-gray-700 mb-4">Durée moyenne des essais par thérapeutique (mois)</h4>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={durationData} layout="vertical" margin={{ left: 8, right: 24 }}>
            <XAxis type="number" tick={{ fontSize: 11 }} unit=" mois" />
            <YAxis type="category" dataKey="name" width={220} tick={{ fontSize: 11 }} />
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