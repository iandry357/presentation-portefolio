import type { CubeOrg } from '@/lib/immobilierOrgApi';
import { formatMois } from '@/lib/immobilierOrg';

// ============================================================================
// Paramètres
// ============================================================================

export const NON_RENSEIGNE = 'non renseigné';   // valeur renvoyée par l'API
export const PIECES_PLAFOND = 6;                // pipeline/organisation/config.py (PIECES_MAX) : 6 = « 6 et plus »
export const SEUIL_VENTES_FIABLES = 30;         // un groupe de moins de N ventes est à lire avec prudence

// Périodes de construction dans l'ordre chronologique (l'API les renvoie par ordre alphabétique)
const PERIODES_CONSTRUCTION = [
  'avant 1948', '1948-1974', '1975-1977', '1978-1982', '1983-1988',
  '1989-2000', '2001-2005', '2006-2012', '2013-2021', 'après 2021',
];

// ============================================================================
// Configuration des cubes (miroir de backend/app/services/immobilier_org_cubes.py)
// ============================================================================

export interface ConfigCube {
  libelle: string;
  unite: string;                 // ce que compte le cube : ventes, DPE, immeubles
  axeDefaut: string;
  dimensions: string[];          // dimensions proposées, dans l'ordre des sélecteurs
  source: string;                // pied de page
  explication: string[];         // détails de calcul (paragraphes)
}

export const CUBES_ORG: Record<CubeOrg, ConfigCube> = {
  dvf: {
    libelle: 'Ventes',
    unite: 'ventes',
    axeDefaut: 'pieces',
    dimensions: ['pieces', 'arrondissement', 'type_local', 'tranche_surface', 'mois'],
    source: 'Ventes : DVF (Etalab), livraison la plus récente.',
    explication: [
      'Ventes de logement du DVF (Etalab) : une vente d’un seul logement (appartement ou maison), sans local commercial.',
      'Le prix au m² est le prix de vente divisé par la surface bâtie déclarée (et non la surface Carrez des annonces). Le prix médian est la valeur du milieu : la moitié des ventes en dessous, l’autre moitié au-dessus. Le détail de chaque barre donne aussi la fourchette qui contient la moitié des ventes « du milieu ».',
    ],
  },
  dpe: {
    libelle: 'Diagnostics',
    unite: 'DPE',
    axeDefaut: 'etiquette',
    dimensions: ['etiquette', 'niveau_dpe', 'type_batiment', 'periode_construction', 'chauffage', 'arrondissement', 'mois'],
    source: 'DPE : ADEME, tous les diagnostics de Paris de la période commune.',
    explication: [
      'Diagnostics de performance énergétique de l’ADEME, un diagnostic par ligne, établis pendant la période commune. L’étiquette est celle du logement diagnostiqué.',
      'Niveau : « logement individuel » (DPE établi pour le logement), « logement déduit de l’immeuble » (DPE généré à partir du DPE de l’immeuble) ou « immeuble » (DPE d’un immeuble collectif).',
      'Un DPE est établi à la vente, à la location ou pour un logement neuf : ce sont des logements diagnostiqués, pas tout le parc parisien. Un DPE qui en remplace un autre en indique l’ancien numéro ; l’ancien DPE est le plus souvent absent du jeu.',
    ],
  },
  batiment: {
    libelle: 'Immeubles',
    unite: 'immeubles',
    axeDefaut: 'epoque_ff',
    dimensions: ['epoque_ff', 'usage_batiment', 'taille_copro', 'inondation', 'patrimoine', 'arrondissement'],
    source: 'Immeubles : BDNB (CSTB), état du parc au millésime.',
    explication: [
      'Immeubles de la BDNB (CSTB) à Paris : un état du parc au millésime de la base, sans date de transaction, donc sans période.',
      'Époque de construction : Fichiers fonciers (souvent arrondie à la décennie dans le parc ancien). Copropriétés : registre national (« hors registre » veut dire absent du registre, pas forcément sans copropriété). Inondation par débordement de cours d’eau, monument historique et bâti patrimonial viennent des plans locaux d’urbanisme et des bases nationales.',
    ],
  },
  croise_ventes: {
    libelle: 'Ventes reliées aux immeubles',
    unite: 'ventes',
    axeDefaut: 'pieces',
    dimensions: [
      'pieces', 'etiquette', 'arrondissement', 'tranche_surface', 'mois', 'rattachee',
      'epoque_ff', 'taille_copro', 'inondation', 'patrimoine', 'usage_batiment',
    ],
    source: 'Ventes : DVF (Etalab). Immeubles et étiquettes : BDNB (CSTB) et DPE de la BDNB.',
    explication: [
      'Ventes de logement du DVF (Etalab) reliées à un immeuble de la BDNB par sa parcelle cadastrale ou son adresse.',
      'L’étiquette d’un immeuble est la note médiane des DPE de ses logements (quand le nombre de DPE est pair, on retient la meilleure des deux notes centrales). Ce n’est pas la note du logement vendu. « Inconnue » : vente non reliée à un immeuble, ou immeuble sans DPE.',
      'Les DPE de ce croisement sont ceux de la BDNB, pas ceux de la partie DPE (ADEME) : les deux populations diffèrent (voir la partie Qualité).',
    ],
  },
  croise_dpe: {
    libelle: 'Diagnostics reliés aux immeubles',
    unite: 'DPE',
    axeDefaut: 'etiquette',
    dimensions: ['etiquette', 'pieces', 'arrondissement', 'tranche_surface', 'mois'],
    source: 'DPE : BDNB (CSTB), assemblés à partir des données de l’ADEME. Nombre de pièces : typologie ADEME.',
    explication: [
      'DPE de la BDNB reliés à un immeuble, établis pendant la période commune jusqu’au millésime de la base. Population différente de la partie DPE (ADEME).',
      'Le nombre de pièces vient de la typologie (T1, T2, T3…) que le diagnostiqueur peut renseigner : elle est déclarative et rarement renseignée.',
    ],
  },
};

// ============================================================================
// Libellés
// ============================================================================

export function majuscule(texte: string): string {
  return texte.charAt(0).toUpperCase() + texte.slice(1);
}

// Première lettre en minuscule, le reste intact : « Étiquette du logement » devient « étiquette du logement »
export function minuscule(texte: string): string {
  return texte.charAt(0).toLowerCase() + texte.slice(1);
}

export function libelleDimensionOrg(dimension: string, cube: CubeOrg): string {
  switch (dimension) {
    case 'mois': return 'Mois';
    case 'arrondissement': return 'Arrondissement';
    case 'type_local': return 'Type de logement';
    case 'pieces': return 'Nombre de pièces';
    case 'tranche_surface': return 'Surface';
    case 'etiquette': return cube === 'croise_ventes' ? 'Étiquette de l’immeuble' : 'Étiquette du logement';
    case 'rattachee': return 'Immeuble identifié';
    case 'epoque_ff': return 'Époque de construction';
    case 'taille_copro': return 'Taille de la copropriété';
    case 'inondation': return 'Inondation par débordement';
    case 'patrimoine': return 'Patrimoine';
    case 'usage_batiment': return 'Usage de l’immeuble';
    case 'niveau_dpe': return 'Niveau du DPE';
    case 'type_batiment': return 'Type de bâtiment';
    case 'periode_construction': return 'Période de construction';
    case 'chauffage': return 'Chauffage';
    default: return dimension;
  }
}
// Explication d'une dimension, en langage d'agent ; elle dépend du cube quand la même dimension n'y veut pas dire la même chose
export function descriptionDimensionOrg(dimension: string, cube: CubeOrg): string {
  const ventes = cube === 'dvf' || cube === 'croise_ventes';
  switch (dimension) {
    case 'mois':
      return ventes ? 'Mois de la vente.' : 'Mois d’établissement du diagnostic.';
    case 'arrondissement':
      return cube === 'batiment' ? 'Arrondissement de Paris (1 à 20) où se situe l’immeuble.' : 'Arrondissement de Paris (1 à 20) où se situe le logement.';
    case 'type_local':
      return 'Appartement ou maison.';
    case 'pieces':
      return ventes
        ? 'Nombre de pièces principales du logement vendu (6 = six pièces et plus).'
        : 'Nombre de pièces d’après la typologie du diagnostic (T1, T2, T3…) : elle est déclarative et rarement renseignée.';
    case 'tranche_surface':
      return ventes
        ? 'Surface bâtie déclarée du logement vendu, par tranche : moins de 25 m², 25 à 40, 40 à 60, 60 à 80, 80 à 120, 120 et plus.'
        : 'Surface habitable du logement diagnostiqué, par tranche : moins de 25 m², 25 à 40, 40 à 60, 60 à 80, 80 à 120, 120 et plus.';
    case 'etiquette':
      if (cube === 'croise_ventes') {
        return 'Note de l’immeuble où a eu lieu la vente : note médiane des diagnostics de ses logements, de A (très économe) à G (très énergivore). « Inconnue » : vente non reliée à un immeuble, ou immeuble sans diagnostic.';
      }
      return 'Lettre du diagnostic du logement, de A (très économe) à G (très énergivore). F et G sont les « passoires thermiques ».';
    case 'rattachee':
      return 'Dit si la vente a pu être reliée à un immeuble de la base nationale des bâtiments. Sans ce lien, on ne connaît ni la note ni les caractéristiques de l’immeuble.';
    case 'epoque_ff':
      return 'Époque de construction de l’immeuble : avant 1946, 1946-1970, 1971-1990, après 1990 (d’après l’année des Fichiers fonciers).';
    case 'taille_copro':
      return 'Taille de la copropriété de l’immeuble, en nombre de logements. « Hors registre » : l’immeuble ne figure pas au registre national des copropriétés.';
    case 'inondation':
      return 'Risque d’inondation par débordement de cours d’eau autour de l’immeuble : aucun, faible, moyen ou fort.';
    case 'patrimoine':
      return 'Immeuble classé monument historique, immeuble en périmètre de bâti patrimonial d’un plan local d’urbanisme, ou aucun des deux.';
    case 'usage_batiment':
      return 'Usage principal de l’immeuble (Fichiers fonciers).';
    case 'niveau_dpe':
      return 'Diagnostic « logement individuel » (fait pour le logement), « logement déduit de l’immeuble » (calculé à partir du diagnostic de l’immeuble, sans visite du logement) ou « immeuble » (immeuble collectif).';
    case 'type_batiment':
      return 'Type de bâtiment indiqué dans le diagnostic : appartement, maison ou immeuble.';
    case 'periode_construction':
      return 'Période de construction du bâtiment indiquée dans le diagnostic (avant 1948, 1948-1974…).';
    case 'chauffage':
      return 'Chauffage principal électrique ou autre énergie (gaz, fioul, réseau de chaleur…).';
    default:
      return '';
  }
}

export function libelleModaliteOrg(dimension: string, valeur: string): string {
  if (dimension === 'taille_copro' && valeur === NON_RENSEIGNE) return 'Hors registre des copropriétés';
  if (valeur === NON_RENSEIGNE) return majuscule(valeur);
  switch (dimension) {
    case 'mois':
      return formatMois(valeur);
    case 'pieces':
      return Number(valeur) >= PIECES_PLAFOND ? `${valeur} pièces et plus` : `${valeur} pièce${valeur === '1' ? '' : 's'}`;
    case 'arrondissement':
      return valeur === '1' ? '1er' : `${valeur}e`;
    case 'tranche_surface': {
      const texte = majuscule(valeur.replace(/^\d\s+/, ''));   // rang de tri retiré
      return texte.endsWith(' et plus') ? texte.replace(' et plus', ' m² et plus') : `${texte} m²`;
    }
    case 'rattachee':
      return valeur === 'oui' ? 'Oui' : 'Non';
    case 'epoque_ff':
      return majuscule(valeur.replace(/^\d\s+/, '')).replace('Apres', 'Après');   // rang de tri retiré
    case 'taille_copro': {
      const texte = majuscule(valeur.replace(/^\d\s+/, ''));   // rang de tri retiré
      return texte.endsWith(' et plus') ? texte.replace(' et plus', ' logements et plus') : `${texte} logements`;
    }
    case 'usage_batiment':
      return valeur;
    default:
      return majuscule(valeur);   // étiquettes A à G ou « inconnue », niveau, type, période, chauffage, inondation, patrimoine, type de logement
  }
}

// ============================================================================
// Ordre d'affichage
// ============================================================================

// Rang d'une modalité : l'API trie par ordre alphabétique, sauf les périodes de construction qui suivent le temps
export function ordreModalite(dimension: string, valeur: string): number {
  if (dimension !== 'periode_construction') return 0;
  const rang = PERIODES_CONSTRUCTION.indexOf(valeur);
  return rang === -1 ? PERIODES_CONSTRUCTION.length : rang;
}

export function trierModalites(dimension: string, valeurs: string[]): string[] {
  return [...valeurs].sort((a, b) => ordreModalite(dimension, a) - ordreModalite(dimension, b));
}

// Cellules dans l'ordre d'affichage (tri stable : l'ordre de l'API est gardé à rang égal)
export function trierCellules<T extends { modalites: string[] }>(axes: string[], cellules: T[]): T[] {
  return [...cellules].sort((a, b) => {
    for (let i = 0; i < axes.length; i++) {
      const ecart = ordreModalite(axes[i], a.modalites[i]) - ordreModalite(axes[i], b.modalites[i]);
      if (ecart !== 0) return ecart;
    }
    return 0;
  });
}
