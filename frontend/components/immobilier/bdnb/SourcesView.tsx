'use client';

import { useEffect, useState } from 'react';
import { SourcesResponse, getBdnbSources } from '@/lib/immobilierBdnbApi';
import { METHODES_NON_RATTACHEES, libelleAppariement, libelleFiabilite, libelleMethodeRattachement } from '@/lib/immobilierBdnb';
import { attentionQualite, retenirAppariement, retenirEntonnoir, retenirGeocodage, retenirQualite } from '@/lib/immobilierBdnbTextes';
import { formatEntier, formatPourcentage } from '@/lib/immobilier';
import { CarteGraphique, COULEURS, Explication } from '../ImmobilierCharts';
import Lecture from './Lecture';

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

    // Qualité du rattachement des ventes : les ventes non rattachées en dernier, les autres par nombre de ventes
  const methodes = [...(data.qualite?.methodes ?? [])].sort(
    (a, b) =>
      Number(METHODES_NON_RATTACHEES.includes(a.methode)) - Number(METHODES_NON_RATTACHEES.includes(b.methode)) ||
      b.nb_ventes - a.nb_ventes,
  );

  return (
    <div className="space-y-6">

      <CarteGraphique
        titre="Sources et millésimes"
        sousTitre="Les données publiques assemblées par la BDNB, avec leur date"
      >
        <Lecture
          voir="D’où viennent les données, et jusqu’à quelle date."
          retenir="Un chiffre ne vaut que pour la période couverte par sa source : voir la colonne « Couverture »."
        />
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-gray-500 border-b">
                <th className="py-1.5 font-medium">Source</th>
                <th className="py-1.5 font-medium">Version</th>
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
        <Lecture
          voir="Combien de diagnostics (DPE) la base contient pour Paris, et combien il en reste après chaque filtre."
          retenir={retenirEntonnoir(data)}
          attention="Les DPE de l’ancienne réglementation (arrêté 2012) sont écartés : leur méthode de calcul diffère et ils n’ont pas de date d’établissement."
        />
        <Explication titre="Détails des filtres">
          <p>
            Chaque ligne applique un filtre de plus, dans cet ordre : DPE de l’arrêté 2021 (ceux de l’arrêté 2012
            sont écartés), logements (les DPE d’immeuble sont écartés), méthode 3CL, surface habitable renseignée.
          </p>
          <p>La dernière ligne est la sélection chargée et utilisée dans les autres vues.</p>
        </Explication>
        <BarresListe lignes={entonnoir} />
      </CarteGraphique>

      <CarteGraphique
        titre="Fiabilité du rattachement des DPE aux immeubles"
        sousTitre={`${formatEntier(totalLiens)} liens entre un DPE et un immeuble, pour ${formatEntier(nbRetenus)} DPE retenus : certains DPE sont reliés à plusieurs immeubles`}
      >
        <Lecture
          voir="La base doit retrouver dans quel immeuble se trouve chaque logement diagnostiqué. Ces barres montrent la confiance qu’elle accorde à ce rattachement."
          retenir={retenirGeocodage(data)}
          attention="Le prix par note énergétique (vue « Prix et DPE ») repose sur ce rattachement. « Non renseigné » regroupe les liens sans information."
        />
        <BarresListe lignes={fiabilite} />
      </CarteGraphique>

      <CarteGraphique
        titre="Comment un DPE est relié à son immeuble"
        sousTitre="Méthode utilisée par la BDNB pour associer un DPE à un immeuble"
      >
        <Lecture
          voir="La méthode utilisée pour rattacher un logement à son immeuble : par son adresse, sa parcelle cadastrale, ou l’identifiant national du bâtiment (RNB)."
          retenir={retenirAppariement(data)}
        />
        <Explication titre="Détails">
          <p>
            Un DPE peut être associé à un bâtiment par son adresse, sa parcelle, ou l’identifiant RNB lorsque
            celui-ci est renseigné par le diagnostiqueur ou via le RPLS. Quand plusieurs méthodes coïncident,
            elles sont indiquées ensemble (par exemple « parcelle + adresse »).
          </p>
        </Explication>
        <BarresListe lignes={appariement} />
      </CarteGraphique>

            {data.qualite && (
        <CarteGraphique
          titre="Rattachement des ventes aux immeubles"
          sousTitre={`Ventes du DVF Etalab (livraison ${data.qualite.livraison}) reliées à un immeuble de la BDNB, contrôlées sur ${formatEntier(data.qualite.nb_controle)} ventes`}
        >
          <Lecture
            voir="Chaque vente est reliée à l’immeuble où elle a eu lieu, par sa parcelle cadastrale et par son adresse. Ce tableau compare ce rattachement à celui de la BDNB sur ses propres ventes."
            retenir={retenirQualite(data)}
            attention={attentionQualite(data)}
          />
          <Explication titre="Détails des méthodes">
            <p>
              « Concordent » : la parcelle et l’adresse désignent le même immeuble. « Parcelle seule » et « adresse
              seule » : un seul des deux critères désigne un immeuble. « Divergent » : les deux critères désignent deux
              immeubles différents, on retient l’adresse. « Croisées » : aucun critère ne suffit seul, mais un seul
              immeuble figure dans les deux listes. « Ambiguë » : plusieurs immeubles possibles, la vente n’est
              rattachée à aucun.
            </p>
          </Explication>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-gray-500 border-b">
                  <th className="py-1.5 font-medium">Méthode</th>
                  <th className="py-1.5 font-medium text-right">Ventes</th>
                  <th className="py-1.5 pl-4 font-medium">Précision</th>
                </tr>
              </thead>
              <tbody>
                {methodes.map(m => (
                  <tr key={m.methode} className="border-b last:border-0">
                    <td className="py-1.5 text-gray-700">{libelleMethodeRattachement(m.methode)}</td>
                    <td className="py-1.5 text-gray-700 text-right">{formatEntier(m.nb_ventes)}</td>
                    <td className="py-1.5 pl-4">
                      {m.precision_pct === null ? (
                        <span className="text-xs text-gray-500">Non rattachée</span>
                      ) : (
                        <div className="flex items-center gap-2">
                          <div className="w-24 h-3 bg-gray-100 rounded-r">
                            <div
                              className="h-3 rounded-r"
                              style={{ width: `${m.precision_pct}%`, backgroundColor: COULEURS.slot1 }}
                            />
                          </div>
                          <span className="text-xs text-gray-600 whitespace-nowrap">{formatPourcentage(m.precision_pct)}</span>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CarteGraphique>
      )}

      <p className="text-xs text-gray-500">
        BDNB (CSTB), Licence Ouverte 2.0. DPE : ADEME. Transactions : DVF (Etalab ; Cerema pour le contrôle du rattachement). Adresses : BAN.
      </p>
    </div>
  );
}
