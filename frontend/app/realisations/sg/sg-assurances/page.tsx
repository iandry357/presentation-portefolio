'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import SgStats from '@/components/sg/sg-assurances/SgStats';
import SgSidebar, { SgView } from '@/components/sg/sg-assurances/SgSidebar';
import NewsView from '@/components/sg/sg-assurances/NewsView';
import RagView from '@/components/sg/sg-assurances/RagView';
import MlView from '@/components/sg/sg-assurances/ml/MlView';
import QwenView from '@/components/sg/sg-assurances/QwenView';
import { fetchSgStats, SgStats as StatsType } from '@/lib/sgApi';

export default function SgAssurancesPage() {
  const [activeView, setActiveView] = useState<SgView>('news');
  const [stats, setStats]           = useState<StatsType | null>(null);
  const [statsLoading, setStatsLoading] = useState(true);

  useEffect(() => {
    fetchSgStats()
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
        <span className="text-gray-900 font-medium">SG Assurances</span>
      </div>

      {/* Titre */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 mb-1">SG Assurances</h1>
        <p className="text-sm text-gray-500">
          Veille assurance · YOLO · NER · RAG · Qwen fine-tuné QLoRA
        </p>
      </div>

      {/* Stats */}
      <SgStats stats={stats} loading={statsLoading} />

      {/* Layout 2 colonnes */}
      <div className="flex flex-col md:flex-row gap-6 items-start">
        <SgSidebar activeView={activeView} onViewChange={setActiveView} />

        {/* Zone résultats */}
        <div className="flex-1 min-w-0">
          {activeView === 'news'  && <NewsView />}
          {activeView === 'rag'   && <RagView />}
          {activeView === 'ml'    && <MlView />}
          {activeView === 'qwen'  && <QwenView />}
        </div>
      </div>
    </div>
  );
}