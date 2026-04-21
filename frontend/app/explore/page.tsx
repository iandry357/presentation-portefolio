"use client";

import { useEffect, useState, useCallback } from "react";
import { getExploreOffers, getExploreFilters } from "@/lib/api";
import { ExploreOffer, FilterOptions } from "@/types/index";
import ExploreCard from "@/components/explore/ExploreCard";
import ExploreFilters from "@/components/explore/ExploreFilters";

const DEFAULT_FILTERS = {
  titre: "",
  source: "",
  type_contrat: "",
  localisation_libelle: "",
  periode_jours: "",
  entreprise_nom: "",
};

export default function ExplorePage() {
  const [offers, setOffers]         = useState<ExploreOffer[]>([]);
  const [filterOptions, setFilterOptions] = useState<FilterOptions>({
    sources: [], types_contrat: [], regions: [], entreprise_nom: []
  });
  const [filters, setFilters]       = useState(DEFAULT_FILTERS);
  const [page, setPage]             = useState(1);
  const [total, setTotal]           = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [loading, setLoading]       = useState(false);
  const [error, setError]           = useState<string | null>(null);

  // Chargement des options de filtres (une seule fois)
  useEffect(() => {
    getExploreFilters()
      .then(setFilterOptions)
      .catch(() => {});
  }, []);

  const loadOffers = useCallback(async (currentPage: number, currentFilters: typeof DEFAULT_FILTERS) => {
    setLoading(true);
    setError(null);
    try {
      const result = await getExploreOffers({
        page: currentPage,
        page_size: 10,
        source:              currentFilters.source || undefined,
        type_contrat:        currentFilters.type_contrat || undefined,
        localisation_libelle: currentFilters.localisation_libelle || undefined,
        periode_jours:       currentFilters.periode_jours ? Number(currentFilters.periode_jours) : undefined,
        titre:               currentFilters.titre || undefined,
        entreprise_nom:              currentFilters.entreprise_nom || undefined,
      });
      setOffers(result.offers);
      setTotal(result.total);
      setTotalPages(result.total_pages);
    } catch {
      setError("Erreur lors du chargement des offres.");
    } finally {
      setLoading(false);
    }
  }, []);

  // Rechargement quand page ou filtres changent
  useEffect(() => {
    loadOffers(page, filters);
  }, [page, filters, loadOffers]);

  const handleFilterChange = (key: string, value: string) => {
    setPage(1);
    setFilters(prev => ({ ...prev, [key]: value }));
  };

  const handleReset = () => {
    setPage(1);
    setFilters(DEFAULT_FILTERS);
  };

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Explorer le marché</h1>
        <p className="text-sm text-gray-500 mt-1">
          {total > 0 ? `${total.toLocaleString()} offres disponibles` : ""}
        </p>
      </div>

      <div className="flex gap-6">
        {/* Filtres */}
        <aside className="w-64 shrink-0">
          <ExploreFilters
            filters={filterOptions}
            values={filters}
            onChange={handleFilterChange}
            onReset={handleReset}
          />
        </aside>

        {/* Liste */}
        <div className="flex-1 min-w-0">
          {error && (
            <div className="text-sm text-red-600 mb-4">{error}</div>
          )}

          {loading ? (
            <div className="space-y-3">
              {Array.from({ length: 10 }).map((_, i) => (
                <div key={i} className="h-24 bg-gray-100 rounded-lg animate-pulse" />
              ))}
            </div>
          ) : offers.length === 0 ? (
            <div className="text-sm text-gray-500 py-12 text-center">
              Aucune offre trouvée pour ces critères.
            </div>
          ) : (
            <div className="space-y-3">
              {offers.map(offer => (
                <ExploreCard key={offer.id_unique} offer={offer} />
              ))}
            </div>
          )}

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between mt-6">
              <button
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1 || loading}
                className="text-sm px-4 py-2 border border-gray-200 rounded hover:bg-gray-50 disabled:opacity-40"
              >
                ← Précédent
              </button>
              <span className="text-sm text-gray-500">
                Page {page} / {totalPages}
              </span>
              <button
                onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                disabled={page === totalPages || loading}
                className="text-sm px-4 py-2 border border-gray-200 rounded hover:bg-gray-50 disabled:opacity-40"
              >
                Suivant →
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}