'use client';

import { useEffect, useState } from 'react';
import { Chauffage, DpeLigne, ETIQUETTES, getDpe } from '@/lib/immobilierApi';
import {
  ARRONDISSEMENTS,
  CLASSE_CHAMP,
  LIBELLES_CHAUFFAGE,
  formatEntier,
  formatPourcentage,
  libelleArrondissement,
} from '@/lib/immobilier';
import { BarresHorizontales, CarteGraphique, COULEURS, Colonnes, ModeAffichage, Point } from './ImmobilierCharts';

// Paramètres
const ETIQUETTES_PASSOIRES: string[] = ['F', 'G'];

export default function DpeView() {
  const [lignes, setLignes] = useState<DpeLigne[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [arrondissement, setArrondissement] = useState<number | null>(null);
  const [chauffage, setChauffage] = useState<Chauffage | ''>('');
  const [mode, setMode] = useState<ModeAffichage>('graphique');

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

  // Répartition par étiquette, sur le périmètre choisi
  const total = dansArrondissement.reduce((somme, l) => somme + l.nb_dpe, 0);
  const parEtiquette: Point[] = ETIQUETTES.map(etiquette => {
    const nb = dansArrondissement
      .filter(l => l.etiquette_dpe === etiquette)
      .reduce((somme, l) => somme + l.nb_dpe, 0);
    return { nom: etiquette, valeur: nb, detail: total ? formatPourcentage((100 * nb) / total) : undefined };
  });

  // Part de passoires par arrondissement : tous les arrondissements, celui choisi en emphase
  const cumul = new Map<number, { total: number; passoires: number }>();
  for (const l of portee) {
    if (l.arrondissement === null) continue;
    const c = cumul.get(l.arrondissement) ?? { total: 0, passoires: 0 };
    c.total += l.nb_dpe;
    if (ETIQUETTES_PASSOIRES.includes(l.etiquette_dpe)) c.passoires += l.nb_dpe;
    cumul.set(l.arrondissement, c);
  }
  const passoires: Point[] = [...cumul.entries()]
    .map(([arr, c]) => ({
      nom: libelleArrondissement(arr),
      valeur: (100 * c.passoires) / c.total,
      detail: `${formatEntier(c.passoires)} sur ${formatEntier(c.total)} DPE`,
      couleur: arrondissement === null || arrondissement === arr ? COULEURS.slot1 : COULEURS.axe,
    }))
    .sort((a, b) => b.valeur - a.valeur);

  const perimetre = arrondissement === null ? 'Paris' : `Paris ${libelleArrondissement(arrondissement)}`;

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
        sousTitre={`${perimetre} · ${formatEntier(total)} DPE`}
      >
        <Colonnes
          points={parEtiquette}
          colonneNom="Étiquette"
          colonneValeur="DPE"
          colonneDetail="Part"
          formater={formatEntier}
          mode={mode}
        />
      </CarteGraphique>

      <CarteGraphique
        titre="Part de passoires par arrondissement"
        sousTitre={
          arrondissement === null
            ? 'Étiquettes F et G, sur l’ensemble des DPE de l’arrondissement'
            : `Étiquettes F et G · ${perimetre} en bleu, les autres arrondissements en gris`
        }
      >
        <BarresHorizontales
          points={passoires}
          colonneNom="Arrondissement"
          colonneValeur="Part de passoires"
          colonneDetail="DPE"
          formater={formatPourcentage}
          mode={mode}
        />
      </CarteGraphique>

      <p className="text-xs text-gray-500">
        DPE des logements existants établis depuis juillet 2021 (ADEME). Chauffage « électrique » : énergie
        principale de chauffage.
      </p>
    </div>
  );
}
