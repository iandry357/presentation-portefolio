 
'use client';

import { useState } from 'react';
import { addManualJob } from '@/lib/api';
import { JobOfferDetail } from '@/types';

interface FranceTravailFormProps {
  onSuccess: (job: JobOfferDetail) => void;
  onCancel: () => void;
}

export default function FranceTravailForm({ onSuccess, onCancel }: FranceTravailFormProps) {
  const [ftId, setFtId] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    if (!ftId.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const job = await addManualJob(ftId.trim());
      onSuccess(job);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erreur ajout manuel');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <label className="text-sm text-gray-600 dark:text-gray-400">
          Numéro de l'offre France Travail
        </label>
        <input
          type="text"
          value={ftId}
          onChange={e => setFtId(e.target.value)}
          placeholder="ex: 9548593"
          className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
        />
      </div>

      {error && (
        <p className="text-sm text-red-500">{error}</p>
      )}

      <div className="flex justify-end gap-2 pt-2">
        <button
          onClick={onCancel}
          className="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white"
        >
          Annuler
        </button>
        <button
          onClick={handleSubmit}
          disabled={loading || !ftId.trim()}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium disabled:opacity-50"
        >
          {loading ? 'Ajout en cours...' : 'Ajouter'}
        </button>
      </div>
    </div>
  );
}