'use client';

import { cn } from '@/lib/utils';

export type SgView = 'news' | 'rag' | 'ml' | 'qwen';

interface Props {
  activeView: SgView;
  onViewChange: (v: SgView) => void;
}

const VIEWS: { id: SgView; label: string; icon: string }[] = [
  { id: 'news', label: 'Actualités',   icon: '📰' },
  { id: 'rag',  label: 'Ask AI',       icon: '🤖' },
  { id: 'ml',   label: 'ML Insights',  icon: '🧠' },
  { id: 'qwen', label: 'Qwen Demo',    icon: '✨' },
];

export default function SgSidebar({ activeView, onViewChange }: Props) {
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