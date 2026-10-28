'use client';

import { useCallback, useEffect, useState } from 'react';
import { useAccess } from '@/components/AccessProvider';
import { cn } from '@/lib/utils';
import { OrgEcartPrix, OrgPrixDpeResponse, getOrgEcartPrix } from '@/lib/immobilierOrgApi';
import { SEUIL_VENTES_FIABLES } from '@/lib/immobilierOrgCubes';
import { formatMois } from '@/lib/immobilierOrg';
import { telechargerCsv } from '@/lib/immobilierOrgCsv';
import { formatEntier, formatPourcentage } from '@/lib/immobilier';
import { CarteGraphique, COULEURS, Colonnes, Explication, ModeAffichage, Point } from '../ImmobilierCharts';
import Lecture from '../bdnb/Lecture';

// Paramètres
const CLASSES_DPE = ['A', 'B', 'C', 'D', 'E', 'F', 'G'];
const CLASSES_PASSOIRES = ['F', 'G'];
const CLASSE_REFERENCE = 'D';
const SEUIL_ECART_FAIBLE = 5;   // écart de prix (en %) en dessous duquel on parle d'un écart faible
const COULEUR_FRAGILE = COULEURS.grille;
const ATTENTION_ECART = 'Cet écart ne tient compte ni du quartier, ni de la surface, ni de l’époque de construction.';

const LEGENDE = [
  { libelle: 'F et G (passoires)', couleur: COULEURS.slot1 },
  { libelle: 'D (référence de l’écart)', couleur: COULEURS.slot2 },
  { libelle: 'Autres classes', couleur: COULEURS.axe },
];

// Emphase : F et G en bleu, D (la référence de l'écart) en orange, le reste en gris
function couleurClasse(classe: string): string {
  if (CLASSES_PASSOIRES.includes(classe)) return COULEURS.slot1;
  if (classe === CLASSE_REFERENCE) return COULEURS.slot2;
  return COULEURS.axe;
}

// Une classe de moins de SEUIL_VENTES_FIABLES ventes est grisée en clair : sa hauteur ne dit rien de fiable
function estFragile(nbVentes: number): boolean {
  return nbVentes < SEUIL_VENTES_FIABLES;
}

function formatEcart(pct: number): string {
  const signe = pct > 0 ? '+' : pct < 0 ? '−' : '';
  return `${signe}${formatPourcentage(Math.abs(pct))}`;
}

// « les notes C à G », « les notes A, C », « la note A »
function libelleNotes(lettres: string[]): string {
  const tri = [...lettres].sort();
  if (tri.length === 1) return `la note ${tri[0]}`;
  const rangs = tri.map(l => CLASSES_DPE.indexOf(l));
  const contigu = rangs.every((r, i) => i === 0 || r === rangs[i - 1] + 1);
  return contigu ? `les notes ${tri[0]} à ${tri[tri.length - 1]}` : `les notes ${tri.join(', ')}`;
}

// « Sur cette période, le prix médian des logements F et G est supérieur de 0,9 % à celui des D, un écart faible. »
function phraseEcart(ecart: OrgEcartPrix): string | null {
  const pct = ecart.ecart_pct;
  if (pct === null) return null;
  const comparaison =
    pct === 0
      ? 'est le même que celui'
      : `est ${pct < 0 ? 'inférieur' : 'supérieur'} de ${formatPourcentage(Math.abs(pct))} à celui`;
  return `Sur cette période, le prix médian des logements F et G ${comparaison} des D${Math.abs(pct) < SEUIL_ECART_FAIBLE ? ', un écart faible' : ''}.`;
}

function retenirPrix(data: OrgPrixDpeResponse): string | null {
  const fiables = data.classes.filter(c => !estFragile(c.nb_ventes) && c.prix_m2_median !== null);
  if (fiables.length < 2) return null;
  const prix = fiables.map(c => c.prix_m2_median as number);
  const phrases = [
    `Le prix médian va de ${formatEntier(Math.min(...prix))} à ${formatEntier(Math.max(...prix))} €/m² selon la note (${libelleNotes(fiables.map(c => c.classe_dpe))}).`,
  ];
  const ecart = data.ecart ? phraseEcart(data.ecart) : null;
  if (ecart) phrases.push(ecart);
  return phrases.join(' ');
}

function attentionPrix(data: OrgPrixDpeResponse): string {
  const faibles = data.classes.filter(c => estFragile(c.nb_ventes));
  if (faibles.length === 0) return ATTENTION_ECART;
  const detail = faibles.map(c => `${libelleNotes([c.classe_dpe])} (${formatEntier(c.nb_ventes)})`).join(', ');
  return `${ATTENTION_ECART} Peu de ventes pour ${detail} : ces prix sont peu fiables.`;
}

export default function OrgPrixDpe() {
  const { unlocked } = useAccess();
  const [data, setData] = useState<OrgPrixDpeResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<ModeAffichage>('graphique');

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await getOrgEcartPrix());
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erreur de chargement');
    } finally {
      setLoading(false);
    }
  }, []);

  // Relecture quand l'accès change : le seuil de ventes ne s'applique que verrouillé
  useEffect(() => {
    load();
  }, [load, unlocked]);

  // Une colonne par classe présente (une classe sous le seuil est absente si l'accès est verrouillé)
  const lignes = CLASSES_DPE.flatMap(classe => {
    const ligne = data?.classes.find(l => l.classe_dpe === classe);
    return ligne && ligne.prix_m2_median !== null ? [ligne] : [];
  });
  const points: Point[] = lignes.map(ligne => ({
    nom: ligne.classe_dpe,
    valeur: ligne.prix_m2_median as number,
    detail: `${formatEntier(ligne.nb_ventes)} ventes${estFragile(ligne.nb_ventes) ? ' · lecture fragile' : ''}`,
    couleur: estFragile(ligne.nb_ventes) ? COULEUR_FRAGILE : couleurClasse(ligne.classe_dpe),
  }));

  const avecClasseFragile = lignes.some(l => estFragile(l.nb_ventes));
  const legende = avecClasseFragile
    ? [...LEGENDE, { libelle: `Moins de ${SEUIL_VENTES_FIABLES} ventes : lecture fragile`, couleur: COULEUR_FRAGILE }]
    : LEGENDE;

  const ecart = data?.ecart ?? null;
  const periode = data?.mois_min && data?.mois_max ? `${formatMois(data.mois_min)} à ${formatMois(data.mois_max)}` : null;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-4 text-sm text-gray-600">
        <label className="inline-flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={mode === 'tableau'}
            onChange={e => setMode(e.target.checked ? 'tableau' : 'graphique')}
            className="w-4 h-4 rounded border-gray-300"
          />
          Voir en tableau
        </label>
        {lignes.length > 0 && (
          <button
            type="button"
            onClick={() =>
              telechargerCsv(
                'immobilier_prix_et_dpe.csv',
                ['Étiquette de l’immeuble', 'Nombre de ventes', 'Prix médian (€/m²)'],
                lignes.map(l => [l.classe_dpe, l.nb_ventes, l.prix_m2_median]),
              )
            }
            className="text-blue-700 hover:underline"
          >
            Télécharger en CSV
          </button>
        )}
      </div>

      {error && <div className="text-sm text-red-600 bg-red-50 px-4 py-3 rounded-lg">{error}</div>}

      {!data && loading && <div className="h-64 border rounded-lg bg-white animate-pulse" />}

      {data && (
        // Pendant un rechargement, le contenu précédent reste affiché en atténué
        <div className={cn('space-y-6 transition-opacity', loading && 'opacity-60')}>

          {ecart && ecart.ecart_pct !== null && ecart.prix_m2_median_fg !== null && ecart.prix_m2_median_d !== null && (
            <div className="border rounded-lg bg-white p-4">
              <p className="text-sm text-gray-500">
                Écart de prix : F et G par rapport à D{periode && ` (${periode} · DVF Etalab)`}
              </p>
              <p className="text-3xl font-semibold text-gray-900 mt-1">{formatEcart(ecart.ecart_pct)}</p>
              <p className="text-sm text-gray-700 mt-1">{phraseEcart(ecart)}</p>
              <p className="text-xs text-gray-500 mt-1">
                {formatEntier(ecart.prix_m2_median_fg)} €/m² pour F et G ({formatEntier(ecart.nb_fg)} ventes) contre{' '}
                {formatEntier(ecart.prix_m2_median_d)} €/m² pour D ({formatEntier(ecart.nb_d)} ventes).
              </p>
              <p className="text-xs text-gray-500 mt-1">{ATTENTION_ECART}</p>
            </div>
          )}

          {data.seuil_applique && data.nb_masquees > 0 && (
            <p className="text-sm text-gray-600 bg-gray-50 border rounded-lg px-4 py-3">
              {formatEntier(data.nb_masquees)} classe{data.nb_masquees > 1 ? 's' : ''} de moins de {data.seuil} ventes
              {data.nb_masquees > 1 ? ' sont masquées' : ' est masquée'}.
              Déverrouillez avec le bouton en haut de la page pour tout voir.
            </p>
          )}

          <CarteGraphique
            titre="Prix médian au m² selon l’étiquette de l’immeuble"
            sousTitre={
              periode && data.prix_m2_min !== null && data.prix_m2_max !== null
                ? `Ventes de ${periode} (DVF Etalab) · prix entre ${formatEntier(data.prix_m2_min)} et ${formatEntier(data.prix_m2_max)} €/m²`
                : undefined
            }
          >
            <Lecture
              voir="Le prix d’un mètre carré vendu à Paris, selon la note énergétique de l’immeuble, de A (très économe) à G (très énergivore). Les logements notés F ou G sont appelés « passoires thermiques »."
              retenir={retenirPrix(data)}
              attention={attentionPrix(data)}
            />

            <Explication titre="Détails de calcul">
              <p>
                Le prix médian est la valeur du milieu : la moitié des ventes s’est faite en dessous, l’autre moitié
                au-dessus.
              </p>
              <p>
                La note d’un immeuble est la note médiane des DPE de ses logements (DPE de la BDNB). Quand le nombre de
                DPE est pair, on retient la meilleure des deux notes centrales. Ce n’est pas la note du logement vendu.
              </p>
              <p>
                Chaque vente de logement de la période est rattachée à son immeuble, par sa parcelle et par son adresse
                (voir la partie Qualité pour la précision de ce rattachement). Les ventes sans immeuble identifié, ou dont
                l’immeuble n’a pas de DPE, ne figurent pas ici. Le prix au m² est celui du logement vendu, pas celui de
                tout l’immeuble.
              </p>
            </Explication>

            <ul className="flex flex-wrap gap-x-4 gap-y-1 mb-3 text-xs text-gray-600" aria-label="Légende">
              {legende.map(({ libelle, couleur }) => (
                <li key={libelle} className="inline-flex items-center gap-1.5">
                  <span className="inline-block w-3 h-3 rounded-sm" style={{ backgroundColor: couleur }} />
                  {libelle}
                </li>
              ))}
            </ul>

            <Colonnes
              points={points}
              colonneNom="Étiquette"
              colonneValeur="Prix médian (€/m²)"
              colonneDetail="Ventes"
              formater={formatEntier}
              mode={mode}
            />
          </CarteGraphique>

          <p className="text-xs text-gray-500">
            Prix : ventes de logement du DVF (Etalab), rattachées à leur immeuble. Notes : DPE de la BDNB (CSTB) reliés à
            l’immeuble. Mêmes données que l’analyse « Ventes, DPE et bâti ».
          </p>
        </div>
      )}
    </div>
  );
}
