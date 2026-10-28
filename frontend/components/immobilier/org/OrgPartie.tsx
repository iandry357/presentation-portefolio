'use client';

import { useState } from 'react';
import type { CubeOrg, JeuBrut } from '@/lib/immobilierOrgApi';
import { cn } from '@/lib/utils';
import OrgAnalyse from './OrgAnalyse';
import OrgBrut from './OrgBrut';

// Jeu de données téléchargeable de chaque partie (le Croisé n'a pas de tableau brut)
const JEUX_BRUTS: Partial<Record<CubeOrg, JeuBrut>> = { dvf: 'dvf', dpe: 'dpe', batiment: 'batiment' };

const VUES = [
  { id: 'analyses', libelle: 'Analyses' },
  { id: 'brut', libelle: 'Tableau brut 🔒' },
] as const;
type Vue = (typeof VUES)[number]['id'];

// Une partie du site (DVF, DPE, Bâtiment, Croisé) : ses analyses et, quand elle en a un, son tableau brut
export default function OrgPartie({ cube }: { cube: CubeOrg }) {
  const jeu = JEUX_BRUTS[cube];
  const [vue, setVue] = useState<Vue>('analyses');

  return (
    <div className="space-y-6">
      {jeu && (
        <div className="inline-flex overflow-hidden rounded border border-gray-200" role="group" aria-label="Contenu de la partie">
          {VUES.map(({ id, libelle }) => (
            <button
              key={id}
              type="button"
              onClick={() => setVue(id)}
              aria-pressed={vue === id}
              className={cn(
                'px-4 py-2 text-sm font-medium transition-colors',
                vue === id ? 'bg-blue-50 text-blue-700' : 'bg-white text-gray-600 hover:bg-gray-50',
              )}
            >
              {libelle}
            </button>
          ))}
        </div>
      )}
      {vue === 'brut' && jeu ? <OrgBrut key={jeu} jeu={jeu} /> : <OrgAnalyse key={cube} cube={cube} />}
    </div>
  );
}
