import type { ParcResponse, PrixDpeResponse, SourcesResponse } from '@/lib/immobilierBdnbApi';
import { formatEntier, formatPourcentage } from '@/lib/immobilier';
import {
  CLASSES_DPE, LIBELLE_ENERGIE_AUTRES, POSTES, libelleAppariement, libelleEnergie, libellePeriode, ordrePeriode,
} from '@/lib/immobilierBdnb';

// Phrases « À retenir » et « Attention » calculées à partir des données affichées.
// Chaque fonction renvoie null quand les données ne suffisent pas : mieux vaut ne rien écrire qu'une phrase fausse.

// Seuils
export const SEUIL_VENTES_FIABLES = 30;   // une classe de moins de N ventes n'entre pas dans les comparaisons de prix
const SEUIL_BASE = 5000;                  // une période ou une énergie de moins de N DPE n'entre pas dans les comparaisons de parts
const SEUIL_ECART_FAIBLE = 5;             // écart de prix (en %) en dessous duquel on parle d'un écart faible
const PASSOIRES = ['F', 'G'];
const ENERGIES_EXCLUES = [LIBELLE_ENERGIE_AUTRES, 'Non renseigné'];   // trop hétérogènes pour être comparées

// ============================================================================
// Outils
// ============================================================================

// « les notes C à G », « les notes A, C », « la note A »
function libelleNotes(lettres: string[]): string {
  const tri = [...lettres].sort();
  if (tri.length === 1) return `la note ${tri[0]}`;
  const rangs = tri.map(l => (CLASSES_DPE as readonly string[]).indexOf(l));
  const contigu = rangs.every((r, i) => i === 0 || r === rangs[i - 1] + 1);
  return contigu ? `les notes ${tri[0]} à ${tri[tri.length - 1]}` : `les notes ${tri.join(', ')}`;
}

interface PartPassoires {
  nom: string;
  total: number;
  part: number;   // % de DPE en F ou G
}

function partsPassoires(lignes: { nom: string; etiquette: string; nb: number }[]): PartPassoires[] {
  const cumul = new Map<string, { total: number; fg: number }>();
  for (const { nom, etiquette, nb } of lignes) {
    const c = cumul.get(nom) ?? { total: 0, fg: 0 };
    c.total += nb;
    if (PASSOIRES.includes(etiquette)) c.fg += nb;
    cumul.set(nom, c);
  }
  return [...cumul.entries()].map(([nom, c]) => ({ nom, total: c.total, part: (100 * c.fg) / c.total }));
}

function extremes(parts: PartPassoires[]): { forte: PartPassoires; faible: PartPassoires } {
  return {
    forte: parts.reduce((a, b) => (b.part > a.part ? b : a)),
    faible: parts.reduce((a, b) => (b.part < a.part ? b : a)),
  };
}

// ============================================================================
// Prix et DPE
// ============================================================================

export function retenirPrix(data: PrixDpeResponse): string | null {
  const fiables = data.classes.filter(c => c.nb_ventes >= SEUIL_VENTES_FIABLES && c.prix_m2_median !== null);
  if (fiables.length < 2) return null;
  const prix = fiables.map(c => c.prix_m2_median as number);
  const phrases = [
    `Le prix médian va de ${formatEntier(Math.min(...prix))} à ${formatEntier(Math.max(...prix))} €/m² selon la note (${libelleNotes(fiables.map(c => c.classe_dpe))}).`,
  ];

  const pct = data.ecart?.ecart_pct;
  if (pct !== null && pct !== undefined) {
    const comparaison =
      pct === 0
        ? 'se vendent au même prix que'
        : `se vendent ${formatPourcentage(Math.abs(pct))} ${pct < 0 ? 'moins' : 'plus'} cher que`;
    phrases.push(`Les logements F et G ${comparaison} les D${Math.abs(pct) < SEUIL_ECART_FAIBLE ? ', un écart faible' : ''}.`);
  }
  return phrases.join(' ');
}

export function attentionPrix(data: PrixDpeResponse): string {
  const base = 'Cet écart ne tient compte ni du quartier, ni de la surface, ni de l’époque de construction.';
  const faibles = data.classes.filter(c => c.nb_ventes < SEUIL_VENTES_FIABLES);
  if (faibles.length === 0) return base;
  const detail = faibles.map(c => `${libelleNotes([c.classe_dpe])} (${formatEntier(c.nb_ventes)})`).join(', ');
  return `${base} Peu de ventes pour ${detail} : ces prix sont peu fiables.`;
}

// ============================================================================
// Profil du parc
// ============================================================================

export function retenirPeriodes(data: ParcResponse): string | null {
  const toutes = partsPassoires(
    data.periodes.map(l => ({ nom: l.periode_construction ?? 'inconnue', etiquette: l.etiquette, nb: l.nb_dpe })),
  );
  const comparables = toutes.filter(p => p.total >= SEUIL_BASE);
  if (comparables.length < 2) return null;

  const { forte, faible } = extremes(comparables);
  const totalTous = toutes.reduce((somme, p) => somme + p.total, 0);
  const plusGrosse = toutes.reduce((a, b) => (b.total > a.total ? b : a));
  return (
    `Selon l’époque de construction, la part de notes F ou G va de ${formatPourcentage(faible.part)} ` +
    `(${libellePeriode(faible.nom)}) à ${formatPourcentage(forte.part)} (${libellePeriode(forte.nom)}). ` +
    `La période « ${libellePeriode(plusGrosse.nom)} » compte le plus de logements ` +
    `(${formatPourcentage((100 * plusGrosse.total) / totalTous)} des logements analysés).`
  );
}

export function attentionPeriodes(data: ParcResponse): string | null {
  const toutes = partsPassoires(
    data.periodes.map(l => ({ nom: l.periode_construction ?? 'inconnue', etiquette: l.etiquette, nb: l.nb_dpe })),
  );
  if (toutes.length === 0) return null;
  const petite = toutes.reduce((a, b) => (b.total < a.total ? b : a));
  return (
    'Une barre construite sur peu de logements est fragile : leur nombre est écrit sous chaque époque ' +
    `(${libellePeriode(petite.nom)} : ${formatEntier(petite.total)}).`
  );
}

export function retenirEnergies(data: ParcResponse): string | null {
  const comparables = partsPassoires(
    data.energies.map(l => ({ nom: libelleEnergie(l.energie_chauffage), etiquette: l.etiquette, nb: l.nb_dpe })),
  ).filter(p => p.total >= SEUIL_BASE && !ENERGIES_EXCLUES.includes(p.nom));
  if (comparables.length < 2) return null;

  const { forte, faible } = extremes(comparables);
  return (
    `Selon le chauffage, la part de notes F ou G va de ${formatPourcentage(faible.part)} (${faible.nom}) ` +
    `à ${formatPourcentage(forte.part)} (${forte.nom}).`
  );
}

export function retenirDeperditions(data: ParcResponse): string | null {
  const parPeriode = new Map<string, { nb: number; lignes: { poste: string; part: number }[] }>();
  for (const l of data.deperditions) {
    if (l.part_moyenne === null) continue;
    const cle = l.periode_construction ?? 'inconnue';
    const entree = parPeriode.get(cle) ?? { nb: 0, lignes: [] };
    entree.nb = Math.max(entree.nb, l.nb_logements);   // les 6 postes portent sur les mêmes logements
    entree.lignes.push({ poste: l.poste, part: l.part_moyenne });
    parPeriode.set(cle, entree);
  }
  const periodes = [...parPeriode.entries()]
    .filter(([, e]) => e.nb >= SEUIL_BASE)
    .sort(([a], [b]) => ordrePeriode(a) - ordrePeriode(b));
  if (periodes.length < 2) return null;

  // Poste de plus forte part pour la première (la plus ancienne) et la dernière (la plus récente) période
  const dominant = ([nom, e]: (typeof periodes)[number]) => {
    const haut = e.lignes.reduce((a, b) => (b.part > a.part ? b : a));
    return {
      periode: libellePeriode(nom),
      poste: POSTES.find(p => p.id === haut.poste)?.libelle ?? haut.poste,
      part: formatPourcentage(100 * haut.part),
    };
  };
  const ancien = dominant(periodes[0]);
  const recent = dominant(periodes[periodes.length - 1]);

  if (ancien.poste === recent.poste) {
    return (
      `Le premier poste de perte de chaleur est « ${ancien.poste} » aussi bien pour la période « ${ancien.periode} » ` +
      `(${ancien.part}) que pour « ${recent.periode} » (${recent.part}).`
    );
  }
  return (
    `Le premier poste de perte de chaleur est « ${ancien.poste} » pour la période « ${ancien.periode} » (${ancien.part}), ` +
    `et « ${recent.poste} » pour « ${recent.periode} » (${recent.part}).`
  );
}

export function attentionDeperditions(data: ParcResponse): string | null {
  if (!data.nb_dpe) return null;
  const couverture = formatPourcentage((100 * data.nb_logements_deperditions) / data.nb_dpe);
  return `Ce sont des parts moyennes : un logement particulier peut s’en écarter. Seuls ${couverture} des logements ont leurs six postes renseignés.`;
}

// ============================================================================
// Sources et qualité
// ============================================================================

export function retenirEntonnoir(data: SourcesResponse): string | null {
  const etapes = [...data.entonnoir].sort((a, b) => a.etape - b.etape);
  if (etapes.length < 2 || !etapes[0].nb_dpe) return null;

  const base = etapes[0];
  const retenu = etapes[etapes.length - 1];
  let pire = { libelle: '', ecartes: 0 };
  for (let i = 1; i < etapes.length; i++) {
    const ecartes = etapes[i - 1].nb_dpe - etapes[i].nb_dpe;
    if (ecartes > pire.ecartes) pire = { libelle: etapes[i].libelle, ecartes };
  }
  return (
    `${formatPourcentage((100 * retenu.nb_dpe) / base.nb_dpe)} des DPE de la base sont gardés ` +
    `(${formatEntier(retenu.nb_dpe)} sur ${formatEntier(base.nb_dpe)}). ` +
    `Le filtre qui en écarte le plus est « ${pire.libelle} » (${formatEntier(pire.ecartes)} DPE).`
  );
}

export function retenirGeocodage(data: SourcesResponse): string | null {
  const total = data.geocodage.reduce((somme, l) => somme + l.nb_liens, 0);
  if (!total) return null;
  const nb = (...niveaux: string[]) =>
    data.geocodage.filter(l => niveaux.includes(l.fiabilite)).reduce((somme, l) => somme + l.nb_liens, 0);
  return (
    `${formatPourcentage((100 * nb('très fiable')) / total)} des rattachements sont jugés « très fiables », ` +
    `${formatPourcentage((100 * nb('très fiable', 'globalement fiable')) / total)} au moins « globalement fiables ».`
  );
}

export function retenirAppariement(data: SourcesResponse): string | null {
  const total = data.geocodage.reduce((somme, l) => somme + l.nb_liens, 0);
  if (!total) return null;
  const parMethode = new Map<string, number>();
  for (const l of data.geocodage) parMethode.set(l.appariement, (parMethode.get(l.appariement) ?? 0) + l.nb_liens);
  const [methode, nb] = [...parMethode.entries()].reduce((a, b) => (b[1] > a[1] ? b : a));
  return `La méthode la plus fréquente est « ${libelleAppariement(methode)} » (${formatPourcentage((100 * nb) / total)} des rattachements).`;
}
