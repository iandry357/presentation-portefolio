'use client';

import { useState } from 'react';
import { cn } from '@/lib/utils';
import AssistantView from '../bdnb/AssistantView';
import RisquesView from '../bdnb/RisquesView';
import OrgLoyers from './OrgLoyers';

// Carte et Assistant appellent les routes publiques existantes (aucune dépendance à la période commune) : composants réutilisés.
const VUES = [
  { id: 'carte', libelle: 'Carte', phrase: 'Cliquez sur la carte : adresse, parcelle, zone d’urbanisme et risques du point choisi.' },
  { id: 'loyers', libelle: 'Loyers', phrase: 'Loyer de référence et rendement théorique, selon le quartier, la taille et l’époque du logement vendu.' },
  { id: 'assistant', libelle: 'Assistant juridique', phrase: 'Une question de bailleur ? Réponse sourcée sur les textes officiels (lois, décrets, BOFiP).' },
] as const;
type Vue = (typeof VUES)[number]['id'];

export default function OrgExploration() {
  const [vue, setVue] = useState<Vue>('carte');
  const courante = VUES.find(v => v.id === vue);

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <div className="inline-flex overflow-hidden rounded border border-gray-200" role="group" aria-label="Exploration">
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
        {courante && <p className="text-sm text-gray-600">{courante.phrase}</p>}
      </div>
      {vue === 'carte' && <RisquesView />}
      {vue === 'loyers' && <OrgLoyers />}
      {vue === 'assistant' && <AssistantView />}
    </div>
  );
}
