'use client';

import { useEffect, useState } from 'react';
import { OrgSourcesResponse, getOrgSources } from '@/lib/immobilierOrgApi';
import { formatDate, formatEntier } from '@/lib/immobilier';
import { CarteGraphique } from '../ImmobilierCharts';
import Lecture from '../bdnb/Lecture';

const STATUT_A_SIGNALER = 'non chargée';

export default function SourcesOrg() {
  const [data, setData] = useState<OrgSourcesResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Une seule lecture : les fiches sont peu nombreuses
  useEffect(() => {
    getOrgSources()
      .then(setData)
      .catch(e => setError(e instanceof Error ? e.message : 'Erreur de chargement'));
  }, []);

  if (error) {
    return <div className="text-sm text-red-600 bg-red-50 px-4 py-3 rounded-lg">{error}</div>;
  }
  if (!data) {
    return <div className="h-64 border rounded-lg bg-white animate-pulse" />;
  }

  return (
    <div className="space-y-6">
      <CarteGraphique
        titre="Sources des données"
        sousTitre="Pour chaque source : la période réellement couverte, le volume et la date de chargement"
      >
        <Lecture
          voir="Chaque jeu de données utilisé, qui le publie, quelle période il couvre et quand il a été chargé."
          retenir="Les sources ne couvrent pas toutes les mêmes dates : un chiffre ne vaut que pour la période de sa source."
        />
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-gray-500 border-b">
                <th className="py-1.5 font-medium">Source</th>
                <th className="py-1.5 pl-4 font-medium">Couverture</th>
                <th className="py-1.5 pl-4 font-medium text-right">Lignes</th>
                <th className="py-1.5 pl-4 font-medium">Chargée le</th>
                <th className="py-1.5 pl-4 font-medium">Utilisée par</th>
                <th className="py-1.5 pl-4 font-medium">Statut</th>
              </tr>
            </thead>
            {data.sources.map(s => (
              <tbody key={s.source} className="border-b last:border-0">
                <tr className="align-top">
                  <td className="pt-2 text-gray-900">
                    {s.source}
                    <span className="block text-xs text-gray-500">
                      {[s.editeur, s.version, s.publiee ? `publiée le ${s.publiee}` : null].filter(Boolean).join(' · ')}
                    </span>
                  </td>
                  <td className="pt-2 pl-4 text-gray-700">
                    {s.couverture ?? '—'}
                    {s.utilisee_depuis && (
                      <span className="block text-xs text-gray-500">utilisée depuis le {formatDate(s.utilisee_depuis)}</span>
                    )}
                  </td>
                  <td className="pt-2 pl-4 text-gray-700 text-right tabular-nums">
                    {s.nb_lignes === null ? '—' : formatEntier(s.nb_lignes)}
                  </td>
                  <td className="pt-2 pl-4 text-gray-700 whitespace-nowrap">{s.chargee_le ? formatDate(s.chargee_le) : '—'}</td>
                  <td className="pt-2 pl-4 text-gray-700">{s.utilisee_par ?? '—'}</td>
                  <td className={s.statut === STATUT_A_SIGNALER ? 'pt-2 pl-4 text-amber-700' : 'pt-2 pl-4 text-gray-600'}>
                    {s.statut}
                  </td>
                </tr>
                {s.limites && (
                  <tr>
                    <td colSpan={6} className="pb-2 pt-0.5 text-xs text-gray-500">
                      Limites : {s.limites}
                    </td>
                  </tr>
                )}
              </tbody>
            ))}
          </table>
        </div>
        {data.date_maj && (
          <p className="text-xs text-gray-500 mt-3">Fiches mises à jour le {formatDate(data.date_maj)}.</p>
        )}
      </CarteGraphique>

      <p className="text-xs text-gray-500">
        DVF (Etalab), BDNB (CSTB), DPE (ADEME) et BAN : Licence Ouverte 2.0. Loyers de référence (Ville de Paris) : ODbL.
        Textes juridiques : Légifrance (PISTE) et BOFiP-Impôts. Cartes et services en ligne : IGN, Géorisques.
      </p>
    </div>
  );
}
