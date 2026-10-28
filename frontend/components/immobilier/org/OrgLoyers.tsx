'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { useAccess } from '@/components/AccessProvider';
import { cn } from '@/lib/utils';
import {
  DimensionLoyersOrg, FiltresOrg, OrgLoyersCellule, OrgLoyersMeta, OrgLoyersResponse, getOrgLoyers,
} from '@/lib/immobilierOrgApi';
import { SEUIL_VENTES_FIABLES, libelleModaliteOrg, minuscule } from '@/lib/immobilierOrgCubes';
import { formatMois } from '@/lib/immobilierOrg';
import { telechargerCsv } from '@/lib/immobilierOrgCsv';
import { formatEntier, formatPourcentage } from '@/lib/immobilier';
import {
  BarresHorizontales, CarteGraphique, COULEURS, Colonnes, Explication, ModeAffichage, Point,
} from '../ImmobilierCharts';
import Lecture from '../bdnb/Lecture';

// Paramètres
type MesureLoyers = 'loyer' | 'rendement';
const MESURE_DEFAUT: MesureLoyers = 'loyer';
const AXE_DEFAUT: DimensionLoyersOrg = 'arrondissement';
const AXES: DimensionLoyersOrg[] = ['arrondissement', 'pieces', 'epoque', 'mois'];
const TOUS_ARRETES = 'tous';
const PIECES_PLAFOND_LOYERS = 4;   // pipeline/loyers/config.py (PIECES_MAX) : 4 = « 4 pièces et plus »
// Époques de l'encadrement dans l'ordre chronologique (l'API les renvoie par ordre alphabétique)
const EPOQUES = ['Avant 1946', '1946-1970', '1971-1990', 'Apres 1990'];
const SEUIL_BARRES_HORIZONTALES = 8;   // au-delà, les libellés en colonnes ne tiennent plus sur un écran étroit
const COULEUR_FRAGILE = COULEURS.grille;
const MESURES: { id: MesureLoyers; libelle: string }[] = [
  { id: 'loyer', libelle: 'Loyer de référence' },
  { id: 'rendement', libelle: 'Rendement brut' },
];
const DECIMAL = new Intl.NumberFormat('fr-FR', { minimumFractionDigits: 1, maximumFractionDigits: 1 });

// ============================================================================
// Libellés et textes
// ============================================================================

const formatDecimal = (valeur: number) => DECIMAL.format(valeur);
const formatLoyer = (valeur: number) => `${formatDecimal(valeur)} €/m²`;

function ordreEpoque(epoque: string): number {
  const rang = EPOQUES.indexOf(epoque);
  return rang === -1 ? EPOQUES.length : rang;
}

function libelleDimension(dimension: DimensionLoyersOrg): string {
  switch (dimension) {
    case 'arrondissement': return 'Arrondissement';
    case 'pieces': return 'Nombre de pièces';
    case 'epoque': return 'Époque de construction';
    case 'mois': return 'Mois de la vente';
    case 'annee_loyer': return 'Arrêté de loyers';
  }
}

function descriptionDimension(dimension: DimensionLoyersOrg): string {
  switch (dimension) {
    case 'arrondissement': return 'Arrondissement de Paris (1 à 20) où se situe le logement vendu.';
    case 'pieces': return 'Nombre de pièces du logement vendu, qui détermine son loyer de référence (1 à 4 ; 4 = quatre pièces et plus).';
    case 'epoque': return 'Époque de construction retenue par l’encadrement des loyers : avant 1946, 1946-1970, 1971-1990, après 1990.';
    case 'mois': return 'Mois de la vente.';
    case 'annee_loyer': return 'Arrêté de loyers en vigueur à la date de la vente (un arrêté court du 1er juillet au 30 juin).';
  }
}

function libelleModalite(dimension: DimensionLoyersOrg, valeur: string): string {
  switch (dimension) {
    case 'pieces':
      return Number(valeur) >= PIECES_PLAFOND_LOYERS ? `${valeur} pièces et plus` : `${valeur} pièce${valeur === '1' ? '' : 's'}`;
    case 'epoque':
      return valeur.replace('Apres', 'Après');
    case 'annee_loyer':
      return valeur;
    default:
      return libelleModaliteOrg(dimension, valeur);   // mois, arrondissement
  }
}

// Part des ventes à l'époque ambiguë, pondérée par les ventes des groupes affichés
function partEpoqueAmbigue(cellules: OrgLoyersCellule[]): number | null {
  const total = cellules.reduce((somme, c) => somme + c.n, 0);
  if (!total) return null;
  return cellules.reduce((somme, c) => somme + c.n * c.part_epoque_ambigue_pct, 0) / total;
}

function alerteEpoque(part: number): string {
  return (
    `Pour ${formatPourcentage(part)} de ces ventes, l’époque de construction du logement est incertaine : elle se déduit des DPE ` +
    'de l’immeuble, dont les périodes ne coïncident pas avec celles de l’encadrement des loyers (surtout dans le parc ancien). ' +
    'Le loyer de référence est donc un ordre de grandeur pour l’immeuble, pas la valeur exacte du logement vendu.'
  );
}

function alerteMillesimes(annees: number[]): string {
  return (
    `Chaque vente est comparée au loyer de l’arrêté en vigueur à sa date : les arrêtés ${Math.min(...annees)} à ${Math.max(...annees)} ` +
    'sont ici mélangés. Les loyers de référence ont évolué : choisissez un arrêté pour une lecture à une date donnée.'
  );
}

function voirLoyers(mesure: MesureLoyers, axe: string, meuble: boolean): string {
  const statut = meuble ? 'meublés' : 'non meublés';
  return mesure === 'loyer'
    ? `Le loyer de référence de l’encadrement des loyers de Paris (€ par m² et par mois, logements ${statut}), selon ${minuscule(axe)}, pour les logements vendus. ` +
      'Ce n’est pas un loyer constaté : c’est le repère fixé par l’arrêté pour le quartier, le nombre de pièces et l’époque.'
    : `Le rendement brut théorique d’un achat loué au loyer de référence (logements ${statut}) : loyer × surface × 12 ÷ prix d’achat, ` +
      `médiane des ventes, selon ${minuscule(axe)}.`;
}

function valeurMesure(c: OrgLoyersCellule, mesure: MesureLoyers): number | null {
  return mesure === 'loyer' ? c.loyer_reference : c.rendement_reference_pct;
}

function retenirLoyers(cellules: OrgLoyersCellule[], axe: DimensionLoyersOrg, mesure: MesureLoyers): string | null {
  const fiables = cellules.filter(c => c.n >= SEUIL_VENTES_FIABLES && valeurMesure(c, mesure) !== null);
  if (fiables.length < 2) return null;
  const bas = fiables.reduce((a, b) => ((valeurMesure(b, mesure) as number) < (valeurMesure(a, mesure) as number) ? b : a));
  const haut = fiables.reduce((a, b) => ((valeurMesure(b, mesure) as number) > (valeurMesure(a, mesure) as number) ? b : a));
  const nom = (c: OrgLoyersCellule) => libelleModalite(axe, c.modalites[0]);
  return mesure === 'loyer'
    ? `Le loyer de référence va de ${formatLoyer(valeurMesure(bas, mesure) as number)} (${nom(bas)}) à ${formatLoyer(valeurMesure(haut, mesure) as number)} (${nom(haut)}) par mois.`
    : `Le rendement brut central va de ${formatPourcentage(valeurMesure(bas, mesure) as number)} (${nom(bas)}) à ${formatPourcentage(valeurMesure(haut, mesure) as number)} (${nom(haut)}).`;
}

function attentionLoyers(cellules: OrgLoyersCellule[], axe: DimensionLoyersOrg, mesure: MesureLoyers): string {
  const base =
    mesure === 'rendement'
      ? 'Ce rendement est brut et théorique : il ne tient compte ni des charges, ni de la vacance, ni de la taxe foncière, ni des travaux. La borne haute suppose un loyer au plafond (loyer majoré).'
      : 'Le loyer de référence est un repère de l’encadrement, pas un loyer constaté ; le plafond légal est le loyer majoré (+20 %).';
  const fragiles = cellules.filter(c => c.n < SEUIL_VENTES_FIABLES);
  if (fragiles.length === 0) return base;
  const detail = fragiles.map(c => `${libelleModalite(axe, c.modalites[0])} (${formatEntier(c.n)} ventes)`).join(', ');
  return `${base} Peu de ventes pour ${detail} : à lire avec prudence.`;
}

// ============================================================================
// Composants
// ============================================================================

function Bandeau({ children, ton = 'neutre' }: { children: ReactNode; ton?: 'neutre' | 'alerte' }) {
  return (
    <p
      className={cn(
        'text-sm border rounded-lg px-4 py-3',
        ton === 'alerte' ? 'text-amber-800 bg-amber-50 border-amber-200' : 'text-gray-600 bg-gray-50',
      )}
    >
      {children}
    </p>
  );
}

function Selecteur({
  libelle,
  valeur,
  options,
  onChange,
  aide,
}: {
  libelle: string;
  valeur: string;
  options: { id: string; libelle: string }[];
  onChange: (valeur: string) => void;
  aide: string;
}) {
  return (
    <label className="block text-sm text-gray-600">
      {libelle}
      <select
        value={valeur}
        onChange={e => onChange(e.target.value)}
        className="mt-1 w-full border rounded-lg bg-white px-3 py-2 text-sm text-gray-700"
      >
        {options.map(o => (
          <option key={o.id} value={o.id}>
            {o.libelle}
          </option>
        ))}
      </select>
      <span className="block mt-1 text-xs text-gray-500">{aide}</span>
    </label>
  );
}

// Détail d'une barre : l'effectif et, selon la mesure, la fourchette légale ou la borne haute du rendement
function detailPoint(cellule: OrgLoyersCellule, mesure: MesureLoyers): string {
  const fragile = cellule.n < SEUIL_VENTES_FIABLES ? ' · à lire avec prudence' : '';
  const ventes = `${formatEntier(cellule.n)} ventes`;
  if (mesure === 'loyer') {
    const fourchette =
      cellule.loyer_minore !== null && cellule.loyer_majore !== null
        ? ` · minoré ${formatLoyer(cellule.loyer_minore)}, majoré ${formatLoyer(cellule.loyer_majore)}`
        : '';
    return `${ventes}${fourchette}${fragile}`;
  }
  const haute =
    cellule.rendement_majore_pct !== null ? ` · borne haute ${formatPourcentage(cellule.rendement_majore_pct)}` : '';
  const prix = cellule.prix_m2_median !== null ? ` · prix médian ${formatEntier(cellule.prix_m2_median)} €/m²` : '';
  return `${ventes}${haute}${prix}${fragile}`;
}

// Un arrêté s'applique du 1er juillet de l'année N au 30 juin de N+1
function libelleVentes(meta: OrgLoyersMeta, arrete: string | null): string {
  const statut = meta.meuble ? 'logements meublés' : 'logements non meublés';
  if (arrete !== null && arrete !== TOUS_ARRETES) {
    const annee = Number(arrete);
    return `Ventes du 1er juillet ${annee} au 30 juin ${annee + 1} · loyers de l’arrêté ${annee} · ${statut}`;
  }
  const periode = meta.mois_min && meta.mois_max ? `de ${formatMois(meta.mois_min)} à ${formatMois(meta.mois_max)}` : '';
  return `Ventes ${periode} · loyers des arrêtés ${Math.min(...meta.annees_loyer)} à ${Math.max(...meta.annees_loyer)} · ${statut}`;
}

export default function OrgLoyers() {
  const { unlocked } = useAccess();
  const [mesure, setMesure] = useState<MesureLoyers>(MESURE_DEFAUT);
  const [axe, setAxe] = useState<DimensionLoyersOrg>(AXE_DEFAUT);
  const [meuble, setMeuble] = useState(false);
  const [pieces, setPieces] = useState<string[]>([]);
  const [arrete, setArrete] = useState<string | null>(null);   // null : arrêté le plus récent pas encore connu
  const [mode, setMode] = useState<ModeAffichage>('graphique');
  // La réponse garde l'arrêté demandé : tant qu'il est null, la réponse sert seulement à connaître l'arrêté le plus récent
  const [data, setData] = useState<{ reponse: OrgLoyersResponse; arrete: string | null } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const derniereRequete = useRef(0);

  const load = useCallback(async () => {
    const numero = ++derniereRequete.current;
    setLoading(true);
    setError(null);
    const filtres: FiltresOrg = {};
    if (pieces.length > 0) filtres.pieces = pieces;
    if (arrete !== null && arrete !== TOUS_ARRETES) filtres.annee_loyer = [arrete];
    try {
      const reponse = await getOrgLoyers([axe], meuble, filtres);
      if (numero === derniereRequete.current) setData({ reponse, arrete });
    } catch (e) {
      if (numero === derniereRequete.current) setError(e instanceof Error ? e.message : 'Erreur de chargement');
    } finally {
      if (numero === derniereRequete.current) setLoading(false);
    }
  }, [axe, meuble, pieces, arrete]);

  // Relecture quand la sélection ou l'accès change : le seuil de 5 ne s'applique que verrouillé
  useEffect(() => {
    load();
  }, [load, unlocked]);

  // Arrêté le plus récent par défaut, connu dès la première réponse
  useEffect(() => {
    if (arrete === null && data) setArrete(String(Math.max(...data.reponse.meta.annees_loyer)));
  }, [arrete, data]);

  const basculerPieces = (valeur: string) =>
    setPieces(actuelles => (actuelles.includes(valeur) ? actuelles.filter(v => v !== valeur) : [...actuelles, valeur]));

  // Tout ce qui est affiché vient de la dernière réponse (meta), pas de la sélection en cours
  const reponse = data && data.arrete !== null ? data.reponse : null;
  const meta = reponse?.meta ?? null;
  const dimension = meta ? meta.axes[0] : axe;
  const cellules = reponse
    ? dimension === 'epoque'
      ? [...reponse.cellules].sort((a, b) => ordreEpoque(a.modalites[0]) - ordreEpoque(b.modalites[0]))
      : reponse.cellules
    : [];
  const partAmbigue = reponse ? partEpoqueAmbigue(reponse.cellules) : null;
  const arretes = meta ? [...(meta.modalites.annee_loyer ?? [])].reverse() : [];
  const piecesProposees = meta?.modalites.pieces ?? [];

  const points: Point[] = cellules.flatMap(c => {
    const valeur = valeurMesure(c, mesure);
    if (valeur === null) return [];
    return [{
      nom: libelleModalite(dimension, c.modalites[0]),
      valeur,
      detail: detailPoint(c, mesure),
      couleur: c.n < SEUIL_VENTES_FIABLES ? COULEUR_FRAGILE : COULEURS.slot1,
    }];
  });
  const avecFragile = cellules.some(c => c.n < SEUIL_VENTES_FIABLES);
  const proprietesGraphique = {
    points,
    colonneNom: libelleDimension(dimension),
    colonneValeur: mesure === 'loyer' ? 'Loyer de référence (€/m² par mois)' : 'Rendement brut central',
    colonneDetail: 'Détail',
    formater: mesure === 'loyer' ? formatDecimal : formatPourcentage,
    mode,
  };

  const telecharger = () =>
    telechargerCsv(
      `immobilier_loyers_${dimension}_${meuble ? 'meuble' : 'non_meuble'}.csv`,
      [
        libelleDimension(dimension), 'Ventes', 'Prix médian (€/m²)', 'Loyer de référence (€/m²/mois)',
        'Loyer minoré (€/m²/mois)', 'Loyer majoré (€/m²/mois)', 'Rendement de référence (%)', 'Rendement majoré (%)',
      ],
      cellules.map(c => [
        libelleModalite(dimension, c.modalites[0]), c.n, c.prix_m2_median, c.loyer_reference,
        c.loyer_minore, c.loyer_majore, c.rendement_reference_pct, c.rendement_majore_pct,
      ]),
    );

  return (
    <div className="space-y-6">
      <div className="border rounded-lg bg-white p-4 space-y-4">
        <div className="inline-flex overflow-hidden rounded border border-gray-200" role="group" aria-label="Mesure">
          {MESURES.map(({ id, libelle }) => (
            <button
              key={id}
              type="button"
              onClick={() => setMesure(id)}
              aria-pressed={mesure === id}
              className={cn(
                'px-4 py-1.5 text-sm transition-colors',
                mesure === id ? 'bg-blue-50 text-blue-700' : 'bg-white text-gray-600 hover:bg-gray-50',
              )}
            >
              {libelle}
            </button>
          ))}
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Selecteur
            libelle="Regrouper par"
            valeur={axe}
            options={AXES.map(d => ({ id: d, libelle: libelleDimension(d) }))}
            onChange={valeur => setAxe(valeur as DimensionLoyersOrg)}
            aide={descriptionDimension(axe)}
          />
          {arrete !== null && arretes.length > 0 && (
            <Selecteur
              libelle="Arrêté de loyers"
              valeur={arrete}
              options={[
                ...arretes.map(a => ({ id: a, libelle: `${a} (ventes de juillet ${a} à juin ${Number(a) + 1})` })),
                { id: TOUS_ARRETES, libelle: 'Tous les arrêtés' },
              ]}
              onChange={setArrete}
              aide={descriptionDimension('annee_loyer')}
            />
          )}
        </div>

        {piecesProposees.length > 0 && (
          <fieldset>
            <legend className="text-xs font-medium text-gray-500 mb-1">Nombre de pièces</legend>
            <div className="flex flex-wrap gap-1.5">
              {piecesProposees.map(valeur => {
                const actif = pieces.includes(valeur);
                return (
                  <button
                    key={valeur}
                    type="button"
                    onClick={() => basculerPieces(valeur)}
                    aria-pressed={actif}
                    className={cn(
                      'px-2.5 py-1 text-xs rounded-full border transition-colors',
                      actif
                        ? 'bg-blue-50 border-blue-300 text-blue-700'
                        : 'bg-white border-gray-200 text-gray-600 hover:bg-gray-50',
                    )}
                  >
                    {libelleModalite('pieces', valeur)}
                  </button>
                );
              })}
            </div>
          </fieldset>
        )}

        <label className="inline-flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
          <input
            type="checkbox"
            checked={meuble}
            onChange={e => setMeuble(e.target.checked)}
            className="w-4 h-4 rounded border-gray-300"
          />
          Logements meublés
        </label>
      </div>

      {error && <div className="text-sm text-red-600 bg-red-50 px-4 py-3 rounded-lg">{error}</div>}

      {!reponse && loading && <div className="h-64 border rounded-lg bg-white animate-pulse" />}

      {reponse && meta && (
        // Pendant un rechargement, le contenu précédent reste affiché en atténué
        <div className={cn('space-y-6 transition-opacity', loading && 'opacity-60')}>

          {partAmbigue !== null && <Bandeau ton="alerte">{alerteEpoque(partAmbigue)}</Bandeau>}

          {data?.arrete === TOUS_ARRETES && <Bandeau ton="alerte">{alerteMillesimes(meta.annees_loyer)}</Bandeau>}

          {meta.seuil_applique && meta.nb_masquees > 0 && (
            <Bandeau>
              {formatEntier(meta.nb_masquees)} regroupement{meta.nb_masquees > 1 ? 's' : ''} de moins de {meta.seuil} ventes
              {meta.nb_masquees > 1 ? ' sont masqués' : ' est masqué'}.
              Déverrouillez avec le bouton en haut de la page pour tout voir.
            </Bandeau>
          )}

          <CarteGraphique
            titre={`${mesure === 'loyer' ? 'Loyer de référence' : 'Rendement brut central'} par ${minuscule(libelleDimension(dimension))}`}
            sousTitre={`${libelleVentes(meta, data?.arrete ?? null)} · prix entre ${formatEntier(meta.prix_m2_min)} et ${formatEntier(meta.prix_m2_max)} €/m²`}
          >
            <Lecture
              voir={voirLoyers(mesure, libelleDimension(dimension), meta.meuble)}
              retenir={retenirLoyers(reponse.cellules, dimension, mesure)}
              attention={attentionLoyers(reponse.cellules, dimension, mesure)}
            />

            <Explication titre="Détails de calcul">
              <p>
                Loyers : encadrement des loyers de Paris ({meta.source_loyers}, licence {meta.licence_loyers}). Un loyer de
                référence est fixé par arrêté pour chacun des 80 quartiers, selon le nombre de pièces (1 à 4 ; 4 vaut
                « 4 pièces et plus »), l’époque de construction et le statut meublé ou non. Le loyer majoré est le
                plafond légal (référence +20 %), le loyer minoré le plancher (référence −30 %). Un arrêté s’applique du
                1er juillet au 30 juin de l’année suivante.
              </p>
              <p>
                Chaque vente du DVF (Etalab) est placée dans un quartier grâce à ses coordonnées, reçoit son nombre de
                pièces et l’époque de construction déduite des DPE de son immeuble (BDNB), puis le loyer de l’arrêté en
                vigueur à sa date. Les ventes qui n’ont pas pu être rattachées à un quartier ne figurent pas ici (voir la
                partie Qualité). Les prix hors de la fourchette de {formatEntier(meta.prix_m2_min)} à{' '}
                {formatEntier(meta.prix_m2_max)} €/m² sont écartés.
              </p>
              <p>
                Le loyer affiché est la médiane des loyers de référence des ventes du groupe. Le rendement brut d’une vente est
                le loyer de référence × surface × 12 ÷ prix de vente ; la barre donne la médiane des ventes du groupe, la
                borne haute la même médiane avec le loyer majoré. La surface est celle du DVF (surface bâtie), pas la
                surface habitable des annonces.
              </p>
              <p>
                Tant que l’accès est verrouillé, un regroupement de moins de {meta.seuil} ventes n’est pas affiché.
              </p>
            </Explication>

            <div className="flex flex-wrap items-center gap-4 mb-3 text-sm text-gray-600">
              <label className="inline-flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={mode === 'tableau'}
                  onChange={e => setMode(e.target.checked ? 'tableau' : 'graphique')}
                  className="w-4 h-4 rounded border-gray-300"
                />
                Voir en tableau
              </label>
              {cellules.length > 0 && (
                <button type="button" onClick={telecharger} className="text-blue-700 hover:underline">
                  Télécharger en CSV
                </button>
              )}
            </div>
            {avecFragile && (
              <p className="inline-flex items-center gap-1.5 mb-3 text-xs text-gray-600">
                <span className="inline-block w-3 h-3 rounded-sm" style={{ backgroundColor: COULEUR_FRAGILE }} />
                Moins de {SEUIL_VENTES_FIABLES} ventes : à lire avec prudence
              </p>
            )}
            {points.length > SEUIL_BARRES_HORIZONTALES
              ? <BarresHorizontales {...proprietesGraphique} />
              : <Colonnes {...proprietesGraphique} />}
          </CarteGraphique>

          <p className="text-xs text-gray-500">
            Loyers de référence : {meta.source_loyers}, licence {meta.licence_loyers}. Ventes : DVF (Etalab).
            Immeubles et époques : BDNB (CSTB) et DPE de la BDNB.
          </p>
        </div>
      )}
    </div>
  );
}
