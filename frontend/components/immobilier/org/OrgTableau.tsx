'use client';

import { cn } from '@/lib/utils';
import type { CubeOrg, OrgAnalyseCellule } from '@/lib/immobilierOrgApi';
import {
  CUBES_ORG, SEUIL_VENTES_FIABLES, libelleDimensionOrg, libelleModaliteOrg, minuscule, trierModalites,
} from '@/lib/immobilierOrgCubes';
import { formatEntier, formatPourcentage } from '@/lib/immobilier';

interface Props {
  cube: CubeOrg;
  prix: boolean;                       // cube de prix (médiane) ou de comptage (part de la ligne)
  axes: [string, string];
  cellules: OrgAnalyseCellule[];
  lignes: string[];                    // modalités du 1er axe (meta.modalites)
  colonnes: string[];                  // modalités du 2e axe
}

const cle = (ligne: string, colonne: string) => `${ligne}\u0000${colonne}`;

function Cellule({ cellule, prix, unite }: { cellule: OrgAnalyseCellule | undefined; prix: boolean; unite: string }) {
  // Pas de cellule : groupe masqué (accès verrouillé) ou combinaison sans observation
  if (!cellule) return <span className="text-gray-300">–</span>;
  const valeur = prix ? cellule.mediane : cellule.part_pct;
  const fragile = prix && cellule.n < SEUIL_VENTES_FIABLES;
  return (
    <div className={cn(fragile && 'text-gray-400')}>
      <div className="font-medium">{valeur === null ? '–' : prix ? formatEntier(valeur) : formatPourcentage(valeur)}</div>
      <div className="text-xs text-gray-400">{formatEntier(cellule.n)} {unite}</div>
    </div>
  );
}

export default function OrgTableau({ cube, prix, axes, cellules, lignes, colonnes }: Props) {
  if (cellules.length === 0) {
    return <p className="text-sm text-gray-400 py-8 text-center">Aucune donnée pour ce filtre.</p>;
  }

  const unite = CUBES_ORG[cube].unite;
  const parCle = new Map(cellules.map(c => [cle(c.modalites[0], c.modalites[1]), c]));
  const lignesVues = new Set(cellules.map(c => c.modalites[0]));
  const colonnesVues = new Set(cellules.map(c => c.modalites[1]));
  const lignesAffichees = trierModalites(axes[0], lignes).filter(l => lignesVues.has(l));
  const colonnesAffichees = trierModalites(axes[1], colonnes).filter(k => colonnesVues.has(k));

  return (
    <div>
      <p className="text-xs text-gray-500 mb-1">
        Lignes : {minuscule(libelleDimensionOrg(axes[0], cube))} · Colonnes : {minuscule(libelleDimensionOrg(axes[1], cube))}
      </p>
      <p className="text-xs text-gray-600 mb-2">
        {prix
          ? `Dans chaque case : le prix médian au m², puis le nombre de ${unite}. En gris : moins de ${SEUIL_VENTES_FIABLES} ventes, à lire avec prudence. Le total est le nombre de ${unite} de la ligne. « – » : aucune observation, ou trop peu pour être affichée tant que l’accès est verrouillé.`
          : `Dans chaque case : la part de la ligne (en %), puis le nombre de ${unite}. Le total est le nombre de ${unite} de la ligne. « – » : aucune observation, ou trop peu pour être affichée tant que l’accès est verrouillé.`}
      </p>

      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-gray-500 border-b">
              <th className="sticky left-0 bg-white py-1.5 pr-3 font-medium" />
              {colonnesAffichees.map(colonne => (
                <th key={colonne} className="py-1.5 px-3 font-medium text-right whitespace-nowrap">
                  {libelleModaliteOrg(axes[1], colonne)}
                </th>
              ))}
              <th className="py-1.5 px-3 font-medium text-right whitespace-nowrap">Total</th>
            </tr>
          </thead>
          <tbody>
            {lignesAffichees.map(ligne => (
              <tr key={ligne} className="border-b last:border-0">
                <th className="sticky left-0 bg-white py-1.5 pr-3 text-left font-medium text-gray-700 whitespace-nowrap">
                  {libelleModaliteOrg(axes[0], ligne)}
                </th>
                {colonnesAffichees.map(colonne => (
                  <td key={colonne} className="py-1.5 px-3 text-right tabular-nums text-gray-700 whitespace-nowrap">
                    <Cellule cellule={parCle.get(cle(ligne, colonne))} prix={prix} unite={unite} />
                  </td>
                ))}
                <td className="py-1.5 pl-3 text-right tabular-nums text-gray-700 whitespace-nowrap border-l">
                  <div className="font-medium">
                    {formatEntier(colonnesAffichees.reduce((somme, colonne) => somme + (parCle.get(cle(ligne, colonne))?.n ?? 0), 0))}
                  </div>
                  <div className="text-xs text-gray-400">{unite}</div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
