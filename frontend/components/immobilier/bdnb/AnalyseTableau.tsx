'use client';

import { cn } from '@/lib/utils';
import type { AnalyseCellule, DimensionAnalyse, SourceAnalyse } from '@/lib/immobilierBdnbApi';
import { estVentes, libelleDimension, libelleModalite, minuscule } from '@/lib/immobilierBdnb';
import { SEUIL_VENTES_FIABLES } from '@/lib/immobilierBdnbTextes';
import { formatEntier, formatPourcentage } from '@/lib/immobilier';

interface Props {
  source: SourceAnalyse;
  axes: [DimensionAnalyse, DimensionAnalyse];
  cellules: AnalyseCellule[];
  lignes: string[];      // modalités du 1er axe, dans l'ordre d'affichage (meta.modalites)
  colonnes: string[];    // modalités du 2e axe, dans l'ordre d'affichage
}

const cle = (ligne: string, colonne: string) => `${ligne}\u0000${colonne}`;

function Cellule({ cellule, source }: { cellule: AnalyseCellule | undefined; source: SourceAnalyse }) {
  // Pas de cellule : groupe masqué (accès verrouillé) ou combinaison sans observation
  if (!cellule) return <span className="text-gray-300">–</span>;
  const ventes = estVentes(source);
  const valeur = ventes ? cellule.mediane : cellule.part_pct;
  const fragile = ventes && cellule.n < SEUIL_VENTES_FIABLES;
  return (
    <div className={cn(fragile && 'text-gray-400')}>
      <div className="font-medium">
        {valeur === null ? '–' : ventes ? formatEntier(valeur) : formatPourcentage(valeur)}
      </div>
      <div className="text-xs text-gray-400">{formatEntier(cellule.n)} {ventes ? 'ventes' : 'DPE'}</div>
    </div>
  );
}

export default function AnalyseTableau({ source, axes, cellules, lignes, colonnes }: Props) {
  if (cellules.length === 0) {
    return <p className="text-sm text-gray-400 py-8 text-center">Aucune donnée pour ce filtre.</p>;
  }

  const parCle = new Map(cellules.map(c => [cle(c.modalites[0], c.modalites[1]), c]));
  const lignesVues = new Set(cellules.map(c => c.modalites[0]));
  const colonnesVues = new Set(cellules.map(c => c.modalites[1]));
  const lignesAffichees = lignes.filter(l => lignesVues.has(l));
  const colonnesAffichees = colonnes.filter(k => colonnesVues.has(k));

  return (
    <div>
      <p className="text-xs text-gray-500 mb-1">
        Lignes : {minuscule(libelleDimension(axes[0], source))} · Colonnes : {minuscule(libelleDimension(axes[1], source))}
      </p>
      <p className="text-xs text-gray-600 mb-2">
        {estVentes(source)
          ? `Dans chaque case : le prix médian au m², puis le nombre de ventes. En gris : moins de ${SEUIL_VENTES_FIABLES} ventes, à lire avec prudence. Le total est le nombre de ventes de la ligne. « – » : aucune vente, ou trop peu pour être affichée tant que l’accès est verrouillé.`
          : 'Dans chaque case : la part de la ligne (en %), puis le nombre de DPE. Le total est le nombre de DPE de la ligne. « – » : aucun DPE, ou trop peu pour être affiché tant que l’accès est verrouillé.'}
      </p>

      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-gray-500 border-b">
              <th className="sticky left-0 bg-white py-1.5 pr-3 font-medium" />
              {colonnesAffichees.map(colonne => (
                <th key={colonne} className="py-1.5 px-3 font-medium text-right whitespace-nowrap">
                  {libelleModalite(axes[1], colonne)}
                </th>
              ))}
              <th className="py-1.5 px-3 font-medium text-right whitespace-nowrap">Total</th>
            </tr>
          </thead>
          <tbody>
            {lignesAffichees.map(ligne => (
              <tr key={ligne} className="border-b last:border-0">
                <th className="sticky left-0 bg-white py-1.5 pr-3 text-left font-medium text-gray-700 whitespace-nowrap">
                  {libelleModalite(axes[0], ligne)}
                </th>
                {colonnesAffichees.map(colonne => (
                  <td key={colonne} className="py-1.5 px-3 text-right tabular-nums text-gray-700 whitespace-nowrap">
                    <Cellule cellule={parCle.get(cle(ligne, colonne))} source={source} />
                  </td>
                ))}
                <td className="py-1.5 pl-3 text-right tabular-nums text-gray-700 whitespace-nowrap border-l">
                  <div className="font-medium">
                    {formatEntier(colonnesAffichees.reduce((somme, colonne) => somme + (parCle.get(cle(ligne, colonne))?.n ?? 0), 0))}
                  </div>
                  <div className="text-xs text-gray-400">{estVentes(source) ? 'ventes' : 'DPE'}</div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
