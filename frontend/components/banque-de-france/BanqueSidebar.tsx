'use client';

import { cn } from '@/lib/utils';

export type BanqueView = 'news' | 'rag' | 'ml';

interface Props {
  activeView: BanqueView;
  onViewChange: (v: BanqueView) => void;
}

const VIEWS: { id: BanqueView; label: string; icon: string }[] = [
  { id: 'news', label: 'Actualités',  icon: '📰' },
  { id: 'rag',  label: 'Ask AI',      icon: '🤖' },
  { id: 'ml',   label: 'ML Insights', icon: '🧠' },
];

export default function BanqueSidebar({ activeView, onViewChange }: Props) {
  return (
    <aside className="w-full md:w-64 shrink-0">
      <div className="border rounded-lg bg-white overflow-hidden">
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
    </aside>
  );
}