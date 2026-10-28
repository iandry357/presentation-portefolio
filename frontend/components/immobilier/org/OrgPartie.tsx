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

// Ce que chaque partie n'utilise pas, et la question qu'elle laisse au Croisement
const RAPPEL: Partial<Record<CubeOrg, { seul: string; question: string }>> = {
  dvf: { seul: 'les ventes', question: 'Le prix change-t-il selon la note énergétique ou l’âge de l’immeuble ?' },
  dpe: { seul: 'les diagnostics de l’ADEME', question: 'Les logements énergivores se vendent-ils moins cher ?' },
  batiment: { seul: 'les immeubles', question: 'Comment le prix des ventes varie-t-il selon l’immeuble ?' },
};

interface Props {
  cube: CubeOrg;
  onCroisement: () => void;   // ouvre l'entrée Croisement
}

// Une partie du site (Ventes, Diagnostics, Immeubles) : ses analyses et, quand elle en a un, son tableau brut
export default function OrgPartie({ cube, onCroisement }: Props) {
  const jeu = JEUX_BRUTS[cube];
  const rappel = RAPPEL[cube];
  const [vue, setVue] = useState<Vue>('analyses');

  return (
    <div className="space-y-6">
      {rappel && (
        <p className="text-sm text-gray-600 bg-indigo-50 border border-indigo-100 rounded-lg px-4 py-3">
          Cette partie n’utilise que {rappel.seul}. {rappel.question}{' '}
          <button type="button" onClick={onCroisement} className="font-medium text-indigo-700 hover:underline">
            Voir le Croisement
          </button>
        </p>
      )}
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
