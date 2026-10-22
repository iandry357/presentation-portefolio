'use client';

import { useCallback, useEffect, useState } from 'react';
import { useAccess } from '@/components/AccessProvider';
import { cn } from '@/lib/utils';
import { PrixDpeResponse, getBdnbPrixDpe } from '@/lib/immobilierBdnbApi';
import { CLASSES_DPE } from '@/lib/immobilierBdnb';
import { SEUIL_VENTES_FIABLES, attentionPrix, retenirPrix } from '@/lib/immobilierBdnbTextes';
import { formatDate, formatEntier, formatPourcentage } from '@/lib/immobilier';
import { CarteGraphique, COULEURS, Colonnes, Explication, ModeAffichage, Point } from '../ImmobilierCharts';
import Lecture from './Lecture';

// Paramètres
const CLASSES_PASSOIRES: string[] = ['F', 'G'];
const CLASSE_REFERENCE = 'D';

// Emphase : F et G en bleu, D (la référence de l'écart) en orange, le reste en gris
function couleurClasse(classe: string): string {
  if (CLASSES_PASSOIRES.includes(classe)) return COULEURS.slot1;
  if (classe === CLASSE_REFERENCE) return COULEURS.slot2;
  return COULEURS.axe;
}

// Une classe de moins de SEUIL_VENTES_FIABLES ventes est grisée en clair : sa hauteur ne dit rien de fiable
const COULEUR_FRAGILE = COULEURS.grille;

function estFragile(nbVentes: number): boolean {
  return nbVentes < SEUIL_VENTES_FIABLES;
}

function formatEcart(pct: number): string {
  const signe = pct > 0 ? '+' : pct < 0 ? '−' : '';
  return `${signe}${formatPourcentage(Math.abs(pct))}`;
}

const LEGENDE = [
  { libelle: 'F et G (passoires)', couleur: COULEURS.slot1 },
  { libelle: 'D (référence de l’écart)', couleur: COULEURS.slot2 },
  { libelle: 'Autres classes', couleur: COULEURS.axe },
];

const ENTREE_FRAGILE = {
  libelle: `Moins de ${SEUIL_VENTES_FIABLES} ventes : lecture fragile`,
  couleur: COULEUR_FRAGILE,
};

export default function PrixDpeView() {
  const { unlocked } = useAccess();
  const [data, setData] = useState<PrixDpeResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<ModeAffichage>('graphique');

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await getBdnbPrixDpe());
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
  const points: Point[] = CLASSES_DPE.flatMap(classe => {
    const ligne = data?.classes.find(l => l.classe_dpe === classe);
    if (!ligne || ligne.prix_m2_median === null) return [];
    return [{
      nom: classe,
      valeur: ligne.prix_m2_median,
      detail: `${formatEntier(ligne.nb_ventes)} ventes${estFragile(ligne.nb_ventes) ? ' · lecture fragile' : ''}`,
      couleur: estFragile(ligne.nb_ventes) ? COULEUR_FRAGILE : couleurClasse(classe),
    }];
  });

  const avecClasseFragile = data?.classes.some(c => c.prix_m2_median !== null && estFragile(c.nb_ventes)) ?? false;
  const legende = avecClasseFragile ? [...LEGENDE, ENTREE_FRAGILE] : LEGENDE;

  const ecart = data?.ecart ?? null;

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
      </div>

      {error && (
        <div className="text-sm text-red-600 bg-red-50 px-4 py-3 rounded-lg">{error}</div>
      )}

      {!data && loading && <div className="h-64 border rounded-lg bg-white animate-pulse" />}

      {data && (
        // Pendant un rechargement, le contenu précédent reste affiché en atténué
        <div className={cn('space-y-6 transition-opacity', loading && 'opacity-60')}>

          {ecart && ecart.ecart_pct !== null && ecart.prix_m2_median_fg !== null && ecart.prix_m2_median_d !== null && (
            <div className="border rounded-lg bg-white p-4">
              <p className="text-sm text-gray-500">Écart de prix : F et G par rapport à D</p>
              <p className="text-3xl font-semibold text-gray-900 mt-1">{formatEcart(ecart.ecart_pct)}</p>
              <p className="text-xs text-gray-500 mt-1">
                {formatEntier(ecart.prix_m2_median_fg)} €/m² pour F et G ({formatEntier(ecart.nb_fg)} ventes) contre{' '}
                {formatEntier(ecart.prix_m2_median_d)} €/m² pour D ({formatEntier(ecart.nb_d)} ventes).
              </p>
              <p className="text-xs text-gray-500 mt-1">Écart brut, non corrigé.</p>
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
            titre="Prix médian au m² selon la classe DPE du bâtiment"
            sousTitre={
              data.date_vente_min && data.prix_m2_min !== null && data.prix_m2_max !== null
                ? `Ventes depuis le ${formatDate(data.date_vente_min)} · prix entre ${formatEntier(data.prix_m2_min)} et ${formatEntier(data.prix_m2_max)} €/m²`
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
                au-dessus. Les médianes sont calculées par BigQuery de façon approchée : elles peuvent varier
                d’environ 0,2 % d’un calcul à l’autre.
              </p>
              <p>
                La note d’un bâtiment est la note médiane de ses DPE (arrêté 2021). Quand le nombre de DPE est
                pair, on retient la meilleure des deux notes centrales.
              </p>
              <p>
                Chaque bâtiment compte une seule transaction : la transaction représentative de la BDNB. Le prix au
                m² est celui du local vendu, pas celui de l’ensemble du bâtiment.
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
              colonneNom="Classe"
              colonneValeur="Prix médian (€/m²)"
              colonneDetail="Ventes"
              formater={formatEntier}
              mode={mode}
            />
          </CarteGraphique>

          <p className="text-xs text-gray-500">
            Prix : transaction DVF représentative de chaque bâtiment (BDNB, CSTB). Classes : DPE de l’arrêté 2021
            (ADEME) rattachés au bâtiment.
          </p>
        </div>
      )}
    </div>
  );
}
