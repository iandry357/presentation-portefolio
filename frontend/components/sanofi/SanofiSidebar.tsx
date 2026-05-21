'use client';

import { cn } from '@/lib/utils';

// export type SanofiView = 'clinical-trials' | 'pubmed' | 'news' | 'rag';
// export type SanofiView = 'clinical-trials' | 'pubmed' | 'news' | 'rag' | 'ml';
export type SanofiView = 'clinical-trials' | 'pubmed' | 'news' | 'press-releases' | 'rag' | 'ml';

interface FiltersClinical {
  phase: string;
  status: string;
}

interface FiltersRag {
  sources: string[];
}

export interface SanofiFilters {
  clinical: FiltersClinical;
  rag: FiltersRag;
}

interface Props {
  activeView: SanofiView;
  onViewChange: (v: SanofiView) => void;
  filters: SanofiFilters;
  onFiltersChange: (f: SanofiFilters) => void;
}

const VIEWS: { id: SanofiView; label: string; icon: string }[] = [
  { id: 'clinical-trials', label: 'Essais Cliniques', icon: '🔬' },
  { id: 'pubmed',          label: 'Publications R&D', icon: '📄' },
  { id: 'news',            label: 'Actualités',       icon: '📰' },
  { id: 'press-releases',  label: 'Press Releases',   icon: '📢' },
  { id: 'rag',             label: 'Ask AI',           icon: '🤖' },
  { id: 'ml',              label: 'ML Insights',      icon: '🧠' },
];

const PHASES = ['', 'PHASE1', 'PHASE2', 'PHASE3', 'PHASE4'];
const STATUSES = ['', 'RECRUITING', 'COMPLETED', 'ACTIVE_NOT_RECRUITING', 'NOT_YET_RECRUITING', 'TERMINATED'];
const RAG_SOURCES = [
  { id: 'clinicaltrials', label: 'Essais cliniques' },
  { id: 'pubmed',         label: 'Publications' },
  { id: 'google_news',    label: 'Actualités' },
];

export default function SanofiSidebar({ activeView, onViewChange, filters, onFiltersChange }: Props) {
  const updateClinical = (key: keyof FiltersClinical, val: string) =>
    onFiltersChange({ ...filters, clinical: { ...filters.clinical, [key]: val } });

  const toggleRagSource = (src: string) => {
    const current = filters.rag.sources;
    const next = current.includes(src) ? current.filter(s => s !== src) : [...current, src];
    onFiltersChange({ ...filters, rag: { sources: next } });
  };

  return (
    // <aside className="w-64 shrink-0">
    <aside className="w-full md:w-64 shrink-0">
      {/* Sélecteur de vue */}
      <div className="border rounded-lg bg-white mb-4 overflow-hidden">
        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide px-4 py-3 border-b">
          Vue
        </p>
        {VIEWS.map(({ id, label, icon }) => (
          <button
            key={id}
            onClick={() => onViewChange(id)}
            className={cn(
              'w-full flex items-center gap-3 px-4 py-3 text-sm font-medium transition-colors text-left',
              activeView === id
                ? 'bg-blue-50 text-blue-700'
                : 'text-gray-600 hover:bg-gray-50'
            )}
          >
            <span>{icon}</span>
            <span>{label}</span>
          </button>
        ))}
      </div>

      {/* Filtres contextuels */}
      {activeView === 'clinical-trials' && (
        <div className="border rounded-lg bg-white overflow-hidden">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide px-4 py-3 border-b">
            Filtres
          </p>
          <div className="p-4 space-y-4">
            <div>
              <label className="block text-xs text-gray-500 mb-1">Phase</label>
              <select
                value={filters.clinical.phase}
                onChange={e => updateClinical('phase', e.target.value)}
                className="w-full border rounded px-2 py-1.5 text-sm text-gray-700"
              >
                <option value="">Toutes</option>
                {PHASES.filter(Boolean).map(p => (
                  <option key={p} value={p}>{p}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Statut</label>
              <select
                value={filters.clinical.status}
                onChange={e => updateClinical('status', e.target.value)}
                className="w-full border rounded px-2 py-1.5 text-sm text-gray-700"
              >
                <option value="">Tous</option>
                {STATUSES.filter(Boolean).map(s => (
                  <option key={s} value={s}>{s.replace(/_/g, ' ')}</option>
                ))}
              </select>
            </div>
          </div>
        </div>
      )}

      {activeView === 'rag' && (
        <div className="border rounded-lg bg-white overflow-hidden">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide px-4 py-3 border-b">
            Sources RAG
          </p>
          <div className="p-4 space-y-2">
            {RAG_SOURCES.map(({ id, label }) => (
              <label key={id} className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={filters.rag.sources.length === 0 || filters.rag.sources.includes(id)}
                  onChange={() => toggleRagSource(id)}
                  className="rounded"
                />
                <span className="text-sm text-gray-700">{label}</span>
              </label>
            ))}
            <p className="text-xs text-gray-400 pt-1">
              {filters.rag.sources.length === 0 ? 'Toutes les sources actives' : `${filters.rag.sources.length} source(s) sélectionnée(s)`}
            </p>
          </div>
        </div>
      )}
    </aside>
  );
}