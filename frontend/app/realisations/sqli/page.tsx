'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import SqliStats from '@/components/sqli/SqliStats';
import SqliSidebar, { SqliView } from '@/components/sqli/SqliSidebar';
import NewsView from '@/components/sqli/NewsView';
import RagView from '@/components/sqli/RagView';
import TopicView from '@/components/sqli/TopicView';
import { fetchSqliStats, SqliStats as StatsType } from '@/lib/sqliApi';

export default function SqliPage() {
  const [activeView, setActiveView] = useState<SqliView>('news');
  const [stats, setStats]           = useState<StatsType | null>(null);
  const [statsLoading, setStatsLoading] = useState(true);

  useEffect(() => {
    fetchSqliStats()
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
        <span className="text-gray-900 font-medium">SQLI</span>
      </div>

      {/* Titre */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 mb-1">SQLI</h1>
        <p className="text-sm text-gray-500">
          Veille Google News · RAG · Topic Modeling LDA
        </p>
      </div>

      {/* Stats */}
      <SqliStats stats={stats} loading={statsLoading} />

      {/* Layout 2 colonnes */}
      <div className="flex flex-col md:flex-row gap-6 items-start">
        <SqliSidebar activeView={activeView} onViewChange={setActiveView} />

        {/* Zone résultats */}
        <div className="flex-1 min-w-0">
          {activeView === 'news'   && <NewsView />}
          {activeView === 'rag'    && <RagView />}
          {activeView === 'topics' && <TopicView />}
        </div>
      </div>
    </div>
  );
}
