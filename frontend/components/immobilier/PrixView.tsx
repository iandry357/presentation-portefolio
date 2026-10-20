'use client';

import { useCallback, useEffect, useState } from 'react';
import { useAccess } from '@/components/AccessProvider';
import { cn } from '@/lib/utils';
import { PrixResponse, TypeLocal, getPrix } from '@/lib/immobilierApi';
import {
  ARRONDISSEMENTS,
  CLASSE_CHAMP,
  formatEntier,
  formatPrixM2,
  libelleArrondissement,
} from '@/lib/immobilier';
import { BarresHorizontales, CarteGraphique, COULEURS, Colonnes, ModeAffichage, Point } from './ImmobilierCharts';

// Paramètres
const TYPES: { id: TypeLocal; label: string }[] = [
  { id: 'Appartement', label: 'Appartements' },
  { id: 'Maison', label: 'Maisons' },
];

export default function PrixView() {
  const { unlocked } = useAccess();
  const [data, setData] = useState<PrixResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [typeLocal, setTypeLocal] = useState<TypeLocal>('Appartement');
  const [arrondissement, setArrondissement] = useState<number | null>(null);
  const [anneeChoisie, setAnneeChoisie] = useState<number | null>(null);
  const [mode, setMode] = useState<ModeAffichage>('graphique');

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await getPrix());
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

  const lignes = (data?.lignes ?? []).filter(l => l.type_local === typeLocal && l.prix_m2_median !== null);
  const annees = [...new Set(lignes.map(l => l.annee).filter((a): a is number => a !== null))].sort(
    (a, b) => b - a,
  );
  const annee = anneeChoisie !== null && annees.includes(anneeChoisie) ? anneeChoisie : (annees[0] ?? null);

  // Prix médian par arrondissement pour l'année choisie ; l'arrondissement choisi en emphase
  const parArrondissement: Point[] = lignes
    .filter(l => l.annee === annee && l.arrondissement !== null)
    .map(l => ({
      nom: libelleArrondissement(l.arrondissement),
      valeur: l.prix_m2_median as number,
      detail: `${formatEntier(l.nb_ventes)} ventes`,
      couleur:
        arrondissement === null || arrondissement === l.arrondissement ? COULEURS.slot1 : COULEURS.axe,
    }))
    .sort((a, b) => b.valeur - a.valeur);

  // Évolution par année : seulement pour un arrondissement (une médiane de médianes n'est pas une médiane)
  const parAnnee: Point[] =
    arrondissement === null
      ? []
      : lignes
          .filter(l => l.arrondissement === arrondissement && l.annee !== null)
          .sort((a, b) => (a.annee as number) - (b.annee as number))
          .map(l => ({
            nom: String(l.annee),
            valeur: l.prix_m2_median as number,
            detail: `${formatEntier(l.nb_ventes)} ventes`,
          }));

  const libelleType = TYPES.find(t => t.id === typeLocal)?.label.toLowerCase() ?? '';

  return (
    <div className="space-y-6">

      {/* Filtres : une seule ligne, au-dessus de ce qu'ils portent */}
      <div className="flex flex-wrap items-center gap-4 text-sm text-gray-600">
        <label className="inline-flex items-center gap-2">
          Type
          <select
            value={typeLocal}
            onChange={e => setTypeLocal(e.target.value as TypeLocal)}
            className={CLASSE_CHAMP}
          >
            {TYPES.map(t => (
              <option key={t.id} value={t.id}>{t.label}</option>
            ))}
          </select>
        </label>
        <label className="inline-flex items-center gap-2">
          Arrondissement
          <select
            value={arrondissement ?? ''}
            onChange={e => setArrondissement(e.target.value ? Number(e.target.value) : null)}
            className={CLASSE_CHAMP}
          >
            <option value="">Tous</option>
            {ARRONDISSEMENTS.map(n => (
              <option key={n} value={n}>{libelleArrondissement(n)}</option>
            ))}
          </select>
        </label>
        <label className="inline-flex items-center gap-2">
          Année
          <select
            value={annee ?? ''}
            onChange={e => setAnneeChoisie(Number(e.target.value))}
            disabled={annees.length === 0}
            className={CLASSE_CHAMP}
          >
            {annees.map(a => (
              <option key={a} value={a}>{a}</option>
            ))}
          </select>
        </label>
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

          {data.seuil_applique && data.nb_masquees > 0 && (
            <p className="text-sm text-gray-600 bg-gray-50 border rounded-lg px-4 py-3">
              {formatEntier(data.nb_masquees)} combinaisons de moins de {data.seuil} ventes sont masquées.
              Déverrouillez avec le bouton en haut de la page pour tout voir.
            </p>
          )}

          <CarteGraphique
            titre="Prix médian au m² par arrondissement"
            sousTitre={
              annee === null
                ? 'Aucune donnée'
                : arrondissement === null
                  ? `Ventes de ${libelleType} en ${annee}`
                  : `Ventes de ${libelleType} en ${annee} · ${libelleArrondissement(arrondissement)} en bleu, les autres arrondissements en gris`
            }
          >
            <BarresHorizontales
              points={parArrondissement}
              colonneNom="Arrondissement"
              colonneValeur="Prix médian"
              colonneDetail="Ventes"
              formater={formatPrixM2}
              mode={mode}
            />
          </CarteGraphique>

          <CarteGraphique
            titre="Évolution du prix médian au m²"
            sousTitre={
              arrondissement === null
                ? 'Choisissez un arrondissement pour voir son évolution par année'
                : `Ventes de ${libelleType} · ${libelleArrondissement(arrondissement)}`
            }
          >
            {arrondissement === null ? (
              <p className="text-sm text-gray-400 py-8 text-center">Aucun arrondissement choisi.</p>
            ) : (
              <Colonnes
                points={parAnnee}
                colonneNom="Année"
                colonneValeur="Prix médian"
                colonneDetail="Ventes"
                formater={formatPrixM2}
                mode={mode}
              />
            )}
          </CarteGraphique>

          <p className="text-xs text-gray-500">
            Valeur foncière rapportée à la surface bâtie, ventes d’un seul logement (dépendances comprises),
            données DVF (Etalab).
          </p>
        </div>
      )}
    </div>
  );
}
