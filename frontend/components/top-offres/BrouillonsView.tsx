'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { ExternalLink, RefreshCw } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { FT_BASE_URL, getJobs } from '@/lib/api';
import { formatDateCourte, libelleSource } from '@/lib/topOffres';
import { cn } from '@/lib/utils';
import { JobOfferSummary } from '@/types';

// Paramètres
const TAILLE_PAGE = 50;

// Lien de l'offre d'origine : page France Travail si l'identifiant existe, sinon l'URL enregistrée
function lienBrouillon(offre: JobOfferSummary): string | null {
  if (offre.ft_id && FT_BASE_URL) return `${FT_BASE_URL}${offre.ft_id}`;
  return offre.offer_url || null;
}

export default function BrouillonsView() {
  const [brouillons, setBrouillons] = useState<JobOfferSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getJobs({
        status: 'brouillon',
        page: 1,
        page_size: TAILLE_PAGE,
        hide_consulted: false,
      });
      setBrouillons(data.items);
      setTotal(data.total);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erreur de chargement');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm text-gray-600">
          Offres marquées « Intéressé ». Ouvrez-en une pour coller la description et la présentation de
          l&apos;entreprise (« Modifier »), puis « Valider » l&apos;ajoute à vos offres.
        </p>
        <button
          onClick={load}
          disabled={loading}
          title="Rafraîchir"
          className="shrink-0 p-1.5 text-gray-500 hover:text-gray-700 transition-colors"
        >
          <RefreshCw className={cn('w-4 h-4', loading && 'animate-spin')} />
        </button>
      </div>

      {error && (
        <div className="text-sm text-red-600 bg-red-50 px-4 py-3 rounded-lg">{error}</div>
      )}

      {loading && brouillons.length === 0 && (
        <div className="space-y-3">
          {[1, 2].map(i => (
            <div key={i} className="h-24 border rounded-lg bg-white animate-pulse" />
          ))}
        </div>
      )}

      {!loading && !error && brouillons.length === 0 && (
        <p className="text-center text-sm text-gray-500 py-12">
          Aucun brouillon. Les offres marquées « Intéressé » dans le Top du jour apparaissent ici.
        </p>
      )}

      {brouillons.length > 0 && (
        <>
          <p className="text-xs text-gray-500">
            {total} brouillon{total > 1 ? 's' : ''}
            {total > brouillons.length ? ` (${brouillons.length} affichés)` : ''}
          </p>
          <ul className={cn('space-y-3', loading && 'opacity-60 transition-opacity')}>
            {brouillons.map(offre => {
              const lien = lienBrouillon(offre);
              const complet = Boolean(offre.description);
              const details = [offre.company_name, offre.location_label].filter(Boolean).join(' · ');
              return (
                <li key={offre.id} className="border rounded-lg bg-white p-4 space-y-2">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <h3 className="text-base font-semibold text-gray-900 break-words">{offre.title}</h3>
                      <p className="text-sm text-gray-600">{details || 'Entreprise non renseignée'}</p>
                      <p className="text-xs text-gray-500 mt-0.5">
                        {[
                          libelleSource(offre.source_offer),
                          offre.ft_published_at ? `Publiée le ${formatDateCourte(offre.ft_published_at)}` : null,
                        ]
                          .filter(Boolean)
                          .join(' · ')}
                      </p>
                    </div>
                    <Badge variant={complet ? 'secondary' : 'outline'} className="shrink-0 text-xs">
                      {complet ? 'Prêt à valider' : 'Description à saisir'}
                    </Badge>
                  </div>
                  <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t">
                    {lien ? (
                      <a
                        href={lien}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-xs text-blue-600 hover:underline"
                      >
                        <ExternalLink className="w-3.5 h-3.5" />
                        Voir l&apos;offre
                      </a>
                    ) : (
                      <span className="text-xs text-gray-400">Lien indisponible</span>
                    )}
                    <Link
                      href={`/jobs/${offre.id}`}
                      className="px-3 py-1.5 text-sm rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-medium transition-colors"
                    >
                      Compléter et valider
                    </Link>
                  </div>
                </li>
              );
            })}
          </ul>
        </>
      )}
    </div>
  );
}
