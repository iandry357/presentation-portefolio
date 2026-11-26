'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Lock } from 'lucide-react';
import { useAccess } from '@/components/AccessProvider';
import {
  NewsView, RagView, TopicView, CasClientsView, RecrutementView, formatDate,
} from '@/components/wavestone/WavestoneViews';
import { fetchWavestoneStats, WavestoneStats } from '@/lib/wavestoneApi';

type Vue = 'rag' | 'news' | 'topics' | 'cas_clients' | 'recrutement';

const VUES: { id: Vue; label: string; prive?: boolean }[] = [
  { id: 'rag', label: 'Ask AI', prive: true },
  { id: 'news', label: 'Actualités' },
  { id: 'topics', label: 'Thèmes' },
  { id: 'cas_clients', label: 'Cas clients' },
  { id: 'recrutement', label: 'Recrutement' },
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

export default function WavestonePage() {
  const { state, unlocked } = useAccess();
  const [choix, setChoix] = useState<Vue | null>(null);
  const [stats, setStats] = useState<WavestoneStats | null>(null);

  // Par défaut : Ask AI si déverrouillé, sinon les actualités publiques
  const vue: Vue = choix ?? (unlocked ? 'rag' : 'news');
  const verrouille = !!VUES.find(v => v.id === vue)?.prive && !unlocked;

  useEffect(() => {
    fetchWavestoneStats().then(setStats).catch(() => setStats(null));
  }, []);

  const nombre = (n?: number) => (n === undefined ? '—' : n.toLocaleString('fr-FR'));
  const somme = (filtre: (s: { section: string; langue: string | null }) => boolean) =>
    stats ? stats.sections.filter(filtre).reduce((n, s) => n + s.nb_documents, 0) : undefined;
  const siteFr = somme(s => s.section !== 'presse' && s.langue === 'fr');
  const siteEn = somme(s => s.section !== 'presse' && s.langue === 'en');
  const presse = somme(s => s.section === 'presse');

  return (
    <div className="container mx-auto px-4 py-8 overflow-hidden">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-gray-500 mb-6">
        <Link href="/realisations" className="hover:text-gray-700 transition-colors">
          Réalisations
        </Link>
        <span>/</span>
        <span className="text-gray-900 font-medium">Wavestone</span>
      </div>

      {/* Titre */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 mb-1">Wavestone — veille et postes ouverts</h1>
        <p className="text-sm text-gray-500">
          Publications, cas clients et communiqués de wavestone.com (FR et EN), presse, et offres Wavestone repérées chaque jour
          {stats?.last_updated && <> · mis à jour le {formatDate(stats.last_updated)}</>}
        </p>
      </div>

      {/* Tuiles */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <Tuile valeur={nombre(siteFr)} libelle="pages du site en français" />
        <Tuile valeur={nombre(siteEn)} libelle="pages du site en anglais" />
        <Tuile valeur={nombre(presse)} libelle="articles de presse" />
        <Tuile
          valeur={nombre(stats?.intitules_distincts)}
          libelle="postes ouverts repérés"
          detail={stats ? `${nombre(stats.total_offres)} publications` : undefined}
        />
      </div>

      {/* Onglets */}
      <div className="flex flex-wrap gap-2 mb-6 border-b">
        {VUES.map(v => (
          <button
            key={v.id}
            onClick={() => setChoix(v.id)}
            className={`inline-flex items-center gap-1.5 px-4 py-2 text-sm -mb-px border-b-2 transition-colors ${
              vue === v.id
                ? 'border-blue-600 text-blue-700 font-medium'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            {v.label}
            {v.prive && !unlocked && <Lock className="w-3.5 h-3.5" />}
          </button>
        ))}
      </div>

      {/* Rien n'est monté tant que l'état d'accès n'est pas connu : évite des appels voués au 403 */}
      {state === 'loading' && <div className="min-h-[40vh]" aria-busy="true" />}

      {state !== 'loading' && verrouille && (
        <div className="px-4 py-16 text-center">
          <Lock className="w-8 h-8 mx-auto mb-3 text-gray-400" />
          <h2 className="text-lg font-semibold text-gray-900">Zone privée</h2>
          <p className="mt-1 text-sm text-gray-500">Utilisez le bouton « Déverrouiller » en haut de la page.</p>
        </div>
      )}

      {state !== 'loading' && !verrouille && (
        <>
          {vue === 'rag' && <RagView />}
          {vue === 'news' && <NewsView />}
          {vue === 'topics' && <TopicView />}
          {vue === 'cas_clients' && <CasClientsView />}
          {vue === 'recrutement' && <RecrutementView unlocked={unlocked} />}
        </>
      )}

      {/* Méthode */}
      <div className="mt-10 border rounded-lg p-4 bg-gray-50 text-xs text-gray-500 space-y-1">
        <p className="font-semibold text-gray-600">Méthode et limites</p>
        <p>Site : pages listées par les sitemaps de wavestone.com (communiqués, publications, cas clients), en français et en anglais ; robots.txt respecté, l&apos;API WordPress n&apos;est pas utilisée ; les pages « expertises » ne sont pas reprises (adresses du sitemap périmées).</p>
        <p>Presse : Google News, hors articles publiés par Wavestone elle-même (déjà couverts par le site) ; titre et résumé seulement.</p>
        <p>Ask AI (accès privé) : recherche sémantique sur les pages, la presse et les fiches d&apos;offres ; les réponses citent leurs sources et ne donnent pas de totaux.</p>
        <p>Thèmes : LDA, un modèle par langue, sur le début de chaque communiqué, publication et article de presse ; nombre de thèmes choisi automatiquement (cohérence et redondance des thèmes) ; libellés générés par un LLM.</p>
        <p>Cas clients : un LLM décrit chaque cas à partir de son texte (secteur du client, type de mission, résumé), puis regroupe ces descriptions en catégories ; aucune catégorie n&apos;est fixée à la main.</p>
        <p>Recrutement : offres collectées par ma veille emploi (data / IA, Île-de-France) sur 90 jours ; le score d&apos;adéquation à mon profil (pas la qualité du poste) n&apos;est visible qu&apos;avec l&apos;accès privé.</p>
      </div>
    </div>
  );
}
