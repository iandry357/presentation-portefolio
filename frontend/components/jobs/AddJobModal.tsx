'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { JobOfferDetail } from '@/types';
import FranceTravailForm from './FranceTravailForm';
import ExternalJobForm from './ExternalJobForm';
import { fetchGmailAlerts } from '@/lib/api';

type Mode = 'france_travail' | 'externe' | 'gmail';

interface AddJobModalProps {
  onSuccess: (job: JobOfferDetail, triggerEnrichment: boolean) => void;
  onClose: () => void;
}

export default function AddJobModal({ onSuccess, onClose }: AddJobModalProps) {
  const [mode, setMode] = useState<Mode>('france_travail');
  const [gmailLoading, setGmailLoading] = useState(false);
  const [gmailResult, setGmailResult] = useState<{ inserted: number; skipped: number; errors: number } | null>(null);
  const [gmailError, setGmailError] = useState<string | null>(null);
  const router = useRouter();

  const handleGmailFetch = async () => {
    setGmailLoading(true);
    setGmailError(null);
    setGmailResult(null);
    try {
      const result = await fetchGmailAlerts();
      setGmailResult(result);
      if (result.inserted > 0) {
        onClose();
        router.refresh();
      }
    } catch (e) {
      setGmailError(e instanceof Error ? e.message : 'Erreur lors de la récupération');
    } finally {
      setGmailLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className={`bg-white dark:bg-gray-800 rounded-lg w-full shadow-xl flex flex-col max-h-[90vh] ${mode === 'externe' ? 'max-w-2xl' : 'max-w-lg'}`}>

        {/* Header */}
        <div className="p-6 pb-4 shrink-0">
          <h2 className="text-base font-semibold text-gray-900 dark:text-white mb-4">
            Ajouter une offre
          </h2>

          {/* Toggle 3 options */}
          <div className="flex rounded-lg border border-gray-200 dark:border-gray-700 p-1 bg-gray-50 dark:bg-gray-900">
            <button
              onClick={() => setMode('france_travail')}
              className={`flex-1 px-3 py-2 text-sm font-medium rounded-md transition-colors ${
                mode === 'france_travail'
                  ? 'bg-white dark:bg-gray-800 text-gray-900 dark:text-white shadow-sm'
                  : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
              }`}
            >
              France Travail
            </button>
            <button
              onClick={() => setMode('externe')}
              className={`flex-1 px-3 py-2 text-sm font-medium rounded-md transition-colors ${
                mode === 'externe'
                  ? 'bg-white dark:bg-gray-800 text-gray-900 dark:text-white shadow-sm'
                  : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
              }`}
            >
              Offre externe
            </button>
            <button
              onClick={() => setMode('gmail')}
              className={`flex-1 px-3 py-2 text-sm font-medium rounded-md transition-colors ${
                mode === 'gmail'
                  ? 'bg-white dark:bg-gray-800 text-gray-900 dark:text-white shadow-sm'
                  : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
              }`}
            >
              Gmail
            </button>
          </div>
        </div>

        {/* Contenu scrollable */}
        <div className="px-6 pb-6 overflow-y-auto">
          {mode === 'france_travail' && (
            <FranceTravailForm onSuccess={(job) => onSuccess(job, false)} onCancel={onClose} />
          )}

          {mode === 'externe' && (
            <ExternalJobForm onSuccess={onSuccess} onCancel={onClose} />
          )}

          {mode === 'gmail' && (
            <div className="space-y-4 py-4">
              <p className="text-sm text-gray-600 dark:text-gray-400">
                Récupère les alertes emploi reçues par email (LinkedIn, APEC, France Travail, Hellowork, Talent.com) et les ajoute à ta liste d'offres.
              </p>

              {gmailResult && gmailResult.inserted === 0 && (
                <div className="rounded-lg bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 p-4 text-sm space-y-1">
                  <p className="text-gray-700 dark:text-gray-300">
                    <span className="font-medium">{gmailResult.inserted}</span> offre(s) ajoutée(s)
                  </p>
                  <p className="text-gray-500 dark:text-gray-400">
                    <span className="font-medium">{gmailResult.skipped}</span> déjà présente(s)
                  </p>
                  {gmailResult.errors > 0 && (
                    <p className="text-red-500">
                      <span className="font-medium">{gmailResult.errors}</span> erreur(s)
                    </p>
                  )}
                </div>
              )}

              {gmailError && (
                <p className="text-sm text-red-500">{gmailError}</p>
              )}

              <div className="flex justify-end gap-2">
                <button
                  onClick={onClose}
                  className="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white"
                >
                  Annuler
                </button>
                <button
                  onClick={handleGmailFetch}
                  disabled={gmailLoading}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium disabled:opacity-50 inline-flex items-center gap-2"
                >
                  {gmailLoading ? (
                    <>
                      <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                      Récupération en cours...
                    </>
                  ) : (
                    'Lancer la récupération'
                  )}
                </button>
              </div>
            </div>
          )}
        </div>

      </div>
    </div>
  );
}