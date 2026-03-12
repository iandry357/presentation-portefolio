'use client';

import { useState, useEffect, useRef } from 'react';
import { Building2, Sparkles } from 'lucide-react';
import { CompanyProfile } from '@/types';
import { getCompany, generateCompany } from '@/lib/api';
import CompanyDetail, { hasPending } from '@/components/jobs/CompanyDetail';

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

// ============================================================================
// Props
// ============================================================================

interface CompanySectionProps {
  jobId: number;
  companyName: string | null;
  companyProfileId: number | null;
  companyDescription: string | null;
  onProfileCreated: (id: number) => void;
}

// ============================================================================
// Composant
// ============================================================================

export default function CompanySection({ jobId, companyName, companyProfileId, companyDescription, onProfileCreated  }: CompanySectionProps) {
  const [profile, setProfile] = useState<CompanyProfile | null>(null);
  const [nameInput, setNameInput] = useState('');
  const [generating, setGenerating] = useState(false);
  // const [refreshing, setRefreshing] = useState(false);
  // const [recalculating, setRecalculating] = useState(false);
  // const [recalculInstruction, setRecalculInstruction] = useState('');
  const [error, setError] = useState<string | null>(null);

  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ── Polling ──────────────────────────────────────────────────────────────

  const stopPolling = () => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  };

  const startPolling = (id: number) => {
    stopPolling();
    pollingRef.current = setInterval(async () => {
      try {
        const updated = await getCompany(id);
        setProfile(updated);
        if (!hasPending(updated)) stopPolling();
      } catch {
        stopPolling();
      }
    }, 5000);
  };

  // ── Chargement initial ───────────────────────────────────────────────────

  useEffect(() => {
    if (!companyProfileId) return;
    getCompany(companyProfileId)
      .then(p => {
        setProfile(p);
        if (hasPending(p)) startPolling(p.id);
      })
      .catch(() => setError('Impossible de charger la fiche entreprise.'));

    return () => stopPolling();
  }, [companyProfileId]);

  // ── Actions ──────────────────────────────────────────────────────────────

  const handleGenerate = async () => {
    setGenerating(true);
    setError(null);
    try {
      const name = (companyName ?? nameInput.trim()) || undefined;
      const response = await generateCompany(jobId, name);
      const created = await getCompany(response.company_profile_id);
      setProfile(created);
      onProfileCreated(created.id);
      if (hasPending(created)) startPolling(created.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erreur lors de la génération.');
    } finally {
      setGenerating(false);
    }
  };

  // const handleRefresh = async () => {
  //   if (!profile) return;
  //   setRefreshing(true);
  //   setError(null);
  //   try {
  //     await refreshCompany(profile.id);
  //     const updated = await getCompany(profile.id);
  //     setProfile(updated);
  //     if (hasPending(updated)) startPolling(updated.id);
  //   } catch (e) {
  //     setError(e instanceof Error ? e.message : 'Erreur lors de l\'actualisation.');
  //   } finally {
  //     setRefreshing(false);
  //   }
  // };

  // const handleRecalcul = async () => {
  //   if (!profile) return;
  //   setRecalculating(true);
  //   setError(null);
  //   try {
  //     await recalculCompany(profile.id, recalculInstruction.trim() || undefined);
  //     const updated = await getCompany(profile.id);
  //     setProfile(updated);
  //     setRecalculInstruction('');
  //     if (hasPending(updated)) startPolling(updated.id);
  //   } catch (e) {
  //     setError(e instanceof Error ? e.message : 'Erreur lors du recalcul.');
  //   } finally {
  //     setRecalculating(false);
  //   }
  // };

  // const isPending = profile ? hasPending(profile) : false;
  // const canRecalcul = profile ? profile.recalcul_count < 3 : false;

  // ============================================================================
  // Rendu
  // ============================================================================

  // ── Cas A — pas de company_name, pas de profil ───────────────────────────
  if (!companyName && !profile) {
    return (
      <div className="space-y-4 pt-4">
        <p className="text-sm text-gray-500 dark:text-gray-400">
          {companyDescription
            ? `"${companyDescription.slice(0, 100)}…" — L'entreprise n'a pas été extraite, veuillez saisir son nom pour générer la fiche.`
            : "L'entreprise n'a pas été extraite, veuillez saisir son nom si disponible pour générer la fiche."
          }
        </p>
        <div className="flex gap-2">
          <input
            type="text"
            value={nameInput}
            onChange={e => setNameInput(e.target.value)}
            placeholder="Nom de l'entreprise"
            className="flex-1 text-sm border border-gray-200 dark:border-gray-700 rounded-lg px-3 py-2 bg-white dark:bg-gray-800 text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-gray-300 dark:focus:ring-gray-600"
          />
          <button
            onClick={handleGenerate}
            disabled={generating || !nameInput.trim()}
            className="inline-flex items-center gap-2 px-4 py-2 bg-gray-900 dark:bg-white text-white dark:text-gray-900 rounded-lg text-sm font-medium hover:bg-gray-800 dark:hover:bg-gray-100 transition-colors disabled:opacity-50"
          >
            {generating ? <>Génération<AnimatedDots /></> : 'Générer'}
          </button>
        </div>
        {error && <p className="text-sm text-red-500 dark:text-red-400">{error}</p>}
      </div>
    );
  }

  // ── Cas B — company_name connu, pas de profil ────────────────────────────
  if (!profile) {
    return (
      <div className="space-y-4 pt-4">
        <div className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
          <Building2 className="w-4 h-4" />
          <span className="font-medium text-gray-900 dark:text-white">{companyName}</span>
        </div>
        <p className="text-sm text-gray-500 dark:text-gray-400">
          Aucune fiche entreprise générée pour le moment.
        </p>
        <button
          onClick={handleGenerate}
          disabled={generating}
          className="inline-flex items-center gap-2 px-4 py-2 bg-gray-900 dark:bg-white text-white dark:text-gray-900 rounded-lg text-sm font-medium hover:bg-gray-800 dark:hover:bg-gray-100 transition-colors disabled:opacity-50"
        >
          <Sparkles className="w-4 h-4" />
          {generating ? <>Génération<AnimatedDots /></> : 'Générer la fiche'}
        </button>
        {error && <p className="text-sm text-red-500 dark:text-red-400">{error}</p>}
      </div>
    );
  }

  // ── Cas C — profil existant ──────────────────────────────────────────────
  return (
    <div className="pt-4">
      <CompanyDetail profile={profile} onProfileUpdate={setProfile} />
    </div>
  );
}