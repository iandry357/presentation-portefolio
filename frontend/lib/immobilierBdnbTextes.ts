import type {
  AnalyseCellule, AnalyseResponse, ParcResponse, PrixDpeResponse, SourceAnalyse, SourcesResponse,
} from '@/lib/immobilierBdnbApi';
import { formatEntier, formatPourcentage } from '@/lib/immobilier';
import {
  CLASSES_DPE, LIBELLE_ENERGIE_AUTRES, NON_RENSEIGNE, POSTES, libelleAppariement, libelleEnergie, libelleModalite, libelleMethodeRattachement,
  libellePeriode, ordrePeriode, minuscule 
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

export function retenirQualite(data: SourcesResponse): string | null {
  const q = data.qualite;
  if (!q || q.precision_pct === null) return null;
  const phrase =
    `${formatPourcentage(q.precision_pct)} des ventes de contrôle sont rattachées au bon immeuble ` +
    `(${formatEntier(q.nb_ok)} sur ${formatEntier(q.nb_ok + q.nb_erreur)}).`;
  const fiables = q.methodes.filter(m => m.precision_pct !== null && m.nb_ventes >= SEUIL_VENTES_FIABLES);
  if (fiables.length < 2) return phrase;
  const moins = fiables.reduce((a, b) => ((b.precision_pct as number) < (a.precision_pct as number) ? b : a));
  return (
    `${phrase} La méthode la moins sûre est « ${libelleMethodeRattachement(moins.methode)} » ` +
    `(${formatPourcentage(moins.precision_pct as number)}, ${formatEntier(moins.nb_ventes)} ventes).`
  );
}

export function attentionQualite(data: SourcesResponse): string | null {
  if (!data.qualite) return null;
  return (
    'La mesure porte sur les ventes que la BDNB a elle-même retenues (une par immeuble) : elle ne vaut pas forcément ' +
    'pour toutes les ventes. Les ventes non rattachées ne figurent dans aucun prix par étiquette.'
  );
}

// ============================================================================
// Analyse (cube ventes / DPE)
// ============================================================================

// Réforme du DPE : même explication que le repère de la vue Changements (Reperes.tsx).
// L'effet exact sur l'ensemble des DPE n'est pas mesuré (suivi E4, 2026-10-23).
export const ALERTE_REFORME_DPE =
  'Réforme du DPE du 1er janvier 2026 : le coefficient de l’électricité passe de 2,3 à 1,9 dans le calcul. Certains logements chauffés à l’électricité gagnent une lettre sans travaux : les étiquettes d’avant et d’après ne se comparent donc pas strictement. L’effet exact sur l’ensemble des DPE reste à mesurer.';

// Mesure de l'exploration du 2026-10-23 : 71 % des DPE avec typologie se trouvent dans les 13e et 15e arrondissements
export function alertePieces(recouvrement: number): string {
  return (
    `Le nombre de pièces vient de la typologie (T1, T2, T3…) que le diagnostiqueur peut renseigner : elle n’est renseignée que pour ${formatPourcentage(recouvrement)} ` +
    'des DPE, surtout dans les 13e et 15e arrondissements. Lisez ces chiffres comme un échantillon, pas comme l’ensemble des logements de Paris.'
  );
}

// `axes` : libellés des axes choisis (« Nombre de pièces », « Étiquette de l’immeuble »)
// comptage : DPE par trimestre, la barre donne le nombre de diagnostics et non une part
export function voirAnalyse(source: SourceAnalyse, axes: string[], comptage = false): string {
  const selon = axes.map(minuscule).join(' et ');
  if (source === 'ventes') {
    return `Le prix médian au m² des logements vendus à Paris, selon ${selon}. La moitié des ventes s’est faite en dessous de ce prix, l’autre moitié au-dessus.`;
  }
  return comptage
    ? `Le nombre de logements diagnostiqués (DPE) à Paris, selon ${selon}.`
    : `La répartition des logements diagnostiqués (DPE) à Paris, selon ${selon}. Chaque barre est la part de ces diagnostics.`;
}

// Modalités qui ne sont pas des valeurs à comparer (« inconnue » : vente sans immeuble ni DPE rattaché)
const MODALITES_ECARTEES = [NON_RENSEIGNE, 'inconnue'];

export function retenirAnalyse(data: AnalyseResponse): string | null {
  if (data.meta.axes.length !== 1) return null;
  const axe = data.meta.axes[0];
  const nom = (c: AnalyseCellule) => libelleModalite(axe, c.modalites[0]);
  const comparables = data.cellules.filter(c => !MODALITES_ECARTEES.includes(c.modalites[0]));

  // DPE par trimestre : évolution du nombre de diagnostics entre le premier et le dernier trimestre
  if (data.meta.source === 'dpe' && axe === 'trimestre') {
    if (comparables.length < 2) return null;
    const premier = comparables[0];
    const dernier = comparables[comparables.length - 1];
    const evolution = ((dernier.n - premier.n) / premier.n) * 100;
    return (
      `Le nombre de DPE passe de ${formatEntier(premier.n)} (${nom(premier)}) à ${formatEntier(dernier.n)} (${nom(dernier)}), ` +
      `soit ${evolution > 0 ? '+' : evolution < 0 ? '−' : ''}${formatPourcentage(Math.abs(evolution))}.`
    );
  }

  if (data.meta.source === 'ventes') {
    const fiables = comparables.filter(c => c.n >= SEUIL_VENTES_FIABLES && c.mediane !== null);
    if (fiables.length < 2) return null;
    const bas = fiables.reduce((a, b) => ((b.mediane as number) < (a.mediane as number) ? b : a));
    const haut = fiables.reduce((a, b) => ((b.mediane as number) > (a.mediane as number) ? b : a));
    const ecart = ((haut.mediane as number) / (bas.mediane as number) - 1) * 100;
    return (
      `Le prix médian va de ${formatEntier(bas.mediane as number)} €/m² (${nom(bas)}) ` +
      `à ${formatEntier(haut.mediane as number)} €/m² (${nom(haut)})${ecart < SEUIL_ECART_FAIBLE ? ', soit un écart faible' : ''}.`
    );
  }

  const avecPart = comparables.filter(c => c.part_pct !== null);
  if (avecPart.length < 2) return null;
  const forte = avecPart.reduce((a, b) => ((b.part_pct as number) > (a.part_pct as number) ? b : a));
  return `La part la plus forte est « ${nom(forte)} » (${formatPourcentage(forte.part_pct as number)}).`;
}

export function attentionAnalyse(data: AnalyseResponse): string | null {
  if (data.meta.source === 'dpe') {
    const { trimestre_min: debut, trimestre_max: fin } = data.meta;
    if (!debut || !fin) return null;
    const base =
      `DPE établis de ${libelleModalite('trimestre', debut)} à ${libelleModalite('trimestre', fin)}, à la vente, ` +
      'à la location ou pour un logement neuf : ce sont des logements diagnostiqués, pas l’ensemble du parc.';
    return data.meta.axes.includes('trimestre')
      ? `${base} Les derniers trimestres peuvent être incomplets : la BDNB reçoit les DPE avec un décalage.`
      : base;
  }

  const base = 'Ces prix sont bruts : ils ne tiennent compte que des critères choisis, ni de l’état du bien, ni de son étage.';
  const fragiles = data.cellules.filter(c => c.n < SEUIL_VENTES_FIABLES);
  if (fragiles.length === 0) return base;
  if (data.meta.axes.length === 1) {
    const detail = fragiles
      .map(c => `${libelleModalite(data.meta.axes[0], c.modalites[0])} (${formatEntier(c.n)} ventes)`)
      .join(', ');
    return `${base} Peu de ventes pour ${detail} : ces prix sont à lire avec prudence.`;
  }
  return (
    `${base} ${fragiles.length} case${fragiles.length > 1 ? 's reposent' : ' repose'} sur moins de ` +
    `${SEUIL_VENTES_FIABLES} ventes : leurs prix sont à lire avec prudence.`
  );
}
