'use client';

import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { ArrowLeft } from 'lucide-react';
import { JobOfferDetail, JobEnriched } from '@/types';
import { getJob, getJobEnriched } from '@/lib/api';
import JobDetail from '@/components/jobs/JobDetail';

export default function JobDetailPage() {
  const params = useParams();
  const router = useRouter();
  const jobId = Number(params.id);

  const [offer, setOffer] = useState<JobOfferDetail | null>(null);
  const [enriched, setEnriched] = useState<JobEnriched | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const offerData = await getJob(jobId);
        setOffer(offerData);

        if (offerData.has_enriched) {
          const enrichedData = await getJobEnriched(jobId);
          setEnriched(enrichedData);
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Erreur de chargement');
      } finally {
        setLoading(false);
      }
    };

    if (jobId) load();
  }, [jobId]);

  return (
    <div className="min-h-[calc(100vh-64px)] bg-gray-50 dark:bg-gray-900 px-4 py-8">
      <div className="max-w-3xl mx-auto space-y-6">

        {/* Retour */}
        <button
          onClick={() => router.back()}
          className="inline-flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          Retour aux offres
        </button>

        {/* Chargement */}
        {loading && (
          <div className="space-y-4">
            <div className="h-48 bg-gray-200 dark:bg-gray-700 rounded-lg animate-pulse" />
            <div className="h-32 bg-gray-200 dark:bg-gray-700 rounded-lg animate-pulse" />
            <div className="h-64 bg-gray-200 dark:bg-gray-700 rounded-lg animate-pulse" />
          </div>
        )}

        {/* Erreur */}
        {error && (
          <div className="text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/30 px-4 py-3 rounded-lg">
            {error}
          </div>
        )}

        {/* Contenu */}
        {!loading && !error && offer && (
          <JobDetail
            offer={offer}
            enriched={enriched}
            onEnrichedUpdate={setEnriched}
          />
        )}
      </div>
    </div>
  );
}