'use client';

import { useEffect, useState } from 'react';
import { cn } from '@/lib/utils';
import { getOrgQualite } from '@/lib/immobilierOrgApi';
import { formatPourcentage } from '@/lib/immobilier';
import OrgAnalyse from './OrgAnalyse';
import OrgPrixDpe from './OrgPrixDpe';

// Indicateurs de la partie Qualité qui donnent la part des ventes reliées à leur immeuble (pipeline/organisation/qualite.py)
const RATTACHEES = { partie: 'Croisé', indicateur: 'Ventes rattachées à un bâtiment' };
const RETENUES = { partie: 'DVF', indicateur: 'Ventes retenues dans les analyses' };

// Une analyse par question d'agent ; le nom de l'analyse vient dessous
const ANALYSES = [
  { id: 'prix', question: 'Les passoires thermiques se vendent-elles moins cher ?', nom: 'Prix et DPE' },
  { id: 'ventes', question: 'Le prix change-t-il selon l’immeuble ?', nom: 'Prix de vente et bâti' },
  { id: 'dpe', question: 'Où sont les logements énergivores ?', nom: 'Diagnostics (DPE de la BDNB)' },
] as const;
type Analyse = (typeof ANALYSES)[number]['id'];

function Etape({ titre, detail }: { titre: string; detail: string }) {
  return (
    <div className="flex-1 min-w-0 rounded-lg border border-indigo-200 bg-white px-4 py-3">
      <p className="text-sm font-medium text-gray-900">{titre}</p>
      <p className="text-xs text-gray-500 mt-0.5">{detail}</p>
    </div>
  );
}

// Le croisement des trois jeux (ventes DVF, immeubles BDNB, DPE de la BDNB). Pas de tableau brut :
// le résultat de chaque analyse s'exporte depuis son sous-onglet « Résultats ».
export default function OrgCroise() {
  const [analyse, setAnalyse] = useState<Analyse>('prix');
  const [part, setPart] = useState<number | null>(null);   // % des ventes retenues reliées à leur immeuble

  // Complément de la page : sans lui, la page reste utilisable
  useEffect(() => {
    getOrgQualite()
      .then(({ indicateurs }) => {
        const valeur = (cible: { partie: string; indicateur: string }) =>
          indicateurs.find(i => i.partie === cible.partie && i.indicateur === cible.indicateur)?.valeur ?? null;
        const rattachees = valeur(RATTACHEES);
        const retenues = valeur(RETENUES);
        if (rattachees !== null && retenues) setPart((100 * rattachees) / retenues);
      })
      .catch(() => undefined);
  }, []);

  return (
    <div className="space-y-6">
      <div className="rounded-lg border border-indigo-100 bg-indigo-50/50 p-4 space-y-3">
        <p className="text-sm font-medium text-gray-900">Comment ça marche</p>
        <div className="flex flex-col md:flex-row items-stretch gap-2">
          <Etape titre="Une vente" detail="DVF : date, prix, surface, adresse" />
          <span className="self-center text-indigo-400 md:hidden" aria-hidden>↓</span>
          <span className="self-center text-indigo-400 hidden md:block" aria-hidden>→</span>
          <Etape titre="Son immeuble" detail="BDNB : époque, copropriété, inondation, patrimoine" />
          <span className="self-center text-indigo-400 md:hidden" aria-hidden>↓</span>
          <span className="self-center text-indigo-400 hidden md:block" aria-hidden>→</span>
          <Etape titre="Ses diagnostics" detail="DPE de l’immeuble : étiquette de A à G" />
        </div>
        <p className="text-xs text-gray-600">
          {part !== null && `${formatPourcentage(part)} des ventes retenues ont été reliées à leur immeuble, par la parcelle cadastrale et l’adresse (précision : partie Qualité). `}
          La note affichée est celle de l’<strong>immeuble</strong> (note médiane des DPE de ses logements), pas celle du logement vendu.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {ANALYSES.map(({ id, question, nom }) => (
          <button
            key={id}
            type="button"
            onClick={() => setAnalyse(id)}
            aria-pressed={analyse === id}
            className={cn(
              'text-left rounded-lg border px-4 py-3 transition-colors',
              analyse === id ? 'border-indigo-500 bg-indigo-50' : 'border-gray-200 bg-white hover:bg-gray-50',
            )}
          >
            <span className="block text-sm font-medium text-gray-900">{question}</span>
            <span className="block text-xs text-indigo-700 mt-1">{nom}</span>
          </button>
        ))}
      </div>

      {analyse === 'prix' && <OrgPrixDpe />}
      {analyse === 'ventes' && <OrgAnalyse key="croise_ventes" cube="croise_ventes" />}
      {analyse === 'dpe' && <OrgAnalyse key="croise_dpe" cube="croise_dpe" />}
    </div>
  );
}
