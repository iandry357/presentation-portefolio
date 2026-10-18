'use client';

import { Lock } from 'lucide-react';
import { cn } from '@/lib/utils';

export type TopView = 'overview' | 'top' | 'entreprises' | 'brouillons';

interface Props {
  activeView: TopView;
  onViewChange: (v: TopView) => void;
  unlocked: boolean;
}

const VIEWS: { id: TopView; label: string; icon: string; prive: boolean }[] = [
  { id: 'overview', label: "Vue d'ensemble", icon: '📊', prive: false },
  { id: 'top', label: 'Top du jour', icon: '⭐', prive: true },
  { id: 'entreprises', label: 'Entreprises', icon: '🏢', prive: true },
  { id: 'brouillons', label: 'Brouillons', icon: '📝', prive: true },
];

export default function TopSidebar({ activeView, onViewChange, unlocked }: Props) {
  return (
    <aside className="w-full md:w-64 shrink-0">
      <div className="border rounded-lg bg-white overflow-hidden">
        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide px-4 py-3 border-b">
          Vue
        </p>
        {VIEWS.map(({ id, label, icon, prive }) => {
          const verrouille = prive && !unlocked;
          return (
            <button
              key={id}
              onClick={() => onViewChange(id)}
              disabled={verrouille}
              title={verrouille ? 'Zone privée : déverrouillez avec le bouton en haut de la page' : undefined}
              className={cn(
                'w-full flex items-center gap-3 px-4 py-3 text-sm font-medium transition-colors text-left',
                activeView === id && !verrouille
                  ? 'bg-blue-50 text-blue-700'
                  : 'text-gray-600 hover:bg-gray-50',
                verrouille && 'text-gray-400 cursor-not-allowed hover:bg-transparent',
              )}
            >
              <span>{icon}</span>
              <span className="flex-1">{label}</span>
              {verrouille && <Lock className="w-3.5 h-3.5" />}
            </button>
          );
        })}
      </div>
    </aside>
  );
}
