'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import BanqueStats from '@/components/banque-de-france/BanqueStats';
import BanqueSidebar, { BanqueView } from '@/components/banque-de-france/BanqueSidebar';
import NewsView from '@/components/banque-de-france/NewsView';
import RagView from '@/components/banque-de-france/RagView';
import MlView from '@/components/banque-de-france/ml/MlView';
import { fetchBdfStats, BdfStats as StatsType } from '@/lib/banqueApi';

export default function BanqueDeFrancePage() {
  const [activeView, setActiveView] = useState<BanqueView>('news');
  const [stats, setStats]           = useState<StatsType | null>(null);
  const [statsLoading, setStatsLoading] = useState(true);

  useEffect(() => {
    fetchBdfStats()
      .then(setStats)
      .finally(() => setStatsLoading(false));
  }, []);

  return (
    <div className="container mx-auto px-4 py-8 overflow-hidden">
      <div className="flex items-center gap-2 text-sm text-gray-500 mb-6">
        <Link href="/realisations" className="hover:text-gray-700 transition-colors">
          Réalisations
        </Link>
        <span>/</span>
        <span className="text-gray-900 font-medium">Banque de France</span>
      </div>

      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 mb-1">Banque de France</h1>
        <p className="text-sm text-gray-500">
          Suptech ACPR · Classification griefs · RAG · Topic Modeling · Scoring EBA
        </p>
      </div>

      <BanqueStats stats={stats} loading={statsLoading} />

      <div className="flex flex-col md:flex-row gap-6 items-start">
        <BanqueSidebar activeView={activeView} onViewChange={setActiveView} />

        <div className="flex-1 min-w-0">
          {activeView === 'news' && <NewsView />}
          {activeView === 'rag'  && <RagView />}
          {activeView === 'ml'   && <MlView />}
        </div>
      </div>
    </div>
  );
}