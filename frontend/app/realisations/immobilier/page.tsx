'use client';

import { useState } from 'react';
import Link from 'next/link';
import { Lock } from 'lucide-react';
import { useAccess } from '@/components/AccessProvider';
import ImmobilierSidebar, { ImmobilierView } from '@/components/immobilier/ImmobilierSidebar';
import ImmobilierStats from '@/components/immobilier/ImmobilierStats';
import DpeView from '@/components/immobilier/DpeView';
import PrixView from '@/components/immobilier/PrixView';
import ChangementsView from '@/components/immobilier/ChangementsView';
import BdnbOnglet from '@/components/immobilier/bdnb/BdnbOnglet';
import OrgPage from '@/components/immobilier/org/OrgPage';
import { Lexique } from '@/components/immobilier/Reperes';
import { cn } from '@/lib/utils';

// Bascule vers la nouvelle organisation : false masque les anciens onglets (code conservé), seule OrgPage s'affiche
const ANCIENS_ONGLETS_VISIBLES = true;

const ONGLETS = [
  { id: 'marche', label: 'Marché (DPE + DVF)' },
  { id: 'bdnb', label: 'Bâtiments (BDNB)' },
  { id: 'org', label: 'Nouvelle organisation' },
] as const;

type Onglet = (typeof ONGLETS)[number]['id'];


export default function ImmobilierPage() {
  const { state, unlocked } = useAccess();
  const [vue, setVue] = useState<ImmobilierView>('dpe');
  const [onglet, setOnglet] = useState<Onglet>(ANCIENS_ONGLETS_VISIBLES ? 'marche' : 'org');
  const verrouille = vue === 'changements' && !unlocked;

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="flex items-center gap-2 text-sm text-gray-500 mb-6">
        <Link href="/realisations" className="hover:text-gray-700 transition-colors">
          Réalisations
        </Link>
        <span>/</span>
        <span className="text-gray-900 font-medium">Immobilier</span>
      </div>

      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 mb-1">Immobilier</h1>
        <p className="text-sm text-gray-500">
          Paris · DPE (ADEME) · Prix de vente (DVF) · Pipeline Python · BigQuery · FastAPI
        </p>
      </div>
      {ANCIENS_ONGLETS_VISIBLES && (
        <div
          className="mb-6 inline-flex overflow-hidden rounded border border-gray-200"
          role="group"
          aria-label="Source des données"
        >
          {ONGLETS.map(({ id, label }) => (
            <button
              key={id}
              type="button"
              onClick={() => setOnglet(id)}
              aria-pressed={onglet === id}
              className={cn(
                'px-4 py-2 text-sm font-medium transition-colors',
                onglet === id ? 'bg-blue-50 text-blue-700' : 'bg-white text-gray-600 hover:bg-gray-50',
              )}
            >
              {label}
            </button>
          ))}
        </div>
      )}


      <div className="mb-6">
        <Lexique />
      </div>

      {onglet === 'bdnb' && <BdnbOnglet />}
      {onglet === 'org' && <OrgPage />}

      {onglet === 'marche' && (
        <>
          <div className="mb-6">
            <ImmobilierStats />
          </div>

          <div className="flex flex-col md:flex-row gap-6 items-stretch md:items-start">
            <ImmobilierSidebar activeView={vue} onViewChange={setVue} unlocked={unlocked} />

            <div className="flex-1 min-w-0 w-full">
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
                  {vue === 'dpe' && <DpeView />}
                  {vue === 'prix' && <PrixView />}
                  {vue === 'changements' && <ChangementsView />}
                </>
              )}
            </div>
          </div>
        </>
      )}

    </div>
  );
}
