'use client';

import { useState } from 'react';
import { RefreshCw } from 'lucide-react';
import { JobEnriched } from '@/types';
import { recalculJob } from '@/lib/api';

interface RecalculButtonProps {
  jobId: number;
  recalculCount: number;
  recalculRemaining: number;
  onRecalcul: (enriched: JobEnriched) => void;
}

export default function RecalculButton({
  jobId,
  recalculCount,
  recalculRemaining,
  onRecalcul,
}: RecalculButtonProps) {
  const [instruction, setInstruction] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isDisabled = recalculRemaining === 0;

  const handleRecalcul = async () => {
    if (!instruction.trim() || isDisabled) return;
    setLoading(true);
    setError(null);
    try {
      const result = await recalculJob(jobId, instruction.trim());
      onRecalcul(result);
      setInstruction('');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erreur recalcul');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="border-t border-gray-100 dark:border-gray-700 pt-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-900 dark:text-white">
          Recalculer la fiche
        </h3>
        <span className={`text-xs ${isDisabled ? 'text-red-500 dark:text-red-400' : 'text-gray-400 dark:text-gray-500'}`}>
          {recalculRemaining} recalcul{recalculRemaining > 1 ? 's' : ''} restant{recalculRemaining > 1 ? 's' : ''}
        </span>
      </div>

      {isDisabled ? (
        <p className="text-sm text-gray-500 dark:text-gray-400 bg-gray-50 dark:bg-gray-700 px-3 py-2 rounded">
          Limite de 3 recalculs atteinte pour cette offre.
        </p>
      ) : (
        <div className="space-y-2">
          <textarea
            value={instruction}
            onChange={e => setInstruction(e.target.value)}
            placeholder="Ex: Détaille davantage les attentes techniques, reformule les conditions..."
            rows={2}
            maxLength={500}
            disabled={loading}
            className="w-full text-sm bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded px-3 py-2 text-gray-900 dark:text-white placeholder-gray-400 resize-none focus:outline-none focus:ring-1 focus:ring-gray-400 disabled:opacity-50"
          />
          <div className="flex items-center justify-between">
            <span className="text-xs text-gray-400">{instruction.length}/500</span>
            <button
              onClick={handleRecalcul}
              disabled={loading || !instruction.trim()}
              className="inline-flex items-center gap-2 px-4 py-1.5 bg-gray-900 dark:bg-white text-white dark:text-gray-900 rounded text-sm font-medium hover:bg-gray-800 dark:hover:bg-gray-100 transition-colors disabled:opacity-50"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
              {loading ? 'Recalcul...' : 'Recalculer'}
            </button>
          </div>
          {error && (
            <p className="text-xs text-red-500 dark:text-red-400">{error}</p>
          )}
        </div>
      )}

      {/* Historique */}
      {recalculCount > 0 && (
        <p className="text-xs text-gray-400 dark:text-gray-500">
          {recalculCount} recalcul{recalculCount > 1 ? 's' : ''} effectué{recalculCount > 1 ? 's' : ''}
        </p>
      )}
    </div>
  );
}