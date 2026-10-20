'use client';

import { useEffect, useState } from 'react';
import { Chauffage, DpeLigne, ETIQUETTES, EtiquetteDpe, getDpe } from '@/lib/immobilierApi';
import {
  ARRONDISSEMENTS,
  CLASSE_CHAMP,
  LIBELLES_CHAUFFAGE,
  formatEntier,
  formatPourcentage,
  libelleArrondissement,
} from '@/lib/immobilier';
import { BarresHorizontales, CarteGraphique, COULEURS, ChoixVueArrondissements, Colonnes, Explication, ModeAffichage, Point, VueArrondissements } from './ImmobilierCharts';
import CarteParis from './CarteParis';

// Paramètres
const ETIQUETTES_PASSOIRES: string[] = ['F', 'G'];

export default function DpeView() {
  const [lignes, setLignes] = useState<DpeLigne[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [arrondissement, setArrondissement] = useState<number | null>(null);
  const [chauffage, setChauffage] = useState<Chauffage | ''>('');
  const [etiquette, setEtiquette] = useState<EtiquetteDpe | null>(null);
  const [mode, setMode] = useState<ModeAffichage>('graphique');
  const [vueArr, setVueArr] = useState<VueArrondissements>('carte');

  // Une seule lecture : la table agrégée est petite, les filtres s'appliquent ici
  useEffect(() => {
    getDpe()
      .then(r => setLignes(r.lignes))
      .catch(e => setError(e instanceof Error ? e.message : 'Erreur de chargement'));
  }, []);

  if (error) {
    return <div className="text-sm text-red-600 bg-red-50 px-4 py-3 rounded-lg">{error}</div>;
  }
  if (!lignes) {
    return <div className="h-64 border rounded-lg bg-white animate-pulse" />;
  }

  const portee = lignes.filter(
    l => !chauffage || (chauffage === 'electrique') === l.flag_chauffage_electrique,
  );
  const dansArrondissement =
    arrondissement === null ? portee : portee.filter(l => l.arrondissement === arrondissement);

  // Répartition par étiquette, sur le périmètre choisi ; l'étiquette ciblée en emphase
  const total = dansArrondissement.reduce((somme, l) => somme + l.nb_dpe, 0);
  const parEtiquette: Point[] = ETIQUETTES.map(lettre => {
    const nb = dansArrondissement
      .filter(l => l.etiquette_dpe === lettre)
      .reduce((somme, l) => somme + l.nb_dpe, 0);
    return {
      nom: lettre,
      valeur: nb,
      detail: total ? formatPourcentage((100 * nb) / total) : undefined,
      couleur: etiquette === null || etiquette === lettre ? COULEURS.slot1 : COULEURS.axe,
    };
  });

  // Part par arrondissement des étiquettes ciblées (F et G par défaut, ou l'étiquette choisie) ;
  // tous les arrondissements, celui choisi en emphase
  const ciblees: string[] = etiquette ? [etiquette] : ETIQUETTES_PASSOIRES;
  const cumul = new Map<number, { total: number; cible: number }>();
  for (const l of portee) {
    if (l.arrondissement === null) continue;
    const c = cumul.get(l.arrondissement) ?? { total: 0, cible: 0 };
    c.total += l.nb_dpe;
    if (ciblees.includes(l.etiquette_dpe)) c.cible += l.nb_dpe;
    cumul.set(l.arrondissement, c);
  }
  const parArrondissement: Point[] = [...cumul.entries()]
    .map(([arr, c]) => ({
      id: arr,
      nom: libelleArrondissement(arr),
      valeur: (100 * c.cible) / c.total,
      detail: `${formatEntier(c.cible)} sur ${formatEntier(c.total)} DPE`,
      couleur: arrondissement === null || arrondissement === arr ? COULEURS.slot1 : COULEURS.axe,
    }))
    .sort((a, b) => b.valeur - a.valeur);

  const perimetre = arrondissement === null ? 'Paris' : `Paris ${libelleArrondissement(arrondissement)}`;

  const baseCible = etiquette ? `Étiquette ${etiquette}` : 'Étiquettes F et G';
  const libelleValeur = etiquette ? `Part des ${etiquette}` : 'Part de passoires';

  // Clic sur un graphique : même effet que les listes déroulantes ; un second clic désélectionne
  const choisirEtiquette = (nom: string) =>
    setEtiquette(courante => (courante === nom ? null : (nom as EtiquetteDpe)));
  const choisirArrondissement = (nom: string) => {
    const n = Number.parseInt(nom, 10);
    setArrondissement(courant => (courant === n ? null : n));
  };

  return (
    <div className="space-y-6">

      {/* Filtres : une seule ligne, au-dessus de ce qu'ils portent */}
      <div className="flex flex-wrap items-center gap-4 text-sm text-gray-600">
        <label className="inline-flex items-center gap-2">
          Arrondissement
          <select
            value={arrondissement ?? ''}
            onChange={e => setArrondissement(e.target.value ? Number(e.target.value) : null)}
            className={CLASSE_CHAMP}
          >
            <option value="">Tous</option>
            {ARRONDISSEMENTS.map(n => (
              <option key={n} value={n}>{libelleArrondissement(n)}</option>
            ))}
          </select>
        </label>
        <label className="inline-flex items-center gap-2">
          Chauffage
          <select
            value={chauffage}
            onChange={e => setChauffage(e.target.value as Chauffage | '')}
            className={CLASSE_CHAMP}
          >
            <option value="">Tous</option>
            {(Object.keys(LIBELLES_CHAUFFAGE) as Chauffage[]).map(c => (
              <option key={c} value={c}>{LIBELLES_CHAUFFAGE[c]}</option>
            ))}
          </select>
        </label>
        <label className="inline-flex items-center gap-2">
          Étiquette ciblée
          <select
            value={etiquette ?? ''}
            onChange={e => setEtiquette(e.target.value ? (e.target.value as EtiquetteDpe) : null)}
            className={CLASSE_CHAMP}
          >
            <option value="">Aucune</option>
            {ETIQUETTES.map(lettre => (
              <option key={lettre} value={lettre}>{lettre}</option>
            ))}
          </select>
        </label>
        {mode === 'graphique' && <ChoixVueArrondissements valeur={vueArr} onChange={setVueArr} />}
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
        titre="Répartition par étiquette"
        sousTitre={`${perimetre} · ${formatEntier(total)} DPE · cliquez sur une colonne`}
      >
        <Explication>
          <p>
            Le DPE (diagnostic de performance énergétique) classe un logement de A (très économe) à G
            (très énergivore). Chaque colonne compte les logements de Paris, ou de l’arrondissement choisi,
            pour une étiquette.
          </p>
          <p>
            F et G sont les « passoires énergétiques ». Ne sont comptés que les logements dont le DPE a été
            établi depuis juillet 2021, pas l’ensemble du parc.
          </p>
          <p>
            Cliquez sur une colonne pour voir, dans le graphique du dessous, la part de cette étiquette dans
            chaque arrondissement ; cliquez de nouveau pour revenir à F et G.
          </p>
        </Explication>
        <Colonnes
          points={parEtiquette}
          colonneNom="Étiquette"
          colonneValeur="DPE"
          colonneDetail="Part"
          formater={formatEntier}
          mode={mode}
          onSelect={choisirEtiquette}
        />
      </CarteGraphique>

      <CarteGraphique
        titre={
          etiquette
            ? `Part des DPE d’étiquette ${etiquette} par arrondissement`
            : 'Part de passoires par arrondissement'
        }
        sousTitre={
          arrondissement === null
            ? `${baseCible}, sur l’ensemble des DPE de l’arrondissement · cliquez sur la carte ou sur une barre`
            : `${baseCible} · ${perimetre} en bleu, les autres arrondissements en gris`
        }
      >
        <Explication>
          <p>
            Pour chaque arrondissement, la part des DPE classés F ou G (ou de l’étiquette choisie dans le
            graphique du dessus). Plus la barre est longue, plus l’arrondissement compte de logements très
            énergivores parmi ses DPE.
          </p>
          <p>
            Sur la carte, plus la couleur est foncée, plus la part est élevée ; les chiffres sont les numéros
            d’arrondissement. Le bouton « Affichage » permet de passer de la carte aux barres, qui donnent le classement.
          </p>
          <p>
            Cliquez sur une barre ou sur la carte pour filtrer toute la page sur cet arrondissement ; cliquez
            de nouveau pour revenir à tout Paris.
          </p>
        </Explication>
        {mode === 'tableau' ? (
          <BarresHorizontales
            points={parArrondissement}
            colonneNom="Arrondissement"
            colonneValeur={libelleValeur}
            colonneDetail="DPE"
            formater={formatPourcentage}
            mode={mode}
          />
        ) : vueArr === 'carte' ? (
          <CarteParis
            points={parArrondissement}
            selection={arrondissement}
            onSelect={id => choisirArrondissement(String(id))}
            formater={formatPourcentage}
            legende={libelleValeur}
          />
        ) : (
          <BarresHorizontales
            points={parArrondissement}
            colonneNom="Arrondissement"
            colonneValeur={libelleValeur}
            colonneDetail="DPE"
            formater={formatPourcentage}
            mode={mode}
            onSelect={choisirArrondissement}
          />
        )}
      </CarteGraphique>

      <p className="text-xs text-gray-500">
        DPE des logements existants établis depuis juillet 2021 (ADEME). Chauffage « électrique » : énergie
        principale de chauffage.
      </p>
    </div>
  );
}
