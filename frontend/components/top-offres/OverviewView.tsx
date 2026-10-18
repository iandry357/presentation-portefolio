'use client';

import { useCallback, useEffect, useState } from 'react';
import { getTopStats } from '@/lib/api';
import { cn } from '@/lib/utils';
import { TopStatsResponse } from '@/types';
import {
  LIBELLES_ANNONCEUR,
  LIBELLES_CATEGORIE,
  calculerTuiles,
  formatDateCourte,
  libelle,
  libelleCible,
  ordonner,
  repartition,
  serieParJour,
  topN,
} from '@/lib/topOffres';
import {
  BarreRepartition,
  BarresHorizontales,
  CarteGraphique,
  COULEURS,
  ColonnesParJour,
  ModeAffichage,
} from './TopCharts';

// Paramètres
const PERIODES = [7, 14, 30];
const JOURS_DEFAUT = 7;
const NB_SECTEURS = 8;

// Les catégories sont ordonnées (cœur > adjacent > hors cible) : rampe ordinale du bleu
const COULEUR_CATEGORIE: Record<string, string> = {
  coeur: COULEURS.ordinal500,
  adjacent: COULEURS.ordinal350,
  hors_cible: COULEURS.ordinal250,
};

// Les types d'annonceur sont nominaux : couleurs catégorielles ; « inconnu » en gris discret
const COULEUR_ANNONCEUR: Record<string, string> = {
  employeur_direct: COULEURS.slot1,
  intermediaire: COULEURS.slot2,
};

function Tuile({
  label,
  valeur,
  ecart,
  unite = '',
  uniteEcart = '',
  info,
}: {
  label: string;
  valeur: number;
  ecart: number | null;
  unite?: string;
  uniteEcart?: string;
  info?: string;
}) {
  const fleche = ecart === null || ecart === 0 ? '=' : ecart > 0 ? '▲' : '▼';
  const signe = ecart !== null && ecart > 0 ? '+' : '';
  return (
    <div className="border rounded-lg bg-white p-4" title={info}>
      <p className="text-sm text-gray-500">{label}</p>
      <p className="text-3xl font-semibold text-gray-900 mt-1">
        {valeur.toLocaleString('fr-FR')}
        {unite}
      </p>
      <p className="text-xs text-gray-500 mt-1">
        {ecart === null
          ? 'Pas de jour précédent'
          : `${fleche} ${signe}${ecart}${uniteEcart} vs jour précédent`}
      </p>
    </div>
  );
}

export default function OverviewView() {
  const [jours, setJours] = useState(JOURS_DEFAUT);
  const [mode, setMode] = useState<ModeAffichage>('graphique');
  const [data, setData] = useState<TopStatsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await getTopStats(jours));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erreur de chargement');
    } finally {
      setLoading(false);
    }
  }, [jours]);

  useEffect(() => {
    load();
  }, [load]);

  const lignes = data?.lignes ?? [];
  const cibles = data?.cibles ?? {};

  const serie = serieParJour(lignes);
  const tuiles = calculerTuiles(serie);

  const categories = ordonner(repartition(lignes, 'categorie'), [
    'coeur',
    'adjacent',
    'hors_cible',
    'inconnu',
  ]).map(p => ({
    nom: libelle(LIBELLES_CATEGORIE, p.valeur),
    nb: p.nb,
    couleur: COULEUR_CATEGORIE[p.valeur] ?? COULEURS.texteDiscret,
  }));

  const annonceurs = ordonner(repartition(lignes, 'type_annonceur'), [
    'employeur_direct',
    'intermediaire',
    'inconnu',
  ]).map(p => ({
    nom: libelle(LIBELLES_ANNONCEUR, p.valeur),
    nb: p.nb,
    couleur: COULEUR_ANNONCEUR[p.valeur] ?? COULEURS.texteDiscret,
  }));

  const parCible = repartition(lignes, 'cible').map(p => ({
    nom: p.valeur === 'inconnu' ? 'Inconnue' : libelleCible(p.valeur, cibles),
    nb: p.nb,
    couleur: COULEURS.slot1,
  }));

  const secteurs = topN(repartition(lignes, 'naf_libelle'), NB_SECTEURS).map(p => ({
    nom: p.valeur === 'inconnu' ? 'Inconnu' : p.valeur,
    nb: p.nb,
    couleur: p.valeur === 'Autres' ? COULEURS.texteDiscret : COULEURS.slot1,
  }));

  return (
    <div className="space-y-6">

      {/* Filtres : une seule ligne, au-dessus de ce qu'ils portent */}
      <div className="flex flex-wrap items-center gap-4 text-sm text-gray-600">
        <label className="inline-flex items-center gap-2">
          Période
          <select
            value={jours}
            onChange={e => setJours(Number(e.target.value))}
            className="text-sm border border-gray-200 rounded px-2 py-1 bg-white text-gray-700"
          >
            {PERIODES.map(j => (
              <option key={j} value={j}>{j} jours</option>
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

      {error && (
        <div className="text-sm text-red-600 bg-red-50 px-4 py-3 rounded-lg">{error}</div>
      )}

      {!data && loading && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map(i => (
            <div key={i} className="h-24 border rounded-lg bg-white animate-pulse" />
          ))}
        </div>
      )}

      {data && (
        // Pendant un rechargement, le contenu précédent reste affiché en atténué
        <div className={cn('space-y-6 transition-opacity', loading && 'opacity-60')}>

          {/* Tuiles : dernier jour collecté */}
          <div>
            <p className="text-xs text-gray-500 mb-2">
              {tuiles.jour ? `Collecte du ${formatDateCourte(tuiles.jour)}` : 'Aucune collecte sur la période'}
            </p>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              <Tuile label="À lire" valeur={tuiles.aLire.valeur} ecart={tuiles.aLire.ecart} />
              <Tuile label="Zone grise" valeur={tuiles.zoneGrise.valeur} ecart={tuiles.zoneGrise.ecart} />
              <Tuile
                label="Masquées"
                valeur={tuiles.masquees.valeur}
                ecart={tuiles.masquees.ecart}
                info="Filtre dur (stage, alternance, hors Île-de-France), score bas ou entreprise exclue"
              />
              <Tuile
                label="Taux retenu"
                valeur={tuiles.tauxRetenu.valeur}
                ecart={tuiles.tauxRetenu.ecart}
                unite=" %"
                uniteEcart=" pt"
                info="(À lire + zone grise) sur le total des offres du jour"
              />
            </div>
          </div>

          <CarteGraphique
            titre="À lire et zone grise par jour"
            sousTitre="Offres retenues, par jour de collecte"
          >
            <ColonnesParJour serie={serie} mode={mode} />
          </CarteGraphique>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <CarteGraphique
              titre="Catégorie des offres scorées"
              sousTitre="Cœur, adjacent ou hors cible, selon le LLM"
            >
              <BarresHorizontales barres={categories} colonneNom="Catégorie" mode={mode} />
            </CarteGraphique>

            <CarteGraphique
              titre="Type d'annonceur"
              sousTitre="Employeur direct ou intermédiaire (cabinet, ESN)"
            >
              <BarreRepartition parts={annonceurs} mode={mode} />
            </CarteGraphique>

            <CarteGraphique
              titre="Cible la plus proche"
              sousTitre="Cible de poste dont le titre se rapproche le plus"
            >
              <BarresHorizontales barres={parCible} colonneNom="Cible" mode={mode} />
            </CarteGraphique>

            <CarteGraphique
              titre="Secteurs"
              sousTitre={`Section NAF de l'entreprise, ${NB_SECTEURS} premiers`}
            >
              <BarresHorizontales barres={secteurs} colonneNom="Secteur" mode={mode} />
            </CarteGraphique>
          </div>

          <p className="text-xs text-gray-500">
            Chiffres issus des offres scorées, par jour de collecte, depuis le premier passage du pipeline.
          </p>
        </div>
      )}
    </div>
  );
}
