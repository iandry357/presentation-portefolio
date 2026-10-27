'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { useAccess } from '@/components/AccessProvider';
import { cn } from '@/lib/utils';
import {
  AnalyseCellule, AnalyseResponse, DimensionAnalyse, FiltresAnalyse, SourceAnalyse, getBdnbAnalyse,
} from '@/lib/immobilierBdnbApi';
import { DIMENSIONS_ANALYSE, NON_RENSEIGNE, estVentes, libelleDimension, libelleModalite, minuscule } from '@/lib/immobilierBdnb';
import {
  ALERTE_REFORME_DPE, SEUIL_VENTES_FIABLES, alertePieces, attentionAnalyse, retenirAnalyse, voirAnalyse,
} from '@/lib/immobilierBdnbTextes';
import { formatEntier, formatPourcentage } from '@/lib/immobilier';
import {
  BarresHorizontales, CarteGraphique, COULEURS, Colonnes, Explication, ModeAffichage, Point,
} from '../ImmobilierCharts';
import AnalyseControles from './AnalyseControles';
import AnalyseTableau from './AnalyseTableau';
import Lecture from './Lecture';

// Paramètres
const SOURCE_DEFAUT: SourceAnalyse = 'ventes';
const AXE_DEFAUT: DimensionAnalyse = 'pieces';
const SEUIL_BARRES_HORIZONTALES = 8;   // au-delà, les libellés en colonnes ne tiennent plus sur un écran étroit
const COULEUR_FRAGILE = COULEURS.grille;

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

// Détail d'une barre : l'effectif ; pour les ventes, la fourchette (la moitié des ventes) et la mise en garde.
// comptage : la barre porte déjà le nombre de DPE, le détail donne sa part du total.
function detailPoint(cellule: AnalyseCellule, ventes: boolean, comptage: boolean): string {
  if (!ventes) {
    return comptage && cellule.part_pct !== null
      ? `${formatPourcentage(cellule.part_pct)} du total`
      : `${formatEntier(cellule.n)} DPE`;
  }
  const fourchette =
    cellule.q1 !== null && cellule.q3 !== null
      ? ` · la moitié des ventes entre ${formatEntier(cellule.q1)} et ${formatEntier(cellule.q3)} €/m²`
      : '';
  const fragile = cellule.n < SEUIL_VENTES_FIABLES ? ' · à lire avec prudence' : '';
  return `${formatEntier(cellule.n)} ventes${fourchette}${fragile}`;
}

// Source DPE, axe pièces : « non renseigné » (97 % des DPE) écrase les autres barres.
// On le retire et on recalcule les parts sur les DPE avec typologie ; la couverture est dite par le bandeau.
function sansNonRenseigne(data: AnalyseResponse): AnalyseResponse {
  const gardees = data.cellules.filter(c => c.modalites[0] !== NON_RENSEIGNE);
  const total = gardees.reduce((somme, c) => somme + c.n, 0);
  return {
    ...data,
    cellules: gardees.map(c => ({ ...c, part_pct: total ? Math.round((c.n / total) * 1000) / 10 : null })),
  };
}

export default function AnalyseView() {
  const { unlocked } = useAccess();
  const [source, setSource] = useState<SourceAnalyse>(SOURCE_DEFAUT);
  const [axe, setAxe] = useState<DimensionAnalyse>(AXE_DEFAUT);
  const [croiser, setCroiser] = useState<DimensionAnalyse | null>(null);
  const [filtres, setFiltres] = useState<FiltresAnalyse>({});
  const [mode, setMode] = useState<ModeAffichage>('graphique');
  const [data, setData] = useState<AnalyseResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const derniereRequete = useRef(0);

  const load = useCallback(async () => {
    const numero = ++derniereRequete.current;
    setLoading(true);
    setError(null);
    try {
      const reponse = await getBdnbAnalyse(source, croiser ? [axe, croiser] : [axe], filtres);
      if (numero === derniereRequete.current) setData(reponse);
    } catch (e) {
      if (numero === derniereRequete.current) setError(e instanceof Error ? e.message : 'Erreur de chargement');
    } finally {
      if (numero === derniereRequete.current) setLoading(false);
    }
  }, [source, axe, croiser, filtres]);

  // Relecture quand la sélection ou l'accès change : le seuil de 5 ne s'applique que verrouillé
  useEffect(() => {
    load();
  }, [load, unlocked]);

  const changerSource = (suivante: SourceAnalyse) => {
    if (suivante === source) return;
    const dimensions = DIMENSIONS_ANALYSE[suivante];
    setSource(suivante);
    setAxe(dimensions.includes(axe) ? axe : AXE_DEFAUT);
    setCroiser(croiser && dimensions.includes(croiser) ? croiser : null);
    setFiltres({});
  };

  const changerAxe = (suivant: DimensionAnalyse) => {
    setAxe(suivant);
    if (croiser === suivant) setCroiser(null);
  };

  // Tout ce qui est affiché vient de la dernière réponse (meta), pas de la sélection en cours
  const meta = data?.meta ?? null;
  const typologieSeule = meta?.source === 'dpe' && meta.axes.length === 1 && meta.axes[0] === 'pieces';
  const donnees = data && typologieSeule ? sansNonRenseigne(data) : data;
  // DPE par trimestre : le nombre de diagnostics est plus parlant que la part de chaque trimestre
  const comptage = meta?.source === 'dpe' && meta.axes.length === 1 && meta.axes[0] === 'trimestre';
  const ventes = !!meta && estVentes(meta.source);
  const unAxe = meta?.axes.length === 1;
  const libellesAxes = meta ? meta.axes.map(a => minuscule(libelleDimension(a, meta.source))) : [];
  const modalites = meta && meta.source === source ? meta.modalites : {};

  const points: Point[] =
    donnees && meta && unAxe
      ? donnees.cellules.flatMap(c => {
          const valeur = ventes ? c.mediane : comptage ? c.n : c.part_pct;
          if (valeur === null) return [];
          return [{
            nom: libelleModalite(meta.axes[0], c.modalites[0]),
            valeur,
            detail: detailPoint(c, ventes, comptage),
            couleur: ventes && c.n < SEUIL_VENTES_FIABLES ? COULEUR_FRAGILE : COULEURS.slot1,
          }];
        })
      : [];
  const avecFragile = ventes && (donnees?.cellules.some(c => c.n < SEUIL_VENTES_FIABLES) ?? false);

  const etiquetteUtilisee = !!meta && (meta.axes.includes('etiquette') || (filtres.etiquette?.length ?? 0) > 0);
  const formater = ventes || comptage ? formatEntier : formatPourcentage;
  const proprietesGraphique = {
    points,
    colonneNom: meta ? libelleDimension(meta.axes[0], meta.source) : '',
    colonneValeur: ventes ? 'Prix médian (€/m²)' : comptage ? 'Nombre de DPE' : 'Part des DPE',
    colonneDetail: ventes ? 'Détail' : comptage ? 'Part du total' : 'DPE',
    formater,
    mode,
  };

  return (
    <div className="space-y-6">
      <AnalyseControles
        source={source}
        onSource={changerSource}
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
            <Bandeau ton="alerte">{alertePieces(meta.recouvrement_typologie)}</Bandeau>
          )}

          {meta.seuil_applique && meta.nb_masquees > 0 && (
            <Bandeau>
              {formatEntier(meta.nb_masquees)} regroupement{meta.nb_masquees > 1 ? 's' : ''} de moins de {meta.seuil}{' '}
              {ventes ? 'ventes' : 'DPE'}
              {meta.nb_masquees > 1 ? ' sont masqués' : ' est masqué'}.
              Déverrouillez avec le bouton en haut de la page pour tout voir.
            </Bandeau>
          )}

          <CarteGraphique
            titre={`${ventes ? 'Prix médian au m²' : comptage ? 'Nombre de DPE' : typologieSeule ? 'Part des DPE avec typologie' : 'Part des DPE'} par ${libellesAxes.join(' et par ')}`}
            sousTitre={
              meta.trimestre_min && meta.trimestre_max
                ? `${ventes ? 'Ventes' : 'DPE établis'} de ${libelleModalite('trimestre', meta.trimestre_min)} à ${libelleModalite('trimestre', meta.trimestre_max)}` +
                  (ventes && meta.prix_m2_min !== null && meta.prix_m2_max !== null
                    ? ` · prix entre ${formatEntier(meta.prix_m2_min)} et ${formatEntier(meta.prix_m2_max)} €/m²`
                    : '')
                : undefined
            }
          >
            <Lecture
              voir={voirAnalyse(meta.source, meta.axes.map(a => libelleDimension(a, meta.source)), comptage)}
              retenir={retenirAnalyse(donnees ?? data)}
              attention={attentionAnalyse(data)}
            />

            <Explication titre="Détails de calcul">
              {ventes ? (
                <>
                  <p>
                    Ventes de logement du DVF (Etalab) : un appartement ou une maison par vente, sans local commercial.
                    Les prix hors de la fourchette de {formatEntier(meta.prix_m2_min ?? 0)} à {formatEntier(meta.prix_m2_max ?? 0)} €/m² sont écartés.
                  </p>
                  <p>
                    Le prix au m² est le prix de vente divisé par la surface bâtie du DVF (et non la surface Carrez des
                    annonces). Le prix médian est la valeur du milieu : la moitié des ventes en dessous, l’autre moitié
                    au-dessus. Le détail de chaque barre donne aussi la fourchette qui contient la moitié des ventes
                    « du milieu ».
                  </p>
                  <p>
                    L’étiquette d’un immeuble est la note médiane des DPE de ses logements (arrêté 2021) ; quand le nombre
                    de DPE est pair, on retient la meilleure des deux notes centrales. Ce n’est pas la note du logement
                    vendu. « Inconnue » : vente non reliée à un immeuble de la BDNB, ou immeuble sans DPE.
                  </p>
                  <p>
                    Une vente est reliée à un immeuble de la BDNB par sa parcelle cadastrale ou son adresse. Sur les ventes
                    de référence de la BDNB, le bon immeuble est retrouvé dans 97,8 % des cas.
                  </p>
                  {meta.source === 'ventes_bati' && (
                    <p>
                      Les attributs du bâti viennent de la BDNB (CSTB) : année de construction des fichiers fonciers (souvent
                      arrondie à la décennie dans le parc ancien), registre des copropriétés (« hors registre » veut dire absent
                      du registre, pas forcément sans copropriété), aléa d’inondation par débordement de cours d’eau, monument
                      historique et bâti patrimonial des plans locaux d’urbanisme. Une vente non reliée à un immeuble n’a aucun de ces attributs.
                    </p>
                  )}
                </>
              ) : (
                <>
                  <p>
                    DPE de l’arrêté 2021 (logements, méthode 3CL), classés par arrondissement d’après l’adresse de leur
                    immeuble. L’étiquette est celle du logement diagnostiqué.
                  </p>
                  <p>
                    Un DPE est établi à la vente, à la location ou pour un logement neuf : ce sont des logements
                    diagnostiqués, pas tout le parc parisien.
                  </p>
                  <p>
                    Le nombre de pièces vient de la typologie (T1, T2, T3…) que le diagnostiqueur peut renseigner : elle
                    est déclarative et peu renseignée. Elle donne une idée, pas une mesure de tout Paris.
                  </p>
                </>
              )}
              <p>
                Tant que l’accès est verrouillé, un regroupement de moins de {meta.seuil} {ventes ? 'ventes' : 'DPE'} n’est
                pas affiché : trop peu de cas pour une lecture fiable.
              </p>
            </Explication>

            {unAxe ? (
              <>
                <div className="flex flex-wrap items-center gap-4 mb-3 text-sm text-gray-600">
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
                {avecFragile && (
                  <p className="inline-flex items-center gap-1.5 mb-3 text-xs text-gray-600">
                    <span className="inline-block w-3 h-3 rounded-sm" style={{ backgroundColor: COULEUR_FRAGILE }} />
                    Moins de {SEUIL_VENTES_FIABLES} ventes : à lire avec prudence
                  </p>
                )}
                {points.length > SEUIL_BARRES_HORIZONTALES
                  ? <BarresHorizontales {...proprietesGraphique} />
                  : <Colonnes {...proprietesGraphique} />}
              </>
            ) : (
              <AnalyseTableau
                source={meta.source}
                axes={meta.axes as [DimensionAnalyse, DimensionAnalyse]}
                cellules={data.cellules}
                lignes={meta.modalites[meta.axes[0]] ?? []}
                colonnes={meta.modalites[meta.axes[1]] ?? []}
              />
            )}
          </CarteGraphique>

          <p className="text-xs text-gray-500">
            {ventes
              ? 'Ventes : DVF (Etalab). Immeubles et étiquettes : BDNB (CSTB) et DPE de l’arrêté 2021 (ADEME).'
              : 'DPE de l’arrêté 2021 (ADEME) reliés aux immeubles (BDNB, CSTB). Nombre de pièces : typologie ADEME.'}
          </p>
        </div>
      )}
    </div>
  );
}
