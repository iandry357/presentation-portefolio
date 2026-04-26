"use client"

import { PERIODES, SOURCES, Periode, Source, QueryMeta } from "@/lib/marketConfig"

interface Props {
  periode: Periode
  source: Source
  query: QueryMeta | null
  onPeriodeChange: (v: Periode) => void
  onSourceChange: (v: Source) => void
  onSubmit: () => void
  loading: boolean
}

export default function FilterBar({
  periode,
  source,
  query,
  onPeriodeChange,
  onSourceChange,
  onSubmit,
  loading,
}: Props) {
  const sourceDisabled = !!query?.sourceRequise

  return (
    <div className="flex flex-wrap items-end gap-4 bg-white border border-gray-200 rounded-lg px-5 py-4">
      {/* Période */}
      <div className="flex flex-col gap-1">
        <label className="text-xs text-gray-500 font-medium">Période</label>
        <select
          value={periode}
          onChange={e => onPeriodeChange(e.target.value as Periode)}
          className="text-sm border border-gray-200 rounded-md px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-blue-400"
        >
          {PERIODES.map(p => (
            <option key={p.value} value={p.value}>{p.label}</option>
          ))}
        </select>
      </div>

      {/* Source */}
      <div className="flex flex-col gap-1">
        <label className="text-xs text-gray-500 font-medium">
          Source
          {sourceDisabled && (
            <span className="ml-2 text-amber-600 font-normal">(fixé : France Travail API)</span>
          )}
        </label>
        <select
          value={sourceDisabled ? "france_travail_api" : source}
          onChange={e => onSourceChange(e.target.value as Source)}
          disabled={sourceDisabled}
          className="text-sm border border-gray-200 rounded-md px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-blue-400 disabled:bg-gray-100 disabled:text-gray-400"
        >
          {SOURCES.map(s => (
            <option key={s.value} value={s.value}>{s.label}</option>
          ))}
        </select>
      </div>

      {/* Bouton */}
      <button
        onClick={onSubmit}
        disabled={loading || !query}
        className="ml-auto px-5 py-2 rounded-md bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        {loading ? "Chargement…" : "Analyser"}
      </button>
    </div>
  )
}