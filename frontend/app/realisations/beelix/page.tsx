'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import {
  ComptesView, ConcurrenceView, BesoinsView, NewsView, RagView, formatDate,
} from '@/components/beelix/BeelixViews';
import { fetchBeelixStats, BeelixStats } from '@/lib/beelixApi';

type Vue = 'comptes' | 'concurrence' | 'besoins' | 'rag' | 'news';

const VUES: { id: Vue; label: string }[] = [
  { id: 'comptes', label: 'Comptes qui recrutent' },
  { id: 'concurrence', label: 'Concurrence' },
  { id: 'besoins', label: 'Besoins' },
  { id: 'rag', label: 'Ask AI' },
  { id: 'news', label: 'Actualités' },
];

function Tuile({ valeur, libelle, detail }: { valeur: string; libelle: string; detail?: string }) {
  return (
    <div className="border rounded-lg p-4 bg-white">
      <p className="text-2xl font-bold text-gray-900">{valeur}</p>
      <p className="text-xs text-gray-500">{libelle}</p>
      {detail && <p className="text-xs text-gray-400 mt-1">{detail}</p>}
    </div>
  );
}

export default function BeelixPage() {
  const [vue, setVue] = useState<Vue>('comptes');
  const [stats, setStats] = useState<BeelixStats | null>(null);

  useEffect(() => {
    fetchBeelixStats().then(setStats).catch(() => setStats(null));
  }, []);

  const nombre = (n?: number) => (n === undefined ? '—' : n.toLocaleString('fr-FR'));

  return (
    <div className="container mx-auto px-4 py-8 overflow-hidden">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-gray-500 mb-6">
        <Link href="/realisations" className="hover:text-gray-700 transition-colors">
          Réalisations
        </Link>
        <span>/</span>
        <span className="text-gray-900 font-medium">Beelix</span>
      </div>

      {/* Titre */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 mb-1">Beelix — signaux de prospection</h1>
        <p className="text-sm text-gray-500">
          Offres data / IA publiées en Île-de-France, rattachées au secteur de l&apos;entreprise qui recrute
          {stats?.periode_debut && (
            <> · du {formatDate(stats.periode_debut)} au {formatDate(stats.periode_fin)}</>
          )}
        </p>
      </div>

      {/* Tuiles */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <Tuile valeur={nombre(stats?.offres_cibles)} libelle="offres dans les 6 secteurs Beelix" />
        <Tuile valeur={nombre(stats?.comptes_cibles)} libelle="comptes qui recrutent" />
        <Tuile
          valeur={nombre(stats?.nb_concurrents)}
          libelle="ESN et cabinets actifs"
          detail={stats ? `${nombre(stats.offres_concurrence)} offres` : undefined}
        />
        <Tuile
          valeur={nombre(stats?.total_offres)}
          libelle="offres analysées"
          detail={stats?.charge_le ? `données du ${formatDate(stats.charge_le)}` : undefined}
        />
      </div>

      {/* Onglets */}
      <div className="flex flex-wrap gap-2 mb-6 border-b">
        {VUES.map(v => (
          <button
            key={v.id}
            onClick={() => setVue(v.id)}
            className={`px-4 py-2 text-sm -mb-px border-b-2 transition-colors ${
              vue === v.id
                ? 'border-blue-600 text-blue-700 font-medium'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            {v.label}
          </button>
        ))}
      </div>

      {vue === 'comptes' && <ComptesView />}
      {vue === 'concurrence' && <ConcurrenceView />}
      {vue === 'besoins' && <BesoinsView />}
      {vue === 'rag' && <RagView />}
      {vue === 'news' && <NewsView />}

      {/* Méthode */}
      <div className="mt-10 border rounded-lg p-4 bg-gray-50 text-xs text-gray-500 space-y-1">
        <p className="font-semibold text-gray-600">Méthode et limites</p>
        <p>Source : offres collectées chaque jour (France Travail et alertes de 10 sites d&apos;emploi), dédoublonnées ; périmètre data / IA en Île-de-France.</p>
        <p>Secteur : code NAF de l&apos;entreprise qui recrute ; les offres sans entreprise identifiée ne sont pas rattachées.</p>
        <p>Ask AI : recherche sémantique sur les fiches d&apos;offres et les actualités ; les réponses citent leurs sources et ne donnent pas de totaux.</p>
        <p>Aucune collecte du site beelix.fr (son robots.txt l&apos;interdit).</p>
      </div>
    </div>
  );
}
