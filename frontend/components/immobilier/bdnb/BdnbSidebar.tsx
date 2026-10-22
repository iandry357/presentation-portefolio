'use client';

import { cn } from '@/lib/utils';

export type BdnbView = 'prix' | 'parc' | 'sources';

interface Props {
  activeView: BdnbView;
  onViewChange: (v: BdnbView) => void;
}

const VIEWS: { id: BdnbView; label: string; icon: string }[] = [
  { id: 'prix', label: 'Prix et DPE', icon: '💶' },
  { id: 'parc', label: 'Profil du parc', icon: '🏢' },
  { id: 'sources', label: 'Sources et qualité', icon: '🧾' },
];

export default function BdnbSidebar({ activeView, onViewChange }: Props) {
  return (
    <aside className="w-full md:w-64 shrink-0 md:sticky md:top-[4.5rem]">
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
              activeView === id ? 'bg-blue-50 text-blue-700' : 'text-gray-600 hover:bg-gray-50',
            )}
          >
            <span>{icon}</span>
            <span className="flex-1">{label}</span>
          </button>
        ))}
      </div>
    </aside>
  );
}
