// ============================================================================
// Entrées de la nouvelle organisation de la page Immobilier
// ============================================================================

export const ENTREES = [
  { id: 'dvf', label: 'Ventes', icon: '💶', phrase: 'Les ventes de logements à Paris (DVF) : prix au m², selon la taille, le quartier, le mois.' },
  { id: 'dpe', label: 'Diagnostics', icon: '⚡', phrase: 'Les diagnostics de performance énergétique (DPE de l’ADEME) : étiquettes de A à G et logements concernés.' },
  { id: 'batiment', label: 'Immeubles', icon: '🏢', phrase: 'Les immeubles de Paris (BDNB) : époque, usage, copropriété, risques.' },
  { id: 'croise', label: 'Croisement', icon: '🔗', phrase: 'Relie chaque vente à son immeuble et à ses diagnostics, pour répondre à ce qu’aucune partie seule ne montre.' },
  { id: 'exploration', label: 'Exploration', icon: '🧭', phrase: 'La carte, les loyers de référence et l’assistant juridique.' },
  { id: 'sources', label: 'Sources', icon: '🧾', phrase: 'D’où viennent les données, quelle période elles couvrent et quand elles ont été chargées.' },
  { id: 'qualite', label: 'Qualité', icon: '✅', phrase: 'Ce qui est retenu, ce qui est écarté, et où deux sources ne coïncident pas.' },
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
