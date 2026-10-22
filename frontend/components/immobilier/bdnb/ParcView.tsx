'use client';

import { useEffect, useState } from 'react';
import { DeperditionLigne, ParcResponse, getBdnbParc } from '@/lib/immobilierBdnbApi';
import {
  GROUPES_ETIQUETTE, LIBELLE_ENERGIE_AUTRES, POSTES, groupeEtiquette, libelleEnergie, libellePeriode, ordrePeriode,
} from '@/lib/immobilierBdnb';
import { formatEntier, formatPourcentage } from '@/lib/immobilier';
import { CarteGraphique, Explication, ModeAffichage } from '../ImmobilierCharts';
import BarresEmpilees, { BarreEmpilee, SerieEmpilee } from './BarresEmpilees';

// Paramètres
const FIN_DE_LISTE = [LIBELLE_ENERGIE_AUTRES, 'Non renseigné'];   // en bas du classement des énergies

const SERIES_ETIQUETTE: SerieEmpilee[] = GROUPES_ETIQUETTE.map(g => ({
  id: g.id, libelle: g.libelle, couleur: g.couleur,
}));
const SERIES_POSTE: SerieEmpilee[] = POSTES.map(p => ({ id: p.id, libelle: p.libelle, couleur: p.couleur }));

function totalBarre(barre: BarreEmpilee): number {
  return Object.values(barre.valeurs).reduce((somme, v) => somme + v, 0);
}

// Effectifs par barre, regroupés en groupes d'étiquettes ; l'ordre des barres est celui des lignes reçues
function regrouperEtiquettes(lignes: { nom: string; etiquette: string; nb_dpe: number }[]): BarreEmpilee[] {
  const parNom = new Map<string, Record<string, number>>();
  for (const { nom, etiquette, nb_dpe } of lignes) {
    const groupe = groupeEtiquette(etiquette);
    if (!groupe) continue;
    const valeurs = parNom.get(nom) ?? {};
    valeurs[groupe.id] = (valeurs[groupe.id] ?? 0) + nb_dpe;
    parNom.set(nom, valeurs);
  }
  return [...parNom.entries()].map(([nom, valeurs]) => {
    const barre: BarreEmpilee = { nom, valeurs };
    return { ...barre, detail: `${formatEntier(totalBarre(barre))} DPE` };
  });
}

function rangFin(nom: string): number {
  const i = FIN_DE_LISTE.indexOf(nom);
  return i === -1 ? 0 : i + 1;
}

// Parts moyennes par poste, une barre par période ; la base est le nombre de logements de la période
function barresDeperditions(lignes: DeperditionLigne[]): BarreEmpilee[] {
  const parPeriode = new Map<string, { valeurs: Record<string, number>; nb: number }>();
  const triees = [...lignes].sort((a, b) => ordrePeriode(a.periode_construction) - ordrePeriode(b.periode_construction));
  for (const l of triees) {
    if (l.part_moyenne === null) continue;
    const nom = libellePeriode(l.periode_construction);
    const entree = parPeriode.get(nom) ?? { valeurs: {}, nb: 0 };
    entree.valeurs[l.poste] = l.part_moyenne;
    entree.nb = Math.max(entree.nb, l.nb_logements);   // les 6 postes portent sur les mêmes logements
    parPeriode.set(nom, entree);
  }
  return [...parPeriode.entries()].map(([nom, e]) => ({
    nom,
    valeurs: e.valeurs,
    detail: `${formatEntier(e.nb)} logements`,
  }));
}

export default function ParcView() {
  const [data, setData] = useState<ParcResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<ModeAffichage>('graphique');

  // Une seule lecture : les agrégats sont petits
  useEffect(() => {
    getBdnbParc()
      .then(setData)
      .catch(e => setError(e instanceof Error ? e.message : 'Erreur de chargement'));
  }, []);

  if (error) {
    return <div className="text-sm text-red-600 bg-red-50 px-4 py-3 rounded-lg">{error}</div>;
  }
  if (!data) {
    return <div className="h-64 border rounded-lg bg-white animate-pulse" />;
  }

  const parPeriode = regrouperEtiquettes(
    [...data.periodes]
      .sort((a, b) => ordrePeriode(a.periode_construction) - ordrePeriode(b.periode_construction))
      .map(l => ({ nom: libellePeriode(l.periode_construction), etiquette: l.etiquette, nb_dpe: l.nb_dpe })),
  );

  const parEnergie = regrouperEtiquettes(
    data.energies.map(l => ({ nom: libelleEnergie(l.energie_chauffage), etiquette: l.etiquette, nb_dpe: l.nb_dpe })),
  ).sort((a, b) => rangFin(a.nom) - rangFin(b.nom) || totalBarre(b) - totalBarre(a));

  const deperditions = barresDeperditions(data.deperditions);
  const couverture = data.nb_dpe ? formatPourcentage((100 * data.nb_logements_deperditions) / data.nb_dpe) : '—';

  return (
    <div className="space-y-6">

      <div className="flex flex-wrap items-center gap-4 text-sm text-gray-600">
        <label className="inline-flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={mode === 'tableau'}
            onChange={e => setMode(e.target.checked ? 'tableau' : 'graphique')}
            className="w-4 h-4 rounded border-gray-300"
          />
          Voir en tableau
        </label>
      </div>

      <CarteGraphique
        titre="Étiquettes par période de construction"
        sousTitre={`${formatEntier(data.nb_dpe)} DPE retenus · chaque barre est ramenée à 100 %`}
      >
        <Explication>
          <p>
            Chaque barre est une période de construction. Ses segments donnent la répartition des étiquettes DPE
            des logements de cette période, de A–B (très économes, teinte la plus claire) à F–G (passoires, teinte
            la plus foncée).
          </p>
          <p>
            Sous le nom de chaque barre figure le nombre de DPE de la période : un pourcentage calculé sur peu de
            logements est fragile.
          </p>
        </Explication>
        <BarresEmpilees
          barres={parPeriode}
          series={SERIES_ETIQUETTE}
          mode={mode}
          colonneNom="Période"
          colonneDetail="DPE"
          formaterEffectif={formatEntier}
        />
      </CarteGraphique>

      <CarteGraphique
        titre="Énergie de chauffage et étiquette"
        sousTitre="Répartition des étiquettes pour chaque énergie principale de chauffage"
      >
        <Explication>
          <p>
            Chaque barre est une énergie principale de chauffage ; ses segments donnent la répartition des
            étiquettes des logements qui l’utilisent, avec les mêmes couleurs que le graphique du dessus.
          </p>
          <p>
            « Autres » regroupe le GPL, le bois, le solaire et le charbon, qui comptent très peu de logements à
            eux quatre.
          </p>
        </Explication>
        <BarresEmpilees
          barres={parEnergie}
          series={SERIES_ETIQUETTE}
          mode={mode}
          colonneNom="Énergie"
          colonneDetail="DPE"
          formaterEffectif={formatEntier}
        />
      </CarteGraphique>

      <CarteGraphique
        titre="Où le logement perd sa chaleur"
        sousTitre={`Part moyenne de chaque poste, par période · ${couverture} des logements (${formatEntier(data.nb_logements_deperditions)} sur ${formatEntier(data.nb_dpe)}) ont leurs six postes renseignés`}
      >
        <Explication>
          <p>
            Les déperditions mesurent la chaleur perdue par chaque élément de l’enveloppe du logement : murs,
            baies vitrées, planchers bas et hauts, ponts thermiques et portes.
          </p>
          <p>
            Pour chaque logement, on calcule la part de chaque poste dans le total de ses déperditions, puis on
            fait la moyenne de ces parts pour chaque période de construction. Les six segments d’une barre
            totalisent donc 100 %.
          </p>
          <p>
            Seuls les logements dont les six postes sont renseignés sont comptés ; le nombre de logements de la
            période figure sous son nom.
          </p>
        </Explication>
        <BarresEmpilees
          barres={deperditions}
          series={SERIES_POSTE}
          mode={mode}
          colonneNom="Période"
          colonneDetail="Logements"
        />
      </CarteGraphique>

      <p className="text-xs text-gray-500">
        DPE de l’arrêté 2021 (ADEME) via la BDNB (CSTB) : logements, méthode 3CL, surface habitable renseignée.
      </p>
    </div>
  );
}
