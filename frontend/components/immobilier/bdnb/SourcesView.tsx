'use client';

import { useEffect, useState } from 'react';
import { SourcesResponse, getBdnbSources } from '@/lib/immobilierBdnbApi';
import { libelleAppariement, libelleFiabilite } from '@/lib/immobilierBdnb';
import { formatEntier, formatPourcentage } from '@/lib/immobilier';
import { CarteGraphique, COULEURS, Explication } from '../ImmobilierCharts';

// Paramètres
const ORDRE_FIABILITE = ['très fiable', 'globalement fiable', 'fiable', 'non renseigné'];
const PART_MAX_BARRE = 70;     // % de la largeur disponible pour la plus longue barre : le reste sert à la valeur

interface LigneBarre {
  nom: string;
  valeur: number;
  detail?: string;
}

// Barres horizontales à libellés longs : le composant partagé réserve 48 px aux noms (numéros d'arrondissement).
// Barre de 20 px, bout arrondi à droite, carrée à la base ; la valeur est écrite au bout.
function BarresListe({ lignes }: { lignes: LigneBarre[] }) {
  const max = Math.max(0, ...lignes.map(l => l.valeur));
  return (
    <ul className="space-y-2">
      {lignes.map(l => (
        <li key={l.nom} className="flex items-center gap-3 text-sm">
          <span className="w-40 sm:w-56 shrink-0 text-gray-700">{l.nom}</span>
          <div className="flex-1 min-w-0 flex items-center gap-2">
            <div
              className="h-5 rounded-r"
              style={{
                width: `${max ? (PART_MAX_BARRE * l.valeur) / max : 0}%`,
                minWidth: 2,
                backgroundColor: COULEURS.slot1,
              }}
            />
            <span className="text-xs text-gray-600 whitespace-nowrap">
              {formatEntier(l.valeur)}
              {l.detail && <span className="text-gray-400"> · {l.detail}</span>}
            </span>
          </div>
        </li>
      ))}
    </ul>
  );
}

function sommerParCle(lignes: { cle: string; nb: number }[]): Map<string, number> {
  const somme = new Map<string, number>();
  for (const { cle, nb } of lignes) somme.set(cle, (somme.get(cle) ?? 0) + nb);
  return somme;
}

function rangFiabilite(fiabilite: string): number {
  const i = ORDRE_FIABILITE.indexOf(fiabilite);
  return i === -1 ? ORDRE_FIABILITE.length : i;
}

export default function SourcesView() {
  const [data, setData] = useState<SourcesResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Une seule lecture : les tables sont petites
  useEffect(() => {
    getBdnbSources()
      .then(setData)
      .catch(e => setError(e instanceof Error ? e.message : 'Erreur de chargement'));
  }, []);

  if (error) {
    return <div className="text-sm text-red-600 bg-red-50 px-4 py-3 rounded-lg">{error}</div>;
  }
  if (!data) {
    return <div className="h-64 border rounded-lg bg-white animate-pulse" />;
  }

  // Entonnoir : chaque étape en part de la première (tous les DPE de la BDNB pour Paris)
  const etapes = [...data.entonnoir].sort((a, b) => a.etape - b.etape);
  const baseEntonnoir = etapes[0]?.nb_dpe ?? 0;
  const nbRetenus = etapes[etapes.length - 1]?.nb_dpe ?? 0;
  const entonnoir: LigneBarre[] = etapes.map(e => ({
    nom: e.libelle,
    valeur: e.nb_dpe,
    detail: baseEntonnoir ? formatPourcentage((100 * e.nb_dpe) / baseEntonnoir) : undefined,
  }));

  // Géocodage : liens entre un DPE et un bâtiment
  const totalLiens = data.geocodage.reduce((somme, l) => somme + l.nb_liens, 0);
  const part = (nb: number) => (totalLiens ? formatPourcentage((100 * nb) / totalLiens) : undefined);

  const fiabilite: LigneBarre[] = [...sommerParCle(data.geocodage.map(l => ({ cle: l.fiabilite, nb: l.nb_liens })))]
    .sort(([a], [b]) => rangFiabilite(a) - rangFiabilite(b))
    .map(([cle, nb]) => ({ nom: libelleFiabilite(cle), valeur: nb, detail: part(nb) }));

  const appariement: LigneBarre[] = [...sommerParCle(data.geocodage.map(l => ({ cle: l.appariement, nb: l.nb_liens })))]
    .sort(([, a], [, b]) => b - a)
    .map(([cle, nb]) => ({ nom: libelleAppariement(cle), valeur: nb, detail: part(nb) }));

  return (
    <div className="space-y-6">

      <CarteGraphique
        titre="Sources et millésimes"
        sousTitre="Les données publiques assemblées par la BDNB, avec leur date"
      >
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-gray-500 border-b">
                <th className="py-1.5 font-medium">Source</th>
                <th className="py-1.5 font-medium">Millésime</th>
                <th className="py-1.5 font-medium">Couverture</th>
              </tr>
            </thead>
            <tbody>
              {data.sources.map(s => (
                <tr key={s.source} className="border-b last:border-0">
                  <td className="py-1.5 text-gray-700">{s.source}</td>
                  <td className="py-1.5 text-gray-700">{s.millesime}</td>
                  <td className="py-1.5 text-gray-500">{s.couverture ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CarteGraphique>

      <CarteGraphique
        titre="De la BDNB à la sélection retenue"
        sousTitre="Nombre de DPE après chaque filtre, en part des DPE de la BDNB pour Paris"
      >
        <Explication>
          <p>
            Chaque ligne applique un filtre de plus, dans cet ordre : DPE de l’arrêté 2021 (ceux de l’arrêté 2012
            sont écartés), logements (les DPE d’immeuble sont écartés), méthode 3CL, surface habitable renseignée.
          </p>
          <p>La dernière ligne est la sélection chargée et utilisée dans les autres vues.</p>
        </Explication>
        <BarresListe lignes={entonnoir} />
      </CarteGraphique>

      <CarteGraphique
        titre="Fiabilité du géocodage"
        sousTitre={`${formatEntier(totalLiens)} liens entre un DPE et un bâtiment, pour ${formatEntier(nbRetenus)} DPE retenus : certains DPE sont reliés à plusieurs bâtiments`}
      >
        <Explication>
          <p>
            La BDNB rattache chaque DPE à un bâtiment. Chaque barre compte les liens selon la fiabilité du
            géocodage indiquée par la BDNB ; « non renseigné » regroupe les liens sans information.
          </p>
        </Explication>
        <BarresListe lignes={fiabilite} />
      </CarteGraphique>

      <CarteGraphique
        titre="Type d’appariement"
        sousTitre="Méthode utilisée par la BDNB pour associer un DPE à un bâtiment"
      >
        <Explication>
          <p>
            Un DPE peut être associé à un bâtiment par son adresse, sa parcelle, ou l’identifiant RNB lorsque
            celui-ci est renseigné par le diagnostiqueur ou via le RPLS. Quand plusieurs méthodes coïncident,
            elles sont indiquées ensemble (par exemple « parcelle + adresse »).
          </p>
        </Explication>
        <BarresListe lignes={appariement} />
      </CarteGraphique>


      <p className="text-xs text-gray-500">
        BDNB (CSTB), Licence Ouverte 2.0. DPE : ADEME. Transactions : DVF (Cerema). Adresses : BAN.
      </p>
    </div>
  );
}
