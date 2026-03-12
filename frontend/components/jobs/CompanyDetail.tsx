'use client';

import { useState } from 'react';
import { Building2, RefreshCw, Sparkles } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { CompanyProfile } from '@/types';
import { refreshCompany, recalculCompany, getCompany, relaunchCompany } from '@/lib/api';

// ============================================================================
// Helpers
// ============================================================================

function AnimatedDots() {
  return (
    <span className="inline-flex gap-0.5">
      <span className="animate-bounce [animation-delay:0ms]">.</span>
      <span className="animate-bounce [animation-delay:150ms]">.</span>
      <span className="animate-bounce [animation-delay:300ms]">.</span>
    </span>
  );
}

export function hasPending(profile: CompanyProfile): boolean {
  return (
    profile.discovery_status === 'pending' ||
    profile.legal_status === 'pending' ||
    profile.actualites_status === 'pending' ||
    profile.memo_status === 'pending'
  );
}

// ============================================================================
// Props
// ============================================================================

interface CompanyDetailProps {
  profile: CompanyProfile;
  onProfileUpdate: (updated: CompanyProfile) => void;
}

// ============================================================================
// Composant
// ============================================================================

export default function CompanyDetail({ profile, onProfileUpdate }: CompanyDetailProps) {
  const [refreshing, setRefreshing] = useState(false);
  const [recalculating, setRecalculating] = useState(false);
  const [recalculInstruction, setRecalculInstruction] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [relaunching, setRelaunching] = useState(false);

  const isPending = hasPending(profile);
  const canRecalcul = profile.recalcul_count < 3;

  // ── Actions ──────────────────────────────────────────────────────────────

  const handleRefresh = async () => {
    setRefreshing(true);
    setError(null);
    try {
      await refreshCompany(profile.id);
      const updated = await getCompany(profile.id);
      onProfileUpdate(updated);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erreur lors de l'actualisation.");
    } finally {
      setRefreshing(false);
    }
  };

  const handleRecalcul = async () => {
    setRecalculating(true);
    setError(null);
    try {
      await recalculCompany(profile.id, recalculInstruction.trim() || undefined);
      const updated = await getCompany(profile.id);
      onProfileUpdate(updated);
      setRecalculInstruction('');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erreur lors du recalcul.');
    } finally {
      setRecalculating(false);
    }
  };

  const handleRelaunch = async () => {
    setRelaunching(true);
    setError(null);
    try {
      await relaunchCompany(profile.id);
      const updated = await getCompany(profile.id);
      onProfileUpdate(updated);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erreur lors de la relance.');
    } finally {
      setRelaunching(false);
    }
  };

  // ============================================================================
  // Rendu
  // ============================================================================

  return (
    <div className="space-y-6">

      {/* Nom + statut global */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm">
          <Building2 className="w-4 h-4 text-gray-500 dark:text-gray-400" />
          <span className="font-medium text-gray-900 dark:text-white">{profile.name}</span>
        </div>
        {isPending && (
          <span className="text-xs text-blue-500 dark:text-blue-400 flex items-center gap-1">
            <RefreshCw className="w-3 h-3 animate-spin" />
            Analyse en cours<AnimatedDots />
          </span>
        )}
      </div>

      {/* Mémo */}
      {profile.memo_status === 'done' && profile.memo ? (
        <div className="prose prose-sm dark:prose-invert max-w-none break-words overflow-hidden">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{profile.memo}</ReactMarkdown>
        </div>
      ) : profile.memo_status === 'failed' ? (
        <p className="text-sm text-red-500 dark:text-red-400">La génération du mémo a échoué.</p>
      ) : (
        <p className="text-sm text-gray-500 dark:text-gray-400 italic">Mémo en cours de génération…</p>
      )}

      {error && <p className="text-sm text-red-500 dark:text-red-400">{error}</p>}

      {/* Actions */}
      <div className="space-y-4 border-t border-gray-100 dark:border-gray-700 pt-4">

        {profile.discovery_status === 'failed' && (
          <button
            onClick={handleRelaunch}
            disabled={relaunching || isPending}
            className="inline-flex items-center gap-2 px-3 py-1.5 border border-red-200 dark:border-red-800 text-red-600 dark:text-red-400 rounded-lg text-sm hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${relaunching ? 'animate-spin' : ''}`} />
            {relaunching ? <>Relance<AnimatedDots /></> : 'Relancer la génération'}
          </button>
        )}

        {/* Actualiser */}
        <button
          onClick={handleRefresh}
          disabled={refreshing || isPending}
          className="inline-flex items-center gap-2 px-3 py-1.5 border border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-300 rounded-lg text-sm hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
          {refreshing ? <>Actualisation<AnimatedDots /></> : 'Actualiser les infos'}
        </button>

        {/* Regénérer le mémo */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <p className="text-xs font-medium text-gray-500 dark:text-gray-400">Regénérer le mémo</p>
            <span className="text-xs text-gray-400 dark:text-gray-500">
              {3 - profile.recalcul_count} recalcul{(3 - profile.recalcul_count) > 1 ? 's' : ''} restant{(3 - profile.recalcul_count) > 1 ? 's' : ''}
            </span>
          </div>
          <textarea
            value={recalculInstruction}
            onChange={e => setRecalculInstruction(e.target.value)}
            placeholder="Instruction optionnelle (ex : insiste sur la culture d'entreprise)"
            disabled={!canRecalcul || recalculating || isPending}
            rows={2}
            className="w-full text-sm border border-gray-200 dark:border-gray-700 rounded-lg px-3 py-2 bg-white dark:bg-gray-800 text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-gray-300 dark:focus:ring-gray-600 disabled:opacity-50 resize-none"
          />
          <button
            onClick={handleRecalcul}
            disabled={!canRecalcul || recalculating || isPending}
            className="inline-flex items-center gap-2 px-3 py-1.5 bg-gray-900 dark:bg-white text-white dark:text-gray-900 rounded-lg text-sm font-medium hover:bg-gray-800 dark:hover:bg-gray-100 transition-colors disabled:opacity-50"
          >
            <Sparkles className="w-3.5 h-3.5" />
            {recalculating
              ? <>Recalcul<AnimatedDots /></>
              : !canRecalcul
              ? 'Quota atteint'
              : 'Regénérer le mémo'}
          </button>
        </div>

      </div>
    </div>
  );
}