'use client';

import { cn } from '@/lib/utils';

export type SavenciaView = 'news' | 'rag' | 'ml';

export interface SavenciaFilters {
  feed_name: string;
}

interface Props {
  activeView: SavenciaView;
  onViewChange: (v: SavenciaView) => void;
  filters: SavenciaFilters;
  onFiltersChange: (f: SavenciaFilters) => void;
}

const VIEWS: { id: SavenciaView; label: string; icon: string }[] = [
  { id: 'news', label: 'Actualités',  icon: '📰' },
  { id: 'rag',  label: 'Ask AI',      icon: '🤖' },
  { id: 'ml',   label: 'ML Insights', icon: '🧠' },
];

const FEED_FILTERS = [
  { id: '',                  label: 'Tous les flux' },
  { id: 'savencia_news',     label: 'Savencia' },
  { id: 'agroalimentaire_ia', label: 'Agroalimentaire IA' },
];

export default function SavenciaSidebar({ activeView, onViewChange, filters, onFiltersChange }: Props) {
  return (
    <aside className="w-full md:w-56 shrink-0">
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

      {/* Filtre flux — uniquement sur la vue news */}
      {activeView === 'news' && (
        <div className="border rounded-lg bg-white overflow-hidden">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide px-4 py-3 border-b">
            Flux
          </p>
          <div className="p-4 space-y-2">
            {FEED_FILTERS.map(({ id, label }) => (
              <label key={id} className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="feed_name"
                  checked={filters.feed_name === id}
                  onChange={() => onFiltersChange({ feed_name: id })}
                  className="accent-blue-600"
                />
                <span className="text-sm text-gray-700">{label}</span>
              </label>
            ))}
          </div>
        </div>
      )}
    </aside>
  );
}