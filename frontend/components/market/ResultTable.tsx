"use client"

import { Fragment, useState, useMemo } from "react"
import { MarketQueryResult, toggleExcludedCompany, batchExcludeCompanies } from "@/lib/marketConfig"

interface Props {
  result: MarketQueryResult
  excludedCompanies: string[]
  onExclusionChange: (updated: string[]) => void
}

const COL_LABELS: Record<string, string> = {
  entreprise_nom:       "Entreprise",
  nb_titres_distincts:  "Postes distincts",
  nb_sources:           "Sources",
  premiere_offre:       "Première offre",
  derniere_offre:       "Dernière offre",
  duree_jours:          "Durée (j)",
  score_signal:         "Score Signal",
  titres:               "Intitulés",
}

type SortDir = "asc" | "desc" | null

export default function ResultTable({ result, excludedCompanies, onExclusionChange }: Props) {
  const [togglingRow, setTogglingRow]   = useState<string | null>(null)
  const [expandedRow, setExpandedRow]   = useState<string | null>(null)
  const [selected, setSelected]         = useState<Set<string>>(new Set())
  const [batchLoading, setBatchLoading] = useState(false)
  const [filterText, setFilterText]     = useState("")
  const [sortCol, setSortCol]           = useState<string | null>(null)
  const [sortDir, setSortDir]           = useState<SortDir>(null)

  const isQ11 = result.query_id === "Q11"
  const { colonnes, lignes } = result

  // ── Filtre + tri ─────────────────────────────────────────────────────────

  const displayedRows = useMemo(() => {
    let rows = [...lignes]

    // Filtre texte sur entreprise_nom (Q11 uniquement)
    if (isQ11 && filterText.trim()) {
      const q = filterText.trim().toLowerCase()
      rows = rows.filter(r =>
        String(r.entreprise_nom ?? "").toLowerCase().includes(q)
      )
    }

    // Tri colonne
    if (sortCol && sortDir) {
      rows.sort((a, b) => {
        const va = a[sortCol] ?? ""
        const vb = b[sortCol] ?? ""
        const cmp = String(va).localeCompare(String(vb), undefined, { numeric: true })
        return sortDir === "asc" ? cmp : -cmp
      })
    }

    return rows
  }, [lignes, filterText, sortCol, sortDir, isQ11])

  // ── Gestion tri ──────────────────────────────────────────────────────────

  function handleSort(col: string) {
    if (sortCol !== col) {
      setSortCol(col)
      setSortDir("asc")
    } else if (sortDir === "asc") {
      setSortDir("desc")
    } else if (sortDir === "desc") {
      setSortCol(null)
      setSortDir(null)
    }
  }

  function SortIcon({ col }: { col: string }) {
    if (sortCol !== col) return <span className="ml-1 text-gray-300">⇅</span>
    return <span className="ml-1 text-blue-500">{sortDir === "asc" ? "▲" : "▼"}</span>
  }

  // ── Sélection ────────────────────────────────────────────────────────────

  function toggleSelect(nom: string) {
    setSelected(prev => {
      const next = new Set(prev)
      next.has(nom) ? next.delete(nom) : next.add(nom)
      return next
    })
  }

  function clearSelection() { setSelected(new Set()) }

  // ── Toggle individuel ────────────────────────────────────────────────────

  async function handleToggle(nom: string) {
    const isExcluded = excludedCompanies.includes(nom)
    setTogglingRow(nom)
    try {
      const updated = await toggleExcludedCompany(nom, isExcluded)
      onExclusionChange(updated.entreprises)
      setSelected(prev => { const n = new Set(prev); n.delete(nom); return n })
    } finally {
      setTogglingRow(null)
    }
  }

  // ── Batch exclusion ──────────────────────────────────────────────────────

  async function handleBatchExclude() {
    if (!selected.size) return
    setBatchLoading(true)
    try {
      const updated = await batchExcludeCompanies(Array.from(selected))
      onExclusionChange(updated.entreprises)
      clearSelection()
    } finally {
      setBatchLoading(false)
    }
  }

  // ── Rendu ────────────────────────────────────────────────────────────────

  if (!lignes.length) {
    return <p className="text-sm text-gray-400 py-8 text-center">Aucune donnée pour cette période.</p>
  }

  return (
    <div className="space-y-2">

      {/* Filtre entreprise (Q11 uniquement) */}
      {isQ11 && (
        <div className="flex items-center gap-3">
          <input
            type="text"
            value={filterText}
            onChange={e => setFilterText(e.target.value)}
            placeholder="Filtrer par entreprise…"
            className="text-sm border border-gray-200 rounded-lg px-3 py-1.5 w-64 focus:outline-none focus:ring-1 focus:ring-blue-300"
          />
          {filterText && (
            <span className="text-xs text-gray-400">
              {displayedRows.length} résultat{displayedRows.length !== 1 ? "s" : ""}
            </span>
          )}
        </div>
      )}

      {/* Bandeau sélection multiple */}
      {isQ11 && selected.size > 0 && (
        <div className="flex items-center justify-between bg-amber-50 border border-amber-200 rounded-lg px-4 py-2">
          <span className="text-sm text-amber-800">
            {selected.size} entreprise{selected.size > 1 ? "s" : ""} sélectionnée{selected.size > 1 ? "s" : ""}
          </span>
          <div className="flex gap-2">
            <button
              onClick={clearSelection}
              className="text-xs px-3 py-1 rounded border border-amber-300 text-amber-700 hover:bg-amber-100 transition-colors"
            >
              Tout désélectionner
            </button>
            <button
              onClick={handleBatchExclude}
              disabled={batchLoading}
              className="text-xs px-3 py-1 rounded bg-red-500 text-white hover:bg-red-600 transition-colors disabled:opacity-50"
            >
              {batchLoading ? "Exclusion…" : `Exclure (${selected.size})`}
            </button>
          </div>
        </div>
      )}

      {/* Tableau */}
      {/* <div className="overflow-x-auto rounded-lg border border-gray-200"> */}
      <div className="overflow-x-auto rounded-lg border border-gray-200 max-w-full">
        <table className="min-w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              {isQ11 && <th className="px-3 py-3 w-8" />}
              {colonnes.map(col => (
                <th
                  key={col}
                  onClick={() => handleSort(col)}
                  // className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide whitespace-nowrap cursor-pointer select-none hover:text-gray-700 hover:bg-gray-100 transition-colors"
                  className={`px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide whitespace-nowrap cursor-pointer select-none hover:text-gray-700 hover:bg-gray-100 transition-colors ${col === "entreprise_nom" ? "max-w-[180px]" : ""}`}
                >
                  {COL_LABELS[col] ?? col}
                  <SortIcon col={col} />
                </th>
              ))}
              {isQ11 && (
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">
                  Intitulés
                </th>
              )}
              {isQ11 && <th className="px-4 py-3 w-10" />}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 bg-white">
            {displayedRows.map((row, i) => {
              const nom        = row.entreprise_nom as string | undefined
              const isExcluded = nom ? excludedCompanies.includes(nom) : false
              const isToggling = nom === togglingRow
              const isExpanded = nom === expandedRow
              const isSelected = nom ? selected.has(nom) : false

              return (
                <Fragment key={i}>
                  <tr
                    className={[
                      "transition-colors",
                      isSelected ? "bg-amber-50" :
                      isExcluded ? "opacity-40 bg-gray-50" :
                      "hover:bg-gray-50",
                    ].join(" ")}
                  >
                    {isQ11 && (
                      <td className="px-3 py-3">
                        {nom && !isExcluded && (
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={() => toggleSelect(nom)}
                            className="rounded border-gray-300 text-amber-500 focus:ring-amber-400"
                          />
                        )}
                      </td>
                    )}

                    {colonnes.map(col => (
                      // <td key={col} className="px-4 py-3 text-gray-800 whitespace-nowrap">
                      <td key={col} className={`px-4 py-3 text-gray-800 whitespace-nowrap ${col === "entreprise_nom" ? "max-w-[180px] truncate" : ""}`}>
                        {String(row[col] ?? "—")}
                      </td>
                    ))}

                    {isQ11 && (
                      <td className="px-4 py-3 max-w-xs">
                        <button
                          onClick={() => setExpandedRow(isExpanded ? null : (nom ?? null))}
                          className="text-xs text-blue-500 hover:underline"
                        >
                          {isExpanded ? "Masquer" : "Voir les intitulés"}
                        </button>
                      </td>
                    )}

                    {isQ11 && nom && (
                      <td className="px-4 py-3 text-right">
                        <button
                          onClick={() => handleToggle(nom)}
                          disabled={isToggling}
                          title={isExcluded ? "Réinclure cette entreprise" : "Exclure cette entreprise"}
                          className={[
                            "text-xs px-2 py-1 rounded border transition-colors disabled:opacity-50",
                            isExcluded
                              ? "border-green-300 text-green-700 hover:bg-green-50"
                              : "border-red-200 text-red-500 hover:bg-red-50",
                          ].join(" ")}
                        >
                          {isToggling ? "…" : isExcluded ? "Inclure" : "Exclure"}
                        </button>
                      </td>
                    )}
                  </tr>

                  {isQ11 && isExpanded && nom && (
                    <tr className="bg-blue-50">
                      <td colSpan={colonnes.length + 3} className="px-6 py-3">
                        <p className="text-xs text-gray-600 leading-relaxed">
                          {String(row.titres ?? "—").split(" | ").map((t, j) => (
                            <span key={j} className="inline-block bg-white border border-blue-100 rounded px-2 py-0.5 mr-1 mb-1 text-gray-700">
                              {t}
                            </span>
                          ))}
                        </p>
                      </td>
                    </tr>
                  )}
                </Fragment>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}