// ============================================================================
// Classes DPE
// ============================================================================

export const CLASSES_DPE = ['A', 'B', 'C', 'D', 'E', 'F', 'G'] as const;

// Graphiques empilés : 5 groupes de classes, rampe ordinale du bleu (le plus clair = le plus économe).
// Au-delà de 5 teintes, les pas de la rampe sont trop serrés pour passer le contrôle de clarté du guide.
export interface GroupeEtiquette {
  id: string;
  libelle: string;
  etiquettes: readonly string[];
  couleur: string;
}

export const GROUPES_ETIQUETTE: GroupeEtiquette[] = [
  { id: 'AB', libelle: 'A–B', etiquettes: ['A', 'B'], couleur: '#86b6ef' },
  { id: 'C', libelle: 'C', etiquettes: ['C'], couleur: '#5598e7' },
  { id: 'D', libelle: 'D', etiquettes: ['D'], couleur: '#2a78d6' },
  { id: 'E', libelle: 'E', etiquettes: ['E'], couleur: '#1c5cab' },
  { id: 'FG', libelle: 'F–G', etiquettes: ['F', 'G'], couleur: '#104281' },
];

export function groupeEtiquette(lettre: string): GroupeEtiquette | undefined {
  return GROUPES_ETIQUETTE.find(g => g.etiquettes.includes(lettre));
}

// ============================================================================
// Périodes de construction (ordre chronologique : le tri alphabétique les mélangerait)
// ============================================================================

export const PERIODES = [
  'avant 1948', '1948-1974', '1975-1977', '1978-1982', '1983-1988',
  '1989-2000', '2001-2005', '2006-2012', '2013-2021', 'après 2021',
];

export function ordrePeriode(periode: string | null): number {
  const rang = periode === null ? -1 : PERIODES.indexOf(periode);
  return rang === -1 ? PERIODES.length : rang;
}

export function libellePeriode(periode: string | null): string {
  return periode === null ? 'Inconnue' : majuscule(periode);
}

// ============================================================================
// Énergie de chauffage (les modalités marginales sont regroupées)
// ============================================================================

const LIBELLES_ENERGIE: Record<string, string> = {
  electricite: 'Électricité',
  gaz: 'Gaz',
  'reseau de chaleur': 'Réseau de chaleur',
  fioul: 'Fioul',
  'non renseigné': 'Non renseigné',
};

// GPL, bois, solaire, charbon : 0,14 % des DPE à eux quatre
export const LIBELLE_ENERGIE_AUTRES = 'Autres';

export function libelleEnergie(energie: string): string {
  return LIBELLES_ENERGIE[energie] ?? LIBELLE_ENERGIE_AUTRES;
}

// ============================================================================
// Postes de déperdition : catégoriel, slots 1 à 6 dans l'ordre fixe de la palette (empilement dans cet ordre)
// ============================================================================

export const POSTES: { id: string; libelle: string; couleur: string }[] = [
  { id: 'murs', libelle: 'Murs', couleur: '#2a78d6' },
  { id: 'baies_vitrees', libelle: 'Baies vitrées', couleur: '#eb6834' },
  { id: 'plancher_bas', libelle: 'Plancher bas', couleur: '#1baf7a' },
  { id: 'plancher_haut', libelle: 'Plancher haut', couleur: '#eda100' },
  { id: 'ponts_thermiques', libelle: 'Ponts thermiques', couleur: '#e87ba4' },
  { id: 'portes', libelle: 'Portes', couleur: '#008300' },
];

// ============================================================================
// Géocodage
// ============================================================================

export function majuscule(texte: string): string {
  return texte.charAt(0).toUpperCase() + texte.slice(1);
}

export function libelleFiabilite(fiabilite: string): string {
  return majuscule(fiabilite);
}

// « rnb + parcelle + adresse » devient « RNB + parcelle + adresse »
export function libelleAppariement(appariement: string): string {
  return majuscule(appariement.replace(/\brnb\b/g, 'RNB'));
}
