'use client';

import { useEffect, useState } from 'react';
import { OrgQualiteLigne, OrgQualiteResponse, getOrgQualite } from '@/lib/immobilierOrgApi';
import { formatDate, formatEntier } from '@/lib/immobilier';
import { CarteGraphique } from '../ImmobilierCharts';
import Lecture from '../bdnb/Lecture';

// Ordre d'affichage des parties (une partie absente de la liste vient après) et ce que chacune contrôle
const PARTIES: { partie: string; sousTitre: string }[] = [
  { partie: 'DVF', sousTitre: 'Ventes de logement de la période, retenues ou écartées des analyses' },
  { partie: 'DPE ADEME', sousTitre: 'Diagnostics collectés auprès de l’ADEME' },
  { partie: 'Croisé', sousTitre: 'Rapprochement des ventes, des DPE de la BDNB et des DPE de l’ADEME' },
  { partie: 'Loyers', sousTitre: 'Ventes rattachées à un loyer de référence' },
  { partie: 'Cohérence', sousTitre: 'La période paramétrée est-elle couverte par les données ?' },
];

function formatValeur(ligne: OrgQualiteLigne): string {
  return ligne.valeur === null ? '—' : `${formatEntier(ligne.valeur)} ${ligne.unite}`;
}

function rang(partie: string): number {
  const i = PARTIES.findIndex(p => p.partie === partie);
  return i === -1 ? PARTIES.length : i;
}

export default function QualiteOrg() {
  const [data, setData] = useState<OrgQualiteResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Une seule lecture : la table est petite
  useEffect(() => {
    getOrgQualite()
      .then(setData)
      .catch(e => setError(e instanceof Error ? e.message : 'Erreur de chargement'));
  }, []);

  if (error) {
    return <div className="text-sm text-red-600 bg-red-50 px-4 py-3 rounded-lg">{error}</div>;
  }
  if (!data) {
    return <div className="h-64 border rounded-lg bg-white animate-pulse" />;
  }

  const parties = [...new Set(data.indicateurs.map(i => i.partie))].sort((a, b) => rang(a) - rang(b));

  return (
    <div className="space-y-6">
      <Lecture
        voir="Des indicateurs mesurés dans les données : ce qui est retenu, ce qui est écarté, et où deux sources ne coïncident pas."
        retenir="Chaque indicateur est recalculé à chaque chargement ; il décrit les données, pas la réalité du marché."
      />

      {parties.map(partie => (
        <CarteGraphique
          key={partie}
          titre={partie}
          sousTitre={PARTIES.find(p => p.partie === partie)?.sousTitre}
        >
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-gray-500 border-b">
                  <th className="py-1.5 font-medium">Indicateur</th>
                  <th className="py-1.5 pl-4 font-medium text-right">Valeur</th>
                  <th className="py-1.5 pl-4 font-medium">Commentaire</th>
                </tr>
              </thead>
              <tbody>
                {data.indicateurs
                  .filter(i => i.partie === partie)
                  .map(i => (
                    <tr key={i.indicateur} className="border-b last:border-0 align-top">
                      <td className="py-1.5 text-gray-700">{i.indicateur}</td>
                      <td className="py-1.5 pl-4 text-gray-900 text-right tabular-nums whitespace-nowrap">{formatValeur(i)}</td>
                      <td className="py-1.5 pl-4 text-gray-500">{i.commentaire ?? ''}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </CarteGraphique>
      ))}

      {data.date_maj && (
        <p className="text-xs text-gray-500">Indicateurs calculés le {formatDate(data.date_maj)}.</p>
      )}
    </div>
  );
}
