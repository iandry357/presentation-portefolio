'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { useAccess } from '@/components/AccessProvider';
import { cn } from '@/lib/utils';
import {
  CubeOrg, FiltresOrg, OrgAnalyseCellule, OrgAnalyseResponse, getOrgAnalyse,
} from '@/lib/immobilierOrgApi';
import {
  CUBES_ORG, SEUIL_VENTES_FIABLES, libelleDimensionOrg, libelleModaliteOrg, minuscule, trierCellules,
} from '@/lib/immobilierOrgCubes';
import { formatMois } from '@/lib/immobilierOrg';
import { formatEntier, formatPourcentage } from '@/lib/immobilier';
import { BarresHorizontales, CarteGraphique, COULEURS, Colonnes, Explication, Point } from '../ImmobilierCharts';
import Lecture from '../bdnb/Lecture';
import OrgControles from './OrgControles';
import OrgResultats from './OrgResultats';
import OrgTableau from './OrgTableau';

// Paramètres
const SEUIL_BARRES_HORIZONTALES = 8;   // au-delà, les libellés en colonnes ne tiennent plus sur un écran étroit
const COULEUR_FRAGILE = COULEURS.grille;
const VUES = [
  { id: 'graphique', libelle: 'Graphique' },
  { id: 'resultats', libelle: 'Résultats' },
] as const;
type Vue = (typeof VUES)[number]['id'];

const ALERTE_REFORME_DPE =
  'Le 1er janvier 2026, le coefficient de l’électricité dans le calcul du DPE est passé de 2,3 à 1,9 : certains logements chauffés à l’électricité ont gagné une lettre sans travaux. Comparer des étiquettes avant et après cette date demande de la prudence.';

function Bandeau({ children, ton = 'neutre' }: { children: ReactNode; ton?: 'neutre' | 'alerte' }) {
  return (
    <p
      className={cn(
        'text-sm border rounded-lg px-4 py-3',
        ton === 'alerte' ? 'text-amber-800 bg-amber-50 border-amber-200' : 'text-gray-600 bg-gray-50',
      )}
    >
      {children}
    </p>
  );
}

// Détail d'une barre : l'effectif ; pour les prix, la fourchette (la moitié des ventes) et la mise en garde
function detailPoint(c: OrgAnalyseCellule, prix: boolean, unite: string): string {
  if (!prix) {
    return [
      c.part_pct !== null ? `${formatPourcentage(c.part_pct)} du total` : `${formatEntier(c.n)} ${unite}`,
      c.nb_logements !== null ? `${formatEntier(c.nb_logements)} logements` : null,
      c.nb_remplacants ? `dont ${formatEntier(c.nb_remplacants)} remplaçants` : null,
    ].filter(Boolean).join(' · ');
  }
  const fourchette =
    c.q1 !== null && c.q3 !== null ? ` · la moitié des ventes entre ${formatEntier(c.q1)} et ${formatEntier(c.q3)} €/m²` : '';
  const fragile = c.n < SEUIL_VENTES_FIABLES ? ' · à lire avec prudence' : '';
  return `${formatEntier(c.n)} ${unite}${fourchette}${fragile}`;
}

export default function OrgAnalyse({ cube }: { cube: CubeOrg }) {
  const config = CUBES_ORG[cube];
  const { unlocked } = useAccess();
  const [axe, setAxe] = useState<string>(config.axeDefaut);
  const [croiser, setCroiser] = useState<string | null>(null);
  const [filtres, setFiltres] = useState<FiltresOrg>({});
  const [vue, setVue] = useState<Vue>('graphique');
  const [data, setData] = useState<OrgAnalyseResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const derniereRequete = useRef(0);

  const load = useCallback(async () => {
    const numero = ++derniereRequete.current;
    setLoading(true);
    setError(null);
    try {
      const reponse = await getOrgAnalyse(cube, croiser ? [axe, croiser] : [axe], filtres);
      if (numero === derniereRequete.current) setData(reponse);
    } catch (e) {
      if (numero === derniereRequete.current) setError(e instanceof Error ? e.message : 'Erreur de chargement');
    } finally {
      if (numero === derniereRequete.current) setLoading(false);
    }
  }, [cube, axe, croiser, filtres]);

  // Relecture quand la sélection ou l'accès change : le seuil de 5 ne s'applique que verrouillé
  useEffect(() => {
    load();
  }, [load, unlocked]);

  const changerAxe = (suivant: string) => {
    setAxe(suivant);
    if (croiser === suivant) setCroiser(null);
  };

  // Tout ce qui est affiché vient de la dernière réponse (meta), pas de la sélection en cours
  const meta = data?.meta ?? null;
  const prix = meta?.mesure === 'prix';
  const unAxe = meta?.axes.length === 1;
  const libelleAxe = (a: string) => minuscule(libelleDimensionOrg(a, cube));
  const modalites = meta ? meta.modalites : {};

  const cellules = data && meta ? trierCellules(meta.axes, data.cellules) : [];
  const points: Point[] =
    meta && unAxe
      ? cellules.flatMap(c => {
          const valeur = prix ? c.mediane : c.n;
          if (valeur === null) return [];
          return [{
            nom: libelleModaliteOrg(meta.axes[0], c.modalites[0]),
            valeur,
            detail: detailPoint(c, prix, config.unite),
            couleur: prix && c.n < SEUIL_VENTES_FIABLES ? COULEUR_FRAGILE : COULEURS.slot1,
          }];
        })
      : [];
  const avecFragile = !!prix && cellules.some(c => c.n < SEUIL_VENTES_FIABLES);

  // « À retenir » : calculé sur les groupes assez nombreux, rien d'écrit sinon
  let aRetenir: string | null = null;
  if (meta && unAxe) {
    const nom = (c: OrgAnalyseCellule) => libelleModaliteOrg(meta.axes[0], c.modalites[0]);
    if (prix) {
      const fiables = cellules.filter(c => c.mediane !== null && c.n >= SEUIL_VENTES_FIABLES);
      if (fiables.length >= 2) {
        const haut = fiables.reduce((a, b) => ((b.mediane ?? 0) > (a.mediane ?? 0) ? b : a));
        const bas = fiables.reduce((a, b) => ((b.mediane ?? 0) < (a.mediane ?? 0) ? b : a));
        aRetenir = `Prix médian le plus haut : ${nom(haut)} (${formatEntier(haut.mediane ?? 0)} €/m²) ; le plus bas : ${nom(bas)} (${formatEntier(bas.mediane ?? 0)} €/m²).`;
      }
    } else if (cellules.length >= 2) {
      const premier = cellules.reduce((a, b) => (b.n > a.n ? b : a));
      if (premier.part_pct !== null) {
        aRetenir = `Le groupe le plus nombreux : ${nom(premier)}, ${formatPourcentage(premier.part_pct)} des ${config.unite}.`;
      }
    }
  }

  const etiquetteUtilisee =
    !!meta && cube !== 'dvf' && cube !== 'batiment' && (meta.axes.includes('etiquette') || (filtres.etiquette?.length ?? 0) > 0);
  const formater = formatEntier;
  const proprietesGraphique = {
    points,
    colonneNom: meta ? libelleDimensionOrg(meta.axes[0], cube) : '',
    colonneValeur: prix ? 'Prix médian (€/m²)' : `Nombre de ${config.unite}`,
    colonneDetail: prix ? 'Détail' : 'Part du total',
    formater,
    mode: 'graphique' as const,
  };

  return (
    <div className="space-y-6">
      <OrgControles
        cube={cube}
        axe={axe}
        onAxe={changerAxe}
        croiser={croiser}
        onCroiser={setCroiser}
        modalites={modalites}
        filtres={filtres}
        onFiltres={setFiltres}
      />

      {error && <div className="text-sm text-red-600 bg-red-50 px-4 py-3 rounded-lg">{error}</div>}

      {!data && loading && <div className="h-64 border rounded-lg bg-white animate-pulse" />}

      {data && meta && (
        // Pendant un rechargement, le contenu précédent reste affiché en atténué
        <div className={cn('space-y-6 transition-opacity', loading && 'opacity-60')}>

          {etiquetteUtilisee && <Bandeau ton="alerte">{ALERTE_REFORME_DPE}</Bandeau>}

          {meta.recouvrement_typologie !== null && (
            <Bandeau ton="alerte">
              Le nombre de pièces n’est renseigné que pour {formatPourcentage(meta.recouvrement_typologie)} des DPE de cette
              sélection : les groupes par nombre de pièces ne décrivent pas tous les DPE.
            </Bandeau>
          )}

          {meta.seuil_applique && meta.nb_masquees > 0 && (
            <Bandeau>
              {formatEntier(meta.nb_masquees)} regroupement{meta.nb_masquees > 1 ? 's' : ''} de moins de {meta.seuil}{' '}
              {config.unite}
              {meta.nb_masquees > 1 ? ' sont masqués' : ' est masqué'}.
              Déverrouillez avec le bouton en haut de la page pour tout voir.
            </Bandeau>
          )}

          <CarteGraphique
            titre={`${prix ? 'Prix médian au m²' : `Nombre de ${config.unite}`} par ${meta.axes.map(libelleAxe).join(' et par ')}`}
            sousTitre={
              (meta.mois_min && meta.mois_max
                ? `${config.libelle} de ${formatMois(meta.mois_min)} à ${formatMois(meta.mois_max)}`
                : `${config.libelle} : état du parc au millésime, sans période`) +
              (prix && meta.prix_m2_min !== null && meta.prix_m2_max !== null
                ? ` · prix entre ${formatEntier(meta.prix_m2_min)} et ${formatEntier(meta.prix_m2_max)} €/m²`
                : '')
            }
          >
            <Lecture
              voir={`${prix ? 'Le prix médian au m²' : `Le nombre de ${config.unite}`}, pour chaque ${meta.axes.map(libelleAxe).join(' et chaque ')}.`}
              retenir={aRetenir}
            />

            <Explication titre="Détails de calcul">
              {config.explication.map(paragraphe => <p key={paragraphe}>{paragraphe}</p>)}
              {prix && meta.prix_m2_min !== null && meta.prix_m2_max !== null && (
                <p>
                  Les ventes dont le prix est hors de la fourchette de {formatEntier(meta.prix_m2_min)} à{' '}
                  {formatEntier(meta.prix_m2_max)} €/m² sont écartées de ces analyses (pas du tableau brut).
                </p>
              )}
              <p>
                Tant que l’accès est verrouillé, un regroupement de moins de {meta.seuil} {config.unite} n’est pas affiché :
                trop peu de cas pour une lecture fiable.
              </p>
            </Explication>

            <div className="inline-flex overflow-hidden rounded border border-gray-200 mb-3" role="group" aria-label="Affichage">
              {VUES.map(({ id, libelle }) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => setVue(id)}
                  aria-pressed={vue === id}
                  className={cn(
                    'px-4 py-1.5 text-sm transition-colors',
                    vue === id ? 'bg-blue-50 text-blue-700' : 'bg-white text-gray-600 hover:bg-gray-50',
                  )}
                >
                  {libelle}
                </button>
              ))}
            </div>

            {vue === 'resultats' ? (
              <OrgResultats cube={cube} meta={meta} cellules={data.cellules} />
            ) : unAxe ? (
              <>
                {avecFragile && (
                  <p className="inline-flex items-center gap-1.5 mb-3 ml-3 text-xs text-gray-600">
                    <span className="inline-block w-3 h-3 rounded-sm" style={{ backgroundColor: COULEUR_FRAGILE }} />
                    Moins de {SEUIL_VENTES_FIABLES} ventes : à lire avec prudence
                  </p>
                )}
                {points.length > SEUIL_BARRES_HORIZONTALES
                  ? <BarresHorizontales {...proprietesGraphique} />
                  : <Colonnes {...proprietesGraphique} />}
              </>
            ) : (
              <OrgTableau
                cube={cube}
                prix={!!prix}
                axes={meta.axes as [string, string]}
                cellules={data.cellules}
                lignes={meta.modalites[meta.axes[0]] ?? []}
                colonnes={meta.modalites[meta.axes[1]] ?? []}
              />
            )}
          </CarteGraphique>

          <p className="text-xs text-gray-500">{config.source}</p>
        </div>
      )}
    </div>
  );
}
