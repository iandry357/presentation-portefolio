"use client"

import { QUERIES, QueryMeta } from "@/lib/marketConfig"

interface Props {
  selected: string | null
  onSelect: (id: string) => void
}

export default function QuerySelector({ selected, onSelect }: Props) {
  return (
    <div className="flex flex-col gap-2">
      <p className="text-sm font-medium text-gray-500 uppercase tracking-wide mb-1">
        Choisir une analyse
      </p>
      {QUERIES.map((q: QueryMeta) => (
        <button
          key={q.id}
          onClick={() => onSelect(q.id)}
          className={[
            "text-left px-4 py-3 rounded-lg border transition-colors",
            selected === q.id
              ? "border-blue-500 bg-blue-50 text-blue-900"
              : "border-gray-200 bg-white hover:border-gray-300 hover:bg-gray-50 text-gray-800",
          ].join(" ")}
        >
          <span className="text-xs font-mono text-gray-400 mr-2">{q.id}</span>
          <span className="font-medium text-sm">{q.titre}</span>
          {q.sourceRequise && (
            <span className="ml-2 text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full">
              FT API
            </span>
          )}
          <p className="text-xs text-gray-500 mt-1 ml-0">{q.description}</p>
        </button>
      ))}
    </div>
  )
}