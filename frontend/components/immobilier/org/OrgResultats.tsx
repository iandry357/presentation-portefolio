'use client';

import type { CubeOrg, OrgAnalyseCellule, OrgAnalyseMeta } from '@/lib/immobilierOrgApi';
import { CUBES_ORG, libelleDimensionOrg, libelleModaliteOrg, trierCellules } from '@/lib/immobilierOrgCubes';
import { CelluleCsv, telechargerCsv } from '@/lib/immobilierOrgCsv';

interface Props {
  cube: CubeOrg;
  meta: OrgAnalyseMeta;
  cellules: OrgAnalyseCellule[];
}

function afficher(valeur: CelluleCsv): string {
  return valeur === null ? '—' : typeof valeur === 'number' ? valeur.toLocaleString('fr-FR') : valeur;
}

// Tableau des chiffres du graphique, un groupe par ligne, avec son téléchargement en CSV
export default function OrgResultats({ cube, meta, cellules }: Props) {
  if (cellules.length === 0) {
    return <p className="text-sm text-gray-400 py-8 text-center">Aucune donnée pour ce filtre.</p>;
  }

  const prix = meta.mesure === 'prix';
  const unite = CUBES_ORG[cube].unite;
  const entetes = [
    ...meta.axes.map(axe => libelleDimensionOrg(axe, cube)),
    `Nombre de ${unite}`,
    ...(prix ? ['Prix médian (€/m²)', '1er quartile (€/m²)', '3e quartile (€/m²)'] : ['Part (%)']),
    ...(cube === 'batiment' ? ['Logements'] : []),
    ...(cube === 'dpe' ? ['DPE remplaçants'] : []),
  ];
  const lignes: CelluleCsv[][] = trierCellules(meta.axes, cellules).map(c => [
    ...c.modalites.map((modalite, i) => libelleModaliteOrg(meta.axes[i], modalite)),
    c.n,
    ...(prix ? [c.mediane, c.q1, c.q3] : [c.part_pct]),
    ...(cube === 'batiment' ? [c.nb_logements] : []),
    ...(cube === 'dpe' ? [c.nb_remplacants] : []),
  ]);
  const nbAxes = meta.axes.length;

  return (
    <div>
      <div className="flex justify-end mb-2">
        <button
          type="button"
          onClick={() => telechargerCsv(`immobilier_${cube}_${meta.axes.join('_')}.csv`, entetes, lignes)}
          className="text-sm text-blue-700 hover:underline"
        >
          Télécharger en CSV
        </button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-gray-500 border-b">
              {entetes.map((entete, i) => (
                <th key={entete} className={i < nbAxes ? 'py-1.5 pr-3 font-medium' : 'py-1.5 px-3 font-medium text-right'}>
                  {entete}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {lignes.map((ligne, i) => (
              <tr key={i} className="border-b last:border-0">
                {ligne.map((cellule, j) => (
                  <td
                    key={j}
                    className={j < nbAxes ? 'py-1.5 pr-3 text-gray-700 whitespace-nowrap' : 'py-1.5 px-3 text-right tabular-nums text-gray-700'}
                  >
                    {afficher(cellule)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
