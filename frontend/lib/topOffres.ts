import { FT_BASE_URL } from '@/lib/api';
import { SOURCES } from '@/lib/marketConfig';
import { TopListe, TopOffre, TopStatLigne, TypeEntrepriseCorrigeable } from '@/types';

const SOURCE_FT = 'france_travail_api';          // valeur de `source` dans BigQuery
const PREFIXE_ID_FT = 'france_travail_api_';     // id_unique = préfixe + identifiant France Travail

// ============================================================================
// Libellés
// ============================================================================

export const LISTES: { id: TopListe; label: string }[] = [
  { id: 'a_lire', label: 'À lire' },
  { id: 'zone_grise', label: 'Zone grise' },
];

export const LIBELLES_TYPE_ENTREPRISE: Record<string, string> = {
  esn: 'ESN',
  conseil: 'Conseil',
  esn_conseil: 'ESN / Conseil',
  cabinet_recrutement: 'Cabinet de recrutement',
  client_final: 'Client final',
  non_identifie: 'Non identifié',
};

// `non_identifie` n'est qu'un défaut automatique : il ne se choisit pas
export const TYPES_CORRIGEABLES: TypeEntrepriseCorrigeable[] = [
  'esn', 'conseil', 'esn_conseil', 'cabinet_recrutement', 'client_final',
];

export const LIBELLES_CATEGORIE: Record<string, string> = {
  coeur: 'Cœur',
  adjacent: 'Adjacent',
  hors_cible: 'Hors cible',
  inconnu: 'Inconnu',
};

export const LIBELLES_ANNONCEUR: Record<string, string> = {
  employeur_direct: 'Employeur direct',
  intermediaire: 'Intermédiaire',
  inconnu: 'Inconnu',
};

export const LIBELLES_ALERTE: Record<string, string> = {
  salaire_incoherent: 'Salaire incohérent',
  titre_ambigu: 'Titre ambigu',
  intermediaire: 'Intermédiaire',
  seniorite_incertaine: 'Séniorité incertaine',
  autre: 'Autre',
};

export function libelle(table: Record<string, string>, valeur: string | null | undefined): string {
  if (!valeur) return 'Inconnu';
  return table[valeur] ?? valeur;
}

export function libelleSource(source: string | null): string {
  if (!source) return '—';
  return SOURCES.find(s => s.value === source)?.label ?? source;
}

export function formatDateCourte(iso: string | null): string {
  if (!iso) return '';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' });
}

// ============================================================================
// Lien de consultation d'une offre
// ============================================================================

// France Travail : page de l'offre ; sinon URL de l'offre (lien de suivi pour les alertes e-mail) ; sinon rien
export function lienOffre(offre: Pick<TopOffre, 'source' | 'id_unique' | 'url_offre'>): string | null {
  if (offre.source === SOURCE_FT && FT_BASE_URL && offre.id_unique.startsWith(PREFIXE_ID_FT)) {
    return `${FT_BASE_URL}${offre.id_unique.slice(PREFIXE_ID_FT.length)}`;
  }
  return offre.url_offre || null;
}

// ============================================================================
// Statistiques (mart_stats, format long) : agrégations pour les tuiles et graphiques
// ============================================================================

export interface PointJour {
  jour: string;
  a_lire: number;
  zone_grise: number;
  masque: number;
}

// Offres par liste et par jour de collecte, jours croissants
export function serieParJour(lignes: TopStatLigne[]): PointJour[] {
  const parJour = new Map<string, PointJour>();
  for (const l of lignes) {
    if (l.dimension !== 'liste') continue;
    const point = parJour.get(l.jour) ?? { jour: l.jour, a_lire: 0, zone_grise: 0, masque: 0 };
    if (l.valeur === 'a_lire' || l.valeur === 'zone_grise' || l.valeur === 'masque') {
      point[l.valeur] += l.nb_offres;
    }
    parJour.set(l.jour, point);
  }
  return [...parJour.values()].sort((a, b) => a.jour.localeCompare(b.jour));
}

export interface Tuile {
  valeur: number;
  ecart: number | null;   // écart au jour précédent (null s'il n'y a pas de jour précédent)
}

export interface Tuiles {
  jour: string | null;    // dernier jour collecté
  aLire: Tuile;
  zoneGrise: Tuile;
  masquees: Tuile;
  tauxRetenu: Tuile;      // (à lire + zone grise) / total, en %
}

function tuile(courant: number, precedent: number | null): Tuile {
  return { valeur: courant, ecart: precedent === null ? null : courant - precedent };
}

function tauxRetenu(point: PointJour): number {
  const total = point.a_lire + point.zone_grise + point.masque;
  return total ? Math.round((100 * (point.a_lire + point.zone_grise)) / total) : 0;
}

export function calculerTuiles(serie: PointJour[]): Tuiles {
  const dernier = serie[serie.length - 1];
  const precedent = serie.length > 1 ? serie[serie.length - 2] : null;
  if (!dernier) {
    return {
      jour: null,
      aLire: tuile(0, null),
      zoneGrise: tuile(0, null),
      masquees: tuile(0, null),
      tauxRetenu: tuile(0, null),
    };
  }
  return {
    jour: dernier.jour,
    aLire: tuile(dernier.a_lire, precedent ? precedent.a_lire : null),
    zoneGrise: tuile(dernier.zone_grise, precedent ? precedent.zone_grise : null),
    masquees: tuile(dernier.masque, precedent ? precedent.masque : null),
    tauxRetenu: tuile(tauxRetenu(dernier), precedent ? tauxRetenu(precedent) : null),
  };
}

export interface Part {
  valeur: string;
  nb: number;
}

// Cumul d'une dimension sur la période, du plus grand au plus petit
export function repartition(lignes: TopStatLigne[], dimension: string): Part[] {
  const cumul = new Map<string, number>();
  for (const l of lignes) {
    if (l.dimension !== dimension) continue;
    const cle = l.valeur ?? 'inconnu';
    cumul.set(cle, (cumul.get(cle) ?? 0) + l.nb_offres);
  }
  return [...cumul.entries()]
    .map(([valeur, nb]) => ({ valeur, nb }))
    .sort((a, b) => b.nb - a.nb);
}

// Ordre logique imposé (ex. cœur, adjacent, hors cible) ; les valeurs hors liste passent à la fin
export function ordonner(parts: Part[], ordre: string[]): Part[] {
  const rang = (valeur: string) => {
    const i = ordre.indexOf(valeur);
    return i === -1 ? ordre.length : i;
  };
  return [...parts].sort((a, b) => rang(a.valeur) - rang(b.valeur));
}

// Garde les n premières parts et replie le reste dans « Autres »
export function topN(parts: Part[], n: number): Part[] {
  if (parts.length <= n) return parts;
  const reste = parts.slice(n).reduce((somme, p) => somme + p.nb, 0);
  return [...parts.slice(0, n), { valeur: 'Autres', nb: reste }];
}

// Intitulé d'une cible (cible_id -> intitulé), à défaut le cible_id
export function libelleCible(id: string, cibles: Record<string, string>): string {
  return cibles[id] ?? id;
}
