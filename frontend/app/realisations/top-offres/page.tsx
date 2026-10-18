'use client';

import { useState } from 'react';
import Link from 'next/link';
import { Lock } from 'lucide-react';
import { useAccess } from '@/components/AccessProvider';
import TopSidebar, { TopView } from '@/components/top-offres/TopSidebar';
import OverviewView from '@/components/top-offres/OverviewView';
import TopDuJourView from '@/components/top-offres/TopDuJourView';
import EntreprisesView from '@/components/top-offres/EntreprisesView';
import BrouillonsView from '@/components/top-offres/BrouillonsView';

export default function TopOffresPage() {
  const { state, unlocked } = useAccess();
  const [choix, setChoix] = useState<TopView | null>(null);

  // Par défaut : « Top du jour » si déverrouillé, sinon la vue d'ensemble publique
  const vue: TopView = choix ?? (unlocked ? 'top' : 'overview');
  const verrouille = vue !== 'overview' && !unlocked;

  return (
    <div className="container mx-auto px-4 py-8 overflow-hidden">
      <div className="flex items-center gap-2 text-sm text-gray-500 mb-6">
        <Link href="/realisations" className="hover:text-gray-700 transition-colors">
          Réalisations
        </Link>
        <span>/</span>
        <span className="text-gray-900 font-medium">Top Offres</span>
      </div>

      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 mb-1">Top Offres</h1>
        <p className="text-sm text-gray-500">
          Classement quotidien des offres · Cibles de postes · LLM local · dbt · BigQuery
        </p>
      </div>

      <div className="flex flex-col md:flex-row gap-6 items-start">
        <TopSidebar activeView={vue} onViewChange={setChoix} unlocked={unlocked} />

        <div className="flex-1 min-w-0">
          {/* Rien n'est monté tant que l'état d'accès n'est pas connu : évite des appels voués au 403 */}
          {state === 'loading' && <div className="min-h-[40vh]" aria-busy="true" />}

          {state !== 'loading' && verrouille && (
            <div className="px-4 py-16 text-center">
              <Lock className="w-8 h-8 mx-auto mb-3 text-gray-400" />
              <h2 className="text-lg font-semibold text-gray-900">Zone privée</h2>
              <p className="mt-1 text-sm text-gray-500">
                Utilisez le bouton « Déverrouiller » en haut de la page.
              </p>
            </div>
          )}

          {state !== 'loading' && !verrouille && (
            <>
              {vue === 'overview' && <OverviewView />}
              {vue === 'top' && <TopDuJourView />}
              {vue === 'brouillons' && <BrouillonsView />}
              {vue === 'entreprises' && <EntreprisesView />}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
