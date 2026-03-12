'use client';

import { useEffect, useState, useRef } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, Building2 } from 'lucide-react';
import { CompanyProfile } from '@/types';
import CompanyDetail, { hasPending } from '@/components/jobs/CompanyDetail';
import { useRouter } from 'next/navigation';
import { getCompany, deleteCompany } from '@/lib/api';
import { Trash2 } from 'lucide-react';

// ============================================================================
// Page
// ============================================================================

export default function CompanyDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [profile, setProfile] = useState<CompanyProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const router = useRouter();

  const handleDelete = async () => {
    if (!profile) return;
    try {
        await deleteCompany(profile.id);
        router.push('/companies');
    } catch (e) {
        console.error(e);
    }
  };

  const stopPolling = () => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  };

  const startPolling = (profileId: number) => {
    stopPolling();
    pollingRef.current = setInterval(async () => {
      try {
        const updated = await getCompany(profileId);
        setProfile(updated);
        if (!hasPending(updated)) stopPolling();
      } catch {
        stopPolling();
      }
    }, 5000);
  };

  
  useEffect(() => {
    if (!id) return;
    getCompany(Number(id))
      .then(p => {
        setProfile(p);
        if (hasPending(p)) startPolling(p.id);
      })
      .catch(() => setError('Impossible de charger la fiche entreprise.'))
      .finally(() => setLoading(false));

    return () => stopPolling();
  }, [id]);

  // ── Rendu ──────────────────────────────────────────────────────────────

  return (
    <main className="max-w-3xl mx-auto px-4 py-8 space-y-6">

      {/* Retour */}
      <Link
        href="/companies"
        className="inline-flex items-center gap-1.5 text-sm text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
        Toutes les fiches
      </Link>

      {loading && (
        <p className="text-sm text-gray-500 dark:text-gray-400">Chargement…</p>
      )}

      {error && (
        <p className="text-sm text-red-500 dark:text-red-400">{error}</p>
      )}

      {!loading && !error && !profile && (
        <p className="text-sm text-gray-500 dark:text-gray-400">Fiche introuvable.</p>
      )}

      {profile && (
        <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-6 space-y-4">
          {/* Header */}
          <div className="flex items-center gap-3">
            <Building2 className="w-5 h-5 text-gray-400 shrink-0" />
            <h1 className="text-xl font-bold text-gray-900 dark:text-white">
              {profile.name}
            </h1>
          </div>

          {/* Contenu */}
          <CompanyDetail
            profile={profile}
            onProfileUpdate={p => {
              setProfile(p);
              if (hasPending(p)) startPolling(p.id);
            }}
          />

          {process.env.NEXT_PUBLIC_ENV !== 'production' && (
            <button
                onClick={handleDelete}
                className="inline-flex items-center gap-2 px-3 py-1.5 border border-red-200 dark:border-red-800 text-red-600 dark:text-red-400 rounded-lg text-sm hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
            >
                <Trash2 className="w-3.5 h-3.5" />
                Supprimer la fiche
            </button>
            )}
        </div>
      )}

    </main>
  );
}