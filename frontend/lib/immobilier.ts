import type { Chauffage } from '@/lib/immobilierApi';

// ============================================================================
// Libellés
// ============================================================================

export const ARRONDISSEMENTS = Array.from({ length: 20 }, (_, i) => i + 1);

export function libelleArrondissement(n: number | null): string {
  if (n === null) return 'Inconnu';
  return n === 1 ? '1er' : `${n}e`;
}

export const LIBELLES_CHAUFFAGE: Record<Chauffage, string> = {
  electrique: 'Électrique',
  autre: 'Autre',
};

export const LIBELLES_LECTURE: Record<string, string> = {
  recalcul_2026_probable: 'Recalcul 2026 probable',
  refait: 'Refait',
};

// ============================================================================
// Formats
// ============================================================================

export function formatEntier(n: number): string {
  return n.toLocaleString('fr-FR');
}

export function formatPourcentage(n: number): string {
  return `${(Math.round(n * 10) / 10).toLocaleString('fr-FR')} %`;
}

export function formatPrixM2(n: number): string {
  return `${Math.round(n).toLocaleString('fr-FR')} €/m²`;
}

export function formatDate(iso: string | null): string {
  if (!iso) return '';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleDateString('fr-FR', { day: 'numeric', month: 'short', year: 'numeric' });
}

// ============================================================================
// Style des champs de filtre (même rendu que Top Offres)
// ============================================================================

export const CLASSE_CHAMP = 'text-sm border border-gray-200 rounded px-2 py-1 bg-white text-gray-700';

// ============================================================================
// Lexique : le terme du métier, puis une explication simple (affiché depuis toutes les vues)
// ============================================================================

export const LEXIQUE: { terme: string; definition: string }[] = [
  { terme: 'DPE', definition: 'Diagnostic de performance énergétique : une note de A (très économe) à G (très énergivore) qui mesure la consommation d’énergie et les émissions de gaz à effet de serre d’un logement. Il est établi à la vente, à la location ou pour un logement neuf.' },
  { terme: 'Étiquette', definition: 'La lettre du DPE, de A à G.' },
  { terme: 'Passoire thermique', definition: 'Logement noté F ou G (aussi appelé passoire énergétique). Sa location est progressivement restreinte.' },
  { terme: 'Prix au m²', definition: 'Prix de vente divisé par la surface bâtie indiquée dans le DVF. Ce n’est pas la surface Carrez des annonces : l’écart n’a pas été mesuré.' },
  { terme: 'Prix médian', definition: 'La moitié des ventes s’est faite en dessous de ce prix, l’autre moitié au-dessus. Une vente exceptionnelle le fausse moins qu’une moyenne.' },
  { terme: 'Fourchette', definition: 'Les prix entre lesquels se situe la moitié des ventes « du milieu » : un quart des ventes est moins cher, un quart est plus cher.' },
  { terme: 'Typologie (T1, T2, T3…)', definition: 'Nombre de pièces principales du logement : T2 = 2 pièces, T3 = 3 pièces. Dans les DPE, elle est déclarative et peu renseignée.' },
  { terme: 'Trimestre', definition: 'T1 = janvier à mars, T2 = avril à juin, T3 = juillet à septembre, T4 = octobre à décembre. « T1 2025 » est le premier trimestre 2025.' },
  { terme: 'DVF', definition: 'Demandes de valeurs foncières : la base publique des ventes immobilières, avec la date, le prix, le type de bien, la surface et la localisation, jamais le nom de l’acheteur ni du vendeur.' },
  { terme: 'Arrêté 2021', definition: 'Règles de calcul du DPE applicables depuis juillet 2021. Les DPE plus anciens sont écartés de ces analyses.' },
  { terme: '3CL', definition: 'Méthode de calcul réglementaire utilisée pour établir la plupart des DPE.' },
  { terme: 'Réforme du 1er janvier 2026', definition: 'Le coefficient de l’électricité dans le calcul du DPE passe de 2,3 à 1,9 : certains logements chauffés à l’électricité gagnent une lettre sans travaux.' },
  { terme: 'BDNB', definition: 'Base de données nationale des bâtiments, publiée par le CSTB (Centre scientifique et technique du bâtiment). Elle rassemble les données publiques bâtiment par bâtiment.' },
  { terme: 'Immeuble', definition: 'Unité de la BDNB : un bâtiment ou un groupe de bâtiments, appelé ici « immeuble » pour simplifier.' },
  { terme: 'Étiquette de l’immeuble', definition: 'Note médiane des DPE de l’immeuble. Ce n’est pas la note du logement vendu.' },
  { terme: 'Rattachement (géocodage, appariement)', definition: 'Retrouver dans quel immeuble se situe un logement diagnostiqué ou vendu, à partir de son adresse ou de sa parcelle cadastrale.' },
  { terme: 'RNB', definition: 'Référentiel national des bâtiments : un identifiant national pour chaque bâtiment.' },
  { terme: 'RPLS', definition: 'Répertoire des logements locatifs des bailleurs sociaux.' },
  { terme: 'Déperdition', definition: 'Chaleur qui s’échappe par un élément du logement (mur, fenêtre, sol, toit...), exprimée en watts par kelvin (W/K).' },
  { terme: 'Pont thermique', definition: 'Jonction entre deux éléments du bâtiment (un mur et un plancher, par exemple) où la chaleur passe plus facilement.' },
];
