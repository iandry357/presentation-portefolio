'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import SavenciaStats from '@/components/savencia/SavenciaStats';
import SavenciaSidebar, { SavenciaView, SavenciaFilters } from '@/components/savencia/SavenciaSidebar';
import NewsView from '@/components/savencia/NewsView';
import AskAiView from '@/components/savencia/AskAiView';
import MlView from '@/components/savencia/ml/MlView';
import { fetchSavenciaStats, SavenciaStats as StatsType } from '@/lib/savenciaApi';

const DEFAULT_FILTERS: SavenciaFilters = {
  feed_name: '',
};

export default function SavenciaPage() {
  const [activeView, setActiveView] = useState<SavenciaView>('news');
  const [filters, setFilters] = useState<SavenciaFilters>(DEFAULT_FILTERS);
  const [stats, setStats] = useState<StatsType | null>(null);
  const [statsLoading, setStatsLoading] = useState(true);

  useEffect(() => {
    fetchSavenciaStats()
      .then(setStats)
      .finally(() => setStatsLoading(false));
  }, []);

  return (
    <div className="container mx-auto px-4 py-8 overflow-hidden">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-gray-500 mb-6">
        <Link href="/realisations" className="hover:text-gray-700 transition-colors">
          Réalisations
        </Link>
        <span>/</span>
        <span className="text-gray-900 font-medium">Savencia Dashboard</span>
      </div>

      {/* Titre */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 mb-1">Savencia Dashboard</h1>
        <p className="text-sm text-gray-500">
          Data source — Google News · Agroalimentaire IA · Détection maturité fromagère (CR-IDB)
        </p>
      </div>

      {/* Stats */}
      <SavenciaStats stats={stats} loading={statsLoading} />

      {/* Layout 2 colonnes */}
      <div className="flex flex-col md:flex-row gap-6 items-start">
        <SavenciaSidebar
          activeView={activeView}
          onViewChange={setActiveView}
          filters={filters}
          onFiltersChange={setFilters}
        />

        {/* Zone résultats */}
        <div className="flex-1 min-w-0">
          {activeView === 'news' && <NewsView feed_name={filters.feed_name} />}
          {activeView === 'rag'  && <AskAiView />}
          {activeView === 'ml'   && <MlView />}
        </div>
      </div>
    </div>
  );
}