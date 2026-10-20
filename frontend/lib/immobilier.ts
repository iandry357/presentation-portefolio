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
