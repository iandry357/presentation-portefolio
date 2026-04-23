"use client"

import {
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts"
import { MarketQueryResult, RenduType } from "@/lib/marketConfig"

const COLORS = ["#3b82f6","#10b981","#f59e0b","#ef4444","#8b5cf6","#ec4899","#06b6d4","#84cc16","#f97316"]

// interface Props {
//   result: MarketQueryResult
// }
interface Props {
  result: MarketQueryResult
  rendu: RenduType
}

export default function ResultChart({ result, rendu }: Props) {
//   const { rendu, lignes } = result as { rendu: RenduType; lignes: Record<string, unknown>[] }
  const { lignes } = result
//   const rendu = (result as unknown as { rendu: RenduType }).rendu

  if (!lignes.length) {
    return <p className="text-sm text-gray-400 py-8 text-center">Aucune donnée pour cette période.</p>
  }

  if (rendu === "courbe") {
    return (
      <ResponsiveContainer width="100%" height={320}>
        <LineChart data={lignes} margin={{ top: 8, right: 24, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis dataKey="date_publication" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} />
          <Tooltip />
          <Line type="monotone" dataKey="nb_offres" stroke="#3b82f6" dot={false} strokeWidth={2} />
        </LineChart>
      </ResponsiveContainer>
    )
  }

  if (rendu === "courbe_multi") {
    const sources = [...new Set(lignes.map(r => r.source as string))]
    const byWeek = Object.values(
      lignes.reduce<Record<string, Record<string, unknown>>>((acc, row) => {
        const w = row.semaine as string
        if (!acc[w]) acc[w] = { semaine: w }
        acc[w][row.source as string] = row.nb_offres
        return acc
      }, {})
    )
    return (
      <ResponsiveContainer width="100%" height={320}>
        <LineChart data={byWeek} margin={{ top: 8, right: 24, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis dataKey="semaine" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} />
          <Tooltip />
          <Legend />
          {sources.map((s, i) => (
            <Line key={s} type="monotone" dataKey={s} stroke={COLORS[i % COLORS.length]} dot={false} strokeWidth={1.5} />
          ))}
        </LineChart>
      </ResponsiveContainer>
    )
  }

  if (rendu === "camembert") {
    const key = result.colonnes[0]
    const data = lignes.map(r => ({ name: String(r[key]), value: Number(r.nb_offres) }))
    return (
      <ResponsiveContainer width="100%" height={320}>
        <PieChart>
          <Pie data={data} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={120} label={({ name, percent }) => `${name} ${((percent ?? 0) * 100).toFixed(0)}%`}>
            {data.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
          </Pie>
          <Tooltip />
        </PieChart>
      </ResponsiveContainer>
    )
  }

  if (rendu === "barres_horizontales") {
    const key = result.colonnes[0]
    return (
      <ResponsiveContainer width="100%" height={Math.max(320, lignes.length * 28)}>
        <BarChart data={lignes} layout="vertical" margin={{ top: 8, right: 24, left: 160, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" horizontal={false} />
          <XAxis type="number" tick={{ fontSize: 11 }} />
          <YAxis type="category" dataKey={key} tick={{ fontSize: 11 }} width={155} />
          <Tooltip />
          <Bar dataKey="nb_offres" fill="#3b82f6" radius={[0, 4, 4, 0]} />
        </BarChart>
      </ResponsiveContainer>
    )
  }

  if (rendu === "indicateur" || rendu === "indicateur_comparatif") {
    return (
      <div className="flex gap-6 flex-wrap py-6">
        {lignes.map((row, i) => {
          const label = Object.entries(row).find(([k]) => k !== "nb_offres" && k !== "pourcentage")
          const val = row.nb_offres as number
          const pct = row.pourcentage as number | undefined
          return (
            <div key={i} className="flex flex-col items-center bg-gray-50 rounded-xl px-8 py-6 min-w-[140px]">
              <span className="text-3xl font-bold text-blue-600">{val}</span>
              {pct !== undefined && (
                <span className="text-sm text-gray-500">{pct}%</span>
              )}
              <span className="text-xs text-gray-500 mt-1 text-center">
                {label ? String(label[1]) : ""}
              </span>
            </div>
          )
        })}
      </div>
    )
  }

  return null
}