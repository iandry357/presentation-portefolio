 
'use client';

import { useState } from 'react';
import { JobOfferDetail } from '@/types';
import FranceTravailForm from './FranceTravailForm';
import ExternalJobForm from './ExternalJobForm';

type Mode = 'france_travail' | 'externe';

interface AddJobModalProps {
  onSuccess: (job: JobOfferDetail, triggerEnrichment: boolean) => void;
  onClose: () => void;
}

export default function AddJobModal({ onSuccess, onClose }: AddJobModalProps) {
  const [mode, setMode] = useState<Mode>('france_travail');

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-gray-800 rounded-lg w-full max-w-lg shadow-xl flex flex-col max-h-[90vh]">

        {/* Header */}
        <div className="p-6 pb-4 shrink-0">
          <h2 className="text-base font-semibold text-gray-900 dark:text-white mb-4">
            Ajouter une offre
          </h2>

          {/* Toggle */}
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
          </div>
        </div>

        {/* Contenu scrollable */}
        <div className="px-6 pb-6 overflow-y-auto">
          {mode === 'france_travail' ? (
            <FranceTravailForm onSuccess={(job) => onSuccess(job, false)} onCancel={onClose} />
          ) : (
            <ExternalJobForm onSuccess={onSuccess} onCancel={onClose} />
          )}
        </div>

      </div>
    </div>
  );
}