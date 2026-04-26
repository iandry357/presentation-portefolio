"use client"

import { useEffect, useState } from "react"
import QuerySelector from "@/components/market/QuerySelector"
import FilterBar from "@/components/market/FilterBar"
import ResultChart from "@/components/market/ResultChart"
import ResultTable from "@/components/market/ResultTable"
import ExcludedCompaniesManager from "@/components/market/ExcludedCompaniesManager"
import {
  fetchMarketQuery,
  fetchExcludedCompanies,
  QUERIES,
  type Periode,
  type Source,
  type MarketQueryResult,
  type QueryMeta,
} from "@/lib/marketConfig"

export default function MarketPage() {
  const [selectedId, setSelectedId]       = useState<string | null>(null)
  const [periode, setPeriode]             = useState<Periode>("30j")
  const [source, setSource]               = useState<Source>("toutes")
  const [result, setResult]               = useState<MarketQueryResult | null>(null)
  const [loading, setLoading]             = useState(false)
  const [error, setError]                 = useState<string | null>(null)
  const [excluded, setExcluded]           = useState<string[]>([])

  const selectedQuery: QueryMeta | null = QUERIES.find(q => q.id === selectedId) ?? null
  const isTableRender = selectedQuery?.rendu === "tableau"

  // Charge la liste d'exclusion au montage
  useEffect(() => {
    fetchExcludedCompanies()
      .then(r => setExcluded(r.entreprises))
      .catch(() => {})
  }, [])

  async function handleSubmit() {
    if (!selectedId) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const data = await fetchMarketQuery(selectedId, { periode, source })
      setResult(data)
    } catch (e) {
      setError("Impossible de charger les données. Réessaie dans quelques instants.")
    } finally {
      setLoading(false)
    }
  }

  // Relance automatiquement Q11 après un changement d'exclusion
  async function handleExclusionChange(updated: string[]) {
    setExcluded(updated)
    if (selectedId === "Q11" && result) {
      await handleSubmit()
    }
  }

  return (
    <main className="max-w-7xl mx-auto px-4 py-8">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-gray-900">Observatoire Marché</h1>
        <p className="text-sm text-gray-500 mt-1">
          Analyses du marché de l&apos;emploi data &amp; IA en France — données BigQuery temps réel
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-6">
        {/* Colonne gauche — sélecteur */}
        <aside className="flex flex-col gap-4">
          <QuerySelector selected={selectedId} onSelect={setSelectedId} />
          <ExcludedCompaniesManager entreprises={excluded} onUpdate={handleExclusionChange} />
        </aside>

        {/* Colonne droite — filtres + résultat */}
        <div className="flex flex-col gap-4">
          <FilterBar
            periode={periode}
            source={source}
            query={selectedQuery}
            onPeriodeChange={setPeriode}
            onSourceChange={setSource}
            onSubmit={handleSubmit}
            loading={loading}
          />

          {/* État vide */}
          {!result && !loading && !error && (
            <div className="flex items-center justify-center h-64 border border-dashed border-gray-200 rounded-lg">
              <p className="text-sm text-gray-400">
                Sélectionne une analyse et clique sur Analyser
              </p>
            </div>
          )}

          {/* Chargement */}
          {loading && (
            <div className="flex items-center justify-center h-64 border border-gray-100 rounded-lg bg-gray-50">
              <p className="text-sm text-gray-400 animate-pulse">Interrogation BigQuery…</p>
            </div>
          )}

          {/* Erreur */}
          {error && (
            <div className="border border-red-200 bg-red-50 rounded-lg px-5 py-4 text-sm text-red-700">
              {error}
            </div>
          )}

          {/* Résultat */}
          {result && !loading && (
            <div className="border border-gray-200 rounded-lg bg-white px-5 py-5">
              <div className="mb-4">
                <h2 className="text-base font-semibold text-gray-900">{result.titre}</h2>
                <p className="text-xs text-gray-500 mt-0.5">{result.description}</p>
                <p className="text-xs text-gray-400 mt-1">
                  {result.total} ligne{result.total > 1 ? "s" : ""} —{" "}
                  {result.params.periode} · {result.params.source}
                </p>
              </div>

              {isTableRender ? (
                <ResultTable
                  result={result}
                  excludedCompanies={excluded}
                  onExclusionChange={handleExclusionChange}
                />
              ) : (
                // <ResultChart result={result} />
                <ResultChart result={result} rendu={selectedQuery!.rendu} />
              )}
            </div>
          )}
        </div>
      </div>
    </main>
  )
}