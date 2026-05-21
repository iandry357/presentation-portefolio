'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import SanofiStats from '@/components/sanofi/SanofiStats';
import SanofiSidebar, { SanofiView, SanofiFilters } from '@/components/sanofi/SanofiSidebar';
import ClinicalTrialsView from '@/components/sanofi/ClinicalTrialsView';
import PubMedView from '@/components/sanofi/PubMedView';
import NewsView from '@/components/sanofi/NewsView';
import RagView from '@/components/sanofi/RagView';
import { fetchSanofiStats, SanofiStats as StatsType } from '@/lib/sanofiApi';
import MlView from '@/components/sanofi/ml/MlView';
import PressReleasesView from '@/components/sanofi/PressReleasesView';

const DEFAULT_FILTERS: SanofiFilters = {
  clinical: { phase: '', status: '' },
  rag: { sources: [] },
};

export default function SanofiPage() {
  const [activeView, setActiveView] = useState<SanofiView>('clinical-trials');
  const [filters, setFilters] = useState<SanofiFilters>(DEFAULT_FILTERS);
  const [stats, setStats] = useState<StatsType | null>(null);
  const [statsLoading, setStatsLoading] = useState(true);

  useEffect(() => {
    fetchSanofiStats()
      .then(setStats)
      .finally(() => setStatsLoading(false));
  }, []);

  return (
    // <div className="container mx-auto px-4 py-8">
    <div className="container mx-auto px-4 py-8 overflow-hidden">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-gray-500 mb-6">
        <Link href="/realisations" className="hover:text-gray-700 transition-colors">
          Réalisations
        </Link>
        <span>/</span>
        <span className="text-gray-900 font-medium">Sanofi Investigation</span>
      </div>

      {/* Titre */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 mb-1">Sanofi Investigation</h1>
        <p className="text-sm text-gray-500">
          Data source — ClinicalTrials.gov · PubMed · Google News · Press Release
        </p>
      </div>

      {/* Stats */}
      <SanofiStats stats={stats} loading={statsLoading} />

      {/* Layout 2 colonnes */}
      {/* <div className="flex gap-6 items-start"> */}
      {/* <div className="flex gap-4 items-start"> */}
      <div className="flex flex-col md:flex-row gap-6 items-start">
        <SanofiSidebar
          activeView={activeView}
          onViewChange={setActiveView}
          filters={filters}
          onFiltersChange={setFilters}
        />

        {/* Zone résultats */}
        <div className="flex-1 min-w-0">
          {activeView === 'clinical-trials' && (
            <ClinicalTrialsView
              phase={filters.clinical.phase}
              status={filters.clinical.status}
            />
          )}
          {activeView === 'pubmed' && <PubMedView />}
          {activeView === 'news' && <NewsView />}
          {activeView === 'press-releases' && <PressReleasesView />}
          {activeView === 'rag' && <RagView sources={filters.rag.sources} />}
          {activeView === 'ml' && <MlView />}
        </div>
      </div>
    </div>
  );
}