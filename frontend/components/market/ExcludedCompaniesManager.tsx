"use client"

import { useState } from "react"
import { toggleExcludedCompany } from "@/lib/marketConfig"

interface Props {
  entreprises: string[]
  onUpdate: (updated: string[]) => void
}

export default function ExcludedCompaniesManager({ entreprises, onUpdate }: Props) {
  const [removing, setRemoving] = useState<string | null>(null)
  const [open, setOpen] = useState(false)

  async function handleRemove(nom: string) {
    setRemoving(nom)
    try {
      const updated = await toggleExcludedCompany(nom, true)
      onUpdate(updated.entreprises)
    } finally {
      setRemoving(null)
    }
  }

  return (
    <div className="border border-gray-200 rounded-lg bg-white">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-5 py-4 text-sm font-medium text-gray-700 hover:bg-gray-50 rounded-lg transition-colors"
      >
        <span>
          Entreprises exclues de Q11
          <span className="ml-2 text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full">
            {entreprises.length}
          </span>
        </span>
        <span className="text-gray-400">{open ? "▲" : "▼"}</span>
      </button>

      {open && (
        <div className="px-5 pb-4 border-t border-gray-100">
          {entreprises.length === 0 ? (
            <p className="text-sm text-gray-400 py-4 text-center">Aucune entreprise exclue.</p>
          ) : (
            <ul className="mt-3 flex flex-wrap gap-2">
              {entreprises.map(nom => (
                <li
                  key={nom}
                  className="flex items-center gap-2 bg-gray-100 rounded-full px-3 py-1 text-sm text-gray-700"
                >
                  <span>{nom}</span>
                  <button
                    onClick={() => handleRemove(nom)}
                    disabled={removing === nom}
                    title="Retirer de la liste d'exclusion"
                    className="text-gray-400 hover:text-red-500 disabled:opacity-50 transition-colors text-xs font-bold"
                  >
                    {removing === nom ? "…" : "×"}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}