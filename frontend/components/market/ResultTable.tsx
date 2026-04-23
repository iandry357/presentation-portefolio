"use client"

import { useState } from "react"
import { MarketQueryResult } from "@/lib/marketConfig"
import { toggleExcludedCompany } from "@/lib/marketConfig"

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
  titres:               "Intitulés",
}

export default function ResultTable({ result, excludedCompanies, onExclusionChange }: Props) {
  const [togglingRow, setTogglingRow] = useState<string | null>(null)
  const [expandedRow, setExpandedRow] = useState<string | null>(null)
  const isQ11 = result.query_id === "Q11"

  const { colonnes, lignes } = result

  if (!lignes.length) {
    return <p className="text-sm text-gray-400 py-8 text-center">Aucune donnée pour cette période.</p>
  }

  async function handleToggle(nom: string) {
    const isExcluded = excludedCompanies.includes(nom)
    setTogglingRow(nom)
    try {
      const updated = await toggleExcludedCompany(nom, isExcluded)
      onExclusionChange(updated.entreprises)
    } finally {
      setTogglingRow(null)
    }
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-gray-200">
      <table className="min-w-full text-sm">
        <thead className="bg-gray-50 border-b border-gray-200">
          <tr>
            {colonnes.map(col => (
              <th key={col} className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide whitespace-nowrap">
                {COL_LABELS[col] ?? col}
              </th>
            ))}
            {isQ11 && (
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">
                Intitulés
              </th>
            )}
            {isQ11 && (
              <th className="px-4 py-3 w-10" />
            )}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100 bg-white">
          {lignes.map((row, i) => {
            const nom = row.entreprise_nom as string | undefined
            const isExcluded = nom ? excludedCompanies.includes(nom) : false
            const isToggling = nom === togglingRow
            const isExpanded = nom === expandedRow

            return (
              <>
                <tr
                  key={i}
                  className={[
                    "transition-colors",
                    isExcluded ? "opacity-40 bg-gray-50" : "hover:bg-gray-50",
                  ].join(" ")}
                >
                  {colonnes.map(col => (
                    <td key={col} className="px-4 py-3 text-gray-800 whitespace-nowrap">
                      {String(row[col] ?? "—")}
                    </td>
                  ))}

                  {/* Colonne titres expandable */}
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

                  {/* Toggle exclusion */}
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

                {/* Ligne expandée — intitulés */}
                {isQ11 && isExpanded && nom && (
                  <tr key={`${i}-expanded`} className="bg-blue-50">
                    <td colSpan={colonnes.length + 2} className="px-6 py-3">
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
              </>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}