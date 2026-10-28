'use client';

import { cn } from '@/lib/utils';
import { ENTREES, EntreeOrg } from '@/lib/immobilierOrg';

interface Props {
  active: EntreeOrg;
  onChange: (entree: EntreeOrg) => void;
}

export default function OrgEntrees({ active, onChange }: Props) {
  return (
    <nav aria-label="Parties" className="overflow-x-auto">
      <div className="inline-flex min-w-full md:min-w-0 overflow-hidden rounded-lg border border-gray-200 bg-white">
        {ENTREES.map(({ id, label, icon }) => (
          <button
            key={id}
            type="button"
            onClick={() => onChange(id)}
            aria-current={active === id ? 'page' : undefined}
            className={cn(
              'flex items-center gap-2 px-4 py-3 text-sm font-medium whitespace-nowrap transition-colors',
              active === id ? 'bg-blue-50 text-blue-700' : 'text-gray-600 hover:bg-gray-50',
            )}
          >
            <span>{icon}</span>
            <span>{label}</span>
          </button>
        ))}
      </div>
    </nav>
  );
}
