'use client';

import { cn } from '@/lib/utils';
import { ENTREES, EntreeOrg } from '@/lib/immobilierOrg';

interface Props {
  active: EntreeOrg;
  onChange: (entree: EntreeOrg) => void;
}

export default function OrgEntrees({ active, onChange }: Props) {
  const courante = ENTREES.find(e => e.id === active);

  return (
    <div className="space-y-2">
      <nav aria-label="Parties" className="overflow-x-auto">
        <div className="inline-flex min-w-full md:min-w-0 overflow-hidden rounded-lg border border-gray-200 bg-white">
          {ENTREES.map(({ id, label, icon }) => {
            const croisement = id === 'croise';   // seule entrée qui relie plusieurs jeux : séparée et colorée
            const actif = active === id;
            return (
              <button
                key={id}
                type="button"
                onClick={() => onChange(id)}
                aria-current={actif ? 'page' : undefined}
                className={cn(
                  'flex items-center gap-2 px-4 py-3 text-sm font-medium whitespace-nowrap transition-colors',
                  croisement && 'border-x border-gray-200',
                  croisement
                    ? actif ? 'bg-indigo-600 text-white' : 'bg-indigo-50 text-indigo-700 hover:bg-indigo-100'
                    : actif ? 'bg-blue-50 text-blue-700' : 'text-gray-600 hover:bg-gray-50',
                )}
              >
                <span>{icon}</span>
                <span>{label}</span>
              </button>
            );
          })}
        </div>
      </nav>
      {courante && <p className="text-sm text-gray-600">{courante.phrase}</p>}
    </div>
  );
}
