'use client';

import { useState, useEffect, useCallback } from 'react';
import { Briefcase, RefreshCw, Play, Trash2, Filter  } from 'lucide-react';
import { JobFilters, JobOfferSummary } from '@/types';
import { getJobs, triggerPipeline, resetJobs, addManualJob  } from '@/lib/api';
import JobCard from '@/components/jobs/JobCard';
import JobFiltersPanel from '@/components/jobs/JobFilters';

// ============================================================================
// Filtres par défaut
// ============================================================================

const DEFAULT_FILTERS: JobFilters = {
  page: 1,
  page_size: 20,
  hide_consulted: false,
};

function AnimatedDots() {
  return (
    <span className="inline-flex gap-0.5">
      <span className="animate-bounce [animation-delay:0ms]">.</span>
      <span className="animate-bounce [animation-delay:150ms]">.</span>
      <span className="animate-bounce [animation-delay:300ms]">.</span>
    </span>
  );
}

// ============================================================================
// Page Jobs
// ============================================================================

export default function JobsPage() {
  const [filters, setFilters] = useState<JobFilters>(DEFAULT_FILTERS);
  const [offers, setOffers] = useState<JobOfferSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [triggering, setTriggering] = useState(false);
  const [triggerResult, setTriggerResult] = useState<string | null>(null);
  const [resetting, setResetting] = useState(false);           // nouveau
  const [resetResult, setResetResult] = useState<string | null>(null);  // nouveau
  const [showManualModal, setShowManualModal] = useState(false);
  const [manualFtId, setManualFtId] = useState('');
  const [manualLoading, setManualLoading] = useState(false);
  const [manualResult, setManualResult] = useState<string | null>(null);
  const [showFilters, setShowFilters] = useState(false);

//   const isDev = process.env.NEXT_PUBLIC_ENV === 'development';
  const isDev = true;

  // ============================================================================
  // Chargement des offres
  // ============================================================================

  const loadOffers = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getJobs(filters);
      setOffers(data.items);
      setTotal(data.total);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erreur de chargement');
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    loadOffers();
  }, [loadOffers]);

  // ============================================================================
  // Déclenchement manuel pipeline
  // ============================================================================

  const handleTrigger = async () => {
    setTriggering(true);
    setTriggerResult(null);
    try {
      const result = await triggerPipeline();
      setTriggerResult(
        `${result.message} — ${result.offers_collected} collectées, ${result.offers_scored} scorées, ${result.offers_enriched} nouvelles`
      );
      await loadOffers();
    } catch (e) {
      setTriggerResult(e instanceof Error ? e.message : 'Erreur pipeline');
    } finally {
      setTriggering(false);
    }
  };

  // ============================================================================
  // Reset offres (nouveau)
  // ============================================================================

  const handleReset = async () => {
    if (!confirm("Supprimer toutes les offres sauf celles marquées 'postulé' ou 'enregistré' ?\nCette action est irréversible.")) {
      return;
    }

    setResetting(true);
    setResetResult(null);

    try {
      const result = await resetJobs();
      setResetResult(`${result.message} (${result.deleted} supprimée(s))`);
      await loadOffers();  // recharge la liste
    } catch (err: any) {
      setResetResult(err.message || 'Erreur lors du reset');
    } finally {
      setResetting(false);
    }
  };

  const handleManualAdd = async () => {
    if (!manualFtId.trim()) return;
    setManualLoading(true);
    setManualResult(null);
    try {
      const result = await addManualJob(manualFtId.trim());
      // setManualResult(`Offre "${result.title}" ajoutée avec succès`);
      setManualFtId('');
      setShowManualModal(false);
      setManualResult(`Offre "${result.title}" ajoutée avec succès`);
      await loadOffers();
    } catch (e) {
      setManualResult(e instanceof Error ? e.message : 'Erreur ajout manuel');
    } finally {
      setManualLoading(false);
    }
  };

  // ============================================================================
  // Pagination
  // ============================================================================

  const totalPages = Math.ceil(total / filters.page_size);

  return (
    <div className="min-h-[calc(100vh-64px)] bg-gray-50 dark:bg-gray-900 px-4 py-8">
      <div className="max-w-6xl mx-auto space-y-6">

        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
              <Briefcase className="w-6 h-6" />
              Offres d'emploi
            </h1>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
              {total} offre{total > 1 ? 's' : ''} correspondant à votre profil
            </p>
          </div>

          {/* <div className="flex items-center gap-2"> */}
          <div className="flex sm:flex-row flex-col items-end sm:items-center gap-2">
            {/* Refresh */}
            <button
              // onClick={loadOffers}
              onClick={() => { setResetResult(null); setTriggerResult(null); setManualResult(null); loadOffers(); }}
              disabled={loading}
              className="p-2 text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 transition-colors"
              title="Rafraîchir"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>

            {/* Trigger pipeline (dev uniquement) */}
            {isDev && (
              <button
                onClick={handleTrigger}
                disabled={triggering}
                className="inline-flex items-center gap-2 px-4 py-2 bg-gray-900 dark:bg-white text-white dark:text-gray-900 rounded-lg text-sm font-medium hover:bg-gray-800 dark:hover:bg-gray-100 transition-colors disabled:opacity-50"
              >
                <Play className="w-4 h-4" />
                {/* {triggering ? 'Pipeline en cours...' : 'Lancer le pipeline'} */}
                <span className="hidden sm:inline">{triggering ? <>Pipeline en cours<AnimatedDots /></> : 'Lancer le pipeline'}</span>
              </button>
            )}

            {/* Nouveau bouton Reset – visible en dev ou toujours selon ton choix */}
            {isDev && (   // ← ou retire cette condition si tu veux le montrer en prod
              <button
                onClick={handleReset}
                disabled={resetting || loading}
                className="inline-flex items-center gap-2 px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
                title="Supprime toutes les offres sauf postulé/enregistré"
              >
                <Trash2 className="w-4 h-4" />
                {/* {resetting ? 'Reset en cours...' : 'Nettoyer les offres'} */}
                <span className="hidden sm:inline">{resetting ? <>Reset en cours<AnimatedDots /></> : 'Nettoyer les offres'}</span>
              </button>
            )}
            {/* Bouton ajout manuel */}
            <button
              onClick={() => setShowManualModal(true)}
              className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors"
            >
              <span className="sm:hidden">+</span>
              <span className="hidden sm:inline">+ Ajouter une offre</span>
            </button>

            {/* Modale ajout manuel */}
            {showManualModal && (
              <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
                <div className="bg-white dark:bg-gray-800 rounded-lg p-6 w-full max-w-sm space-y-4 shadow-xl">
                  <h2 className="text-base font-semibold text-gray-900 dark:text-white">
                    Ajouter une offre manuellement
                  </h2>
                  <div className="space-y-2">
                    <label className="text-sm text-gray-600 dark:text-gray-400">
                      Numéro de l'offre France Travail
                    </label>
                    <input
                      type="text"
                      value={manualFtId}
                      onChange={e => setManualFtId(e.target.value)}
                      placeholder="ex: 9548593"
                      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                    />
                  </div>
                  {manualResult && (
                    <p className={`text-sm ${manualResult.includes('Erreur') || manualResult.includes('introuvable') ? 'text-red-500' : 'text-green-600'}`}>
                      {manualResult}
                    </p>
                  )}
                  <div className="flex justify-end gap-2">
                    <button
                      onClick={() => { setShowManualModal(false); setManualResult(null); setManualFtId(''); }}
                      className="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white"
                    >
                      Annuler
                    </button>
                    <button
                      onClick={handleManualAdd}
                      disabled={manualLoading || !manualFtId.trim()}
                      className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium disabled:opacity-50"
                    >
                      {manualLoading ? 'Ajout en cours...' : 'Ajouter'}
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Résultat pipeline */}
        {triggerResult && (
          <div className="text-sm bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 px-4 py-3 rounded-lg">
            {triggerResult}
          </div>
        )}

        {/* Nouveau → Résultat reset */}
        {resetResult && (
          <div
            className={`text-sm px-4 py-3 rounded-lg ${
              resetResult.includes('Erreur')
                ? 'bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-300'
                : 'bg-green-50 dark:bg-green-900/30 text-green-700 dark:text-green-300'
            }`}
          >
            {resetResult}
          </div>
        )}

        {manualResult && (
          <div className="text-sm bg-green-50 dark:bg-green-900/30 text-green-700 dark:text-green-300 px-4 py-3 rounded-lg">
            {manualResult}
          </div>
        )}

        {/* Layout principal */}
        <div className="flex gap-6 items-start">

          {/* Filtres */}
          {/* <aside className="w-56 shrink-0 sticky top-4">
            <JobFiltersPanel filters={filters} onChange={setFilters} />
          </aside> */}
          {/* Bouton filtre mobile */}
          <button
            onClick={() => setShowFilters(true)}
            className="sm:hidden flex items-center gap-1 px-3 py-1.5 text-sm border border-gray-200 rounded-lg text-gray-600 hover:bg-gray-100"
          >
            <Filter className="w-4 h-4" />
            Filtres
          </button>

          {/* Overlay mobile */}
          {showFilters && (
            <div
              className="fixed inset-0 bg-black/40 z-40 sm:hidden"
              onClick={() => setShowFilters(false)}
            >
              <div
                className="absolute left-0 top-0 h-full w-72 bg-white dark:bg-gray-800 overflow-y-auto p-4 z-50"
                onClick={e => e.stopPropagation()}
              >
                <JobFiltersPanel
                  filters={filters}
                  onChange={setFilters}
                  onClose={() => setShowFilters(false)}
                />
              </div>
            </div>
          )}

          {/* Sidebar desktop */}
          <aside className="hidden sm:block w-56 shrink-0 sticky top-4">
            <JobFiltersPanel filters={filters} onChange={setFilters} />
          </aside>

          {/* Liste offres */}
          <div className="flex-1 space-y-4">
            {error && (
              <div className="text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/30 px-4 py-3 rounded-lg">
                {error}
              </div>
            )}

            {loading && (
              <div className="space-y-4">
                {Array.from({ length: 5 }).map((_, i) => (
                  <div key={i} className="h-40 bg-gray-200 dark:bg-gray-700 rounded-lg animate-pulse" />
                ))}
              </div>
            )}

            {!loading && !error && offers.length === 0 && (
              <div className="text-center py-16 text-gray-500 dark:text-gray-400">
                <Briefcase className="w-10 h-10 mx-auto mb-3 opacity-30" />
                <p>Aucune offre trouvée</p>
                <p className="text-sm mt-1">Modifiez vos filtres ou lancez le pipeline</p>
              </div>
            )}

            {!loading && offers.map(offer => (
              <JobCard key={offer.id} offer={offer} />
            ))}

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-2 pt-4">
                <button
                  onClick={() => setFilters(f => ({ ...f, page: f.page - 1 }))}
                  disabled={filters.page === 1}
                  className="px-3 py-1.5 text-sm border border-gray-200 dark:border-gray-700 rounded disabled:opacity-40 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                >
                  Précédent
                </button>
                <span className="text-sm text-gray-500 dark:text-gray-400">
                  {filters.page} / {totalPages}
                </span>
                <button
                  onClick={() => setFilters(f => ({ ...f, page: f.page + 1 }))}
                  disabled={filters.page === totalPages}
                  className="px-3 py-1.5 text-sm border border-gray-200 dark:border-gray-700 rounded disabled:opacity-40 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                >
                  Suivant
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}