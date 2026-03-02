'use client';

import { JobFilters } from '@/types';

// ============================================================================
// Options filtres
// ============================================================================

const CONTRACT_TYPES = [
  { value: '', label: 'Tous les contrats' },
  { value: 'CDI', label: 'CDI' },
  { value: 'CDD', label: 'CDD' },
  { value: 'MIS', label: 'Intérim' },
  { value: 'LIB', label: 'Indépendant' },
];

const STATUSES = [
  { value: '', label: 'Tous les statuts' },
  { value: 'nouveau', label: 'Nouveau' },
  { value: 'existant', label: 'Existant' },
  { value: 'ferme', label: 'Fermé' },
  { value: 'consulte', label: 'Consulté' },
  { value: 'postule', label: 'Postulé' },
];

const MAX_DAYS_OPTIONS = [
  { value: '', label: 'Toutes les dates' },
  { value: '3', label: 'Moins de 3 jours' },
  { value: '7', label: 'Moins de 7 jours' },
  { value: '14', label: 'Moins de 14 jours' },
  { value: '30', label: 'Moins de 30 jours' },
];

// ============================================================================
// JobFilters component
// ============================================================================

interface JobFiltersProps {
  filters: JobFilters;
  onChange: (filters: JobFilters) => void;
}

export default function JobFiltersPanel({ filters, onChange }: JobFiltersProps) {
  const update = (patch: Partial<JobFilters>) =>
    onChange({ ...filters, page: 1, ...patch });

  return (
    <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4 space-y-4">
      <h2 className="text-sm font-semibold text-gray-900 dark:text-white">Filtres</h2>

      {/* Type de contrat */}
      <div className="space-y-1">
        <label className="text-xs text-gray-500 dark:text-gray-400">Type de contrat</label>
        <select
          value={filters.contract_type ?? ''}
          onChange={e => update({ contract_type: e.target.value || undefined })}
          className="w-full text-sm bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded px-3 py-1.5 text-gray-900 dark:text-white"
        >
          {CONTRACT_TYPES.map(o => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
      </div>

      {/* Statut */}
      <div className="space-y-1">
        <label className="text-xs text-gray-500 dark:text-gray-400">Statut</label>
        <select
          value={filters.status ?? ''}
          onChange={e => update({ status: e.target.value || undefined })}
          className="w-full text-sm bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded px-3 py-1.5 text-gray-900 dark:text-white"
        >
          {STATUSES.map(o => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
      </div>

      {/* Code postal */}
      <div className="space-y-1">
        <label className="text-xs text-gray-500 dark:text-gray-400">Code postal</label>
        <input
          type="text"
          placeholder="ex: 75001"
          value={filters.postal_code ?? ''}
          onChange={e => update({ postal_code: e.target.value || undefined })}
          maxLength={5}
          className="w-full text-sm bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded px-3 py-1.5 text-gray-900 dark:text-white placeholder-gray-400"
        />
      </div>

      {/* Ancienneté */}
      <div className="space-y-1">
        <label className="text-xs text-gray-500 dark:text-gray-400">Ancienneté de l'offre</label>
        <select
          value={filters.max_days_old ?? ''}
          onChange={e => update({ max_days_old: e.target.value ? Number(e.target.value) : undefined })}
          className="w-full text-sm bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded px-3 py-1.5 text-gray-900 dark:text-white"
        >
          {MAX_DAYS_OPTIONS.map(o => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
      </div>

      {/* Masquer consultées */}
      <div className="flex items-center gap-2 pt-1">
        <input
          type="checkbox"
          id="hide_consulted"
          checked={filters.hide_consulted}
          onChange={e => update({ hide_consulted: e.target.checked })}
          className="w-4 h-4 rounded border-gray-300 dark:border-gray-600"
        />
        <label htmlFor="hide_consulted" className="text-sm text-gray-700 dark:text-gray-300 cursor-pointer">
          Masquer les consultées
        </label>
      </div>

      {/* Reset */}
      <button
        onClick={() => onChange({
          page: 1,
          page_size: filters.page_size,
          hide_consulted: false,
        })}
        className="w-full text-xs text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 transition-colors pt-1"
      >
        Réinitialiser les filtres
      </button>
    </div>
  );
}