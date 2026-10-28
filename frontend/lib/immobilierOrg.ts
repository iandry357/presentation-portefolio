// ============================================================================
// Entrées de la nouvelle organisation de la page Immobilier
// ============================================================================

export const ENTREES = [
  { id: 'dvf', label: 'DVF', icon: '💶' },
  { id: 'dpe', label: 'DPE', icon: '⚡' },
  { id: 'batiment', label: 'Bâtiment', icon: '🏢' },
  { id: 'croise', label: 'Croisé', icon: '🔎' },
  { id: 'exploration', label: 'Exploration', icon: '🧭' },
  { id: 'sources', label: 'Sources', icon: '🧾' },
  { id: 'qualite', label: 'Qualité', icon: '✅' },
] as const;

export type EntreeOrg = (typeof ENTREES)[number]['id'];

// ============================================================================
// Libellés
// ============================================================================

// « 2025-05 » -> « mai 2025 » (libellé court : « janv. 2026 »)
export function formatMois(mois: string): string {
  const [annee, numero] = mois.split('-').map(Number);
  if (!annee || !numero) return mois;
  return new Date(Date.UTC(annee, numero - 1, 1)).toLocaleDateString('fr-FR', {
    month: 'short',
    year: 'numeric',
    timeZone: 'UTC',
  });
}
