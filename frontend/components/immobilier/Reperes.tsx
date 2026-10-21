'use client';

import type { ReactNode } from 'react';
import { PrixParisLigne, TypeLocal } from '@/lib/immobilierApi';
import { formatEntier, formatPourcentage, formatPrixM2 } from '@/lib/immobilier';
import { COULEURS } from './ImmobilierCharts';

// Paramètres
const ENCRE = '#0b0b0b';
// Échelle A à G : sept étapes consécutives de la rampe bleue de la palette (250 à 550), du plus clair au plus foncé
const RAMPE_ECHELLE = ['#86b6ef', '#6da7ec', '#5598e7', '#3987e5', '#2a78d6', '#256abf', '#1c5cab'];
const LETTRES = ['A', 'B', 'C', 'D', 'E', 'F', 'G'];
// Schéma de la médiane : abscisses des 9 ventes d'exemple (rangées par prix) et de la moyenne
const VENTES_X = [40, 80, 120, 160, 200, 240, 280, 320, 470];
const MEDIANE_X = 200;
const MOYENNE_X = 290;

// Carte dépliée par défaut, repliable
function CarteRepere({ titre, children }: { titre: string; children: ReactNode }) {
  return (
    <details open className="border rounded-lg bg-white p-4">
      <summary className="cursor-pointer select-none text-sm font-semibold text-gray-900">{titre}</summary>
      <div className="mt-3 space-y-3">{children}</div>
    </details>
  );
}

// ============================================================================
// Parc DPE : l'échelle de A à G
// ============================================================================

export function ReperesDpe() {
  return (
    <CarteRepere titre="Repère : l’échelle du DPE">
      <div>
        <div className="flex justify-between text-xs text-gray-500 mb-1">
          <span>Très économe</span>
          <span>Très énergivore</span>
        </div>
        <div className="grid grid-cols-7 gap-1">
          {LETTRES.map((lettre, i) => (
            <div
              key={lettre}
              className="rounded-md py-2 text-center text-lg font-semibold"
              style={{ backgroundColor: RAMPE_ECHELLE[i], color: i < 3 ? ENCRE : '#ffffff' }}
            >
              {lettre}
            </div>
          ))}
          <div className="col-span-5" />
          <div className="col-span-2 border-t-2 border-gray-400 pt-1 text-center text-xs text-gray-600">
            Passoires énergétiques
          </div>
        </div>
      </div>
      <p className="text-sm text-gray-600">
        Le DPE note un logement de A à G selon sa consommation d’énergie et ses émissions de gaz à effet de
        serre. Des restrictions de location s’appliquent progressivement aux logements les moins bien notés.
      </p>
    </CarteRepere>
  );
}

// ============================================================================
// Prix DVF : la médiane, avec le chiffre réel de Paris
// ============================================================================

// Exemple illustratif : neuf ventes rangées par prix ; la moyenne est tirée par une vente très chère
function SchemaMediane() {
  return (
    <svg
      viewBox="0 0 520 140"
      className="w-full h-auto"
      role="img"
      aria-label="Neuf ventes rangées par prix : la médiane est la cinquième, avec quatre ventes moins chères et quatre plus chères ; la moyenne est tirée vers la droite par une vente très chère"
    >
      <line x1={20} x2={500} y1={60} y2={60} stroke={COULEURS.axe} strokeWidth={1} />

      {/* Quatre ventes de chaque côté de la médiane */}
      <path d="M33,36 V30 H167 V36" fill="none" stroke={COULEURS.axe} strokeWidth={1} />
      <path d="M233,36 V30 H477 V36" fill="none" stroke={COULEURS.axe} strokeWidth={1} />
      <text x={100} y={22} textAnchor="middle" fontSize={11} fill={COULEURS.texteSecondaire}>
        4 ventes moins chères
      </text>
      <text x={355} y={22} textAnchor="middle" fontSize={11} fill={COULEURS.texteSecondaire}>
        4 ventes plus chères
      </text>

      {VENTES_X.map(x => (
        <circle
          key={x}
          cx={x}
          cy={60}
          r={x === MEDIANE_X ? 9 : 7}
          fill={COULEURS.slot1}
          stroke={x === MEDIANE_X ? ENCRE : COULEURS.surface}
          strokeWidth={2}
        />
      ))}

      <polygon points={`${MEDIANE_X},78 ${MEDIANE_X - 6},88 ${MEDIANE_X + 6},88`} fill={COULEURS.slot1} />
      <text x={MEDIANE_X} y={104} textAnchor="middle" fontSize={12} fontWeight={600} fill={ENCRE}>
        Médiane
      </text>

      <polygon points={`${MOYENNE_X},78 ${MOYENNE_X - 6},88 ${MOYENNE_X + 6},88`} fill={COULEURS.slot2} />
      <text x={MOYENNE_X} y={104} textAnchor="middle" fontSize={12} fontWeight={600} fill={ENCRE}>
        Moyenne
      </text>

      <text x={470} y={86} textAnchor="middle" fontSize={11} fill={COULEURS.texteSecondaire}>
        une vente très chère
      </text>

      <text x={20} y={130} fontSize={11} fill={COULEURS.texteDiscret}>
        Exemple illustratif : 9 ventes rangées par prix
      </text>
      <text x={500} y={130} textAnchor="end" fontSize={11} fill={COULEURS.texteDiscret}>
        prix croissant →
      </text>
    </svg>
  );
}

export function ReperesPrix({
  paris,
  typeLocal,
  annee,
  libelleType,
}: {
  paris: PrixParisLigne[];
  typeLocal: TypeLocal;
  annee: number | null;
  libelleType: string;
}) {
  const lignes = paris
    .filter(l => l.type_local === typeLocal && l.annee !== null && l.prix_m2_median !== null)
    .sort((a, b) => (a.annee as number) - (b.annee as number));
  const courante = lignes.find(l => l.annee === annee);
  const premiere = lignes[0];
  const variation =
    courante && premiere && premiere.annee !== annee
      ? (100 * ((courante.prix_m2_median as number) - (premiere.prix_m2_median as number))) /
        (premiere.prix_m2_median as number)
      : null;

  return (
    <CarteRepere titre="Repère : comprendre la médiane">
      <SchemaMediane />
      <p className="text-sm text-gray-600">
        La médiane est la valeur du milieu : la moitié des ventes est moins chère, l’autre moitié plus chère. La
        moyenne, elle, est tirée vers le haut par une seule vente très chère.
      </p>
      {courante && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div className="rounded-lg border bg-gray-50 p-3">
            <p className="text-xs text-gray-500">Paris entier, {annee}</p>
            <p className="text-2xl font-semibold text-gray-900">
              {formatPrixM2(courante.prix_m2_median as number)}
            </p>
            <p className="text-xs text-gray-500">
              médiane de {formatEntier(courante.nb_ventes)} ventes de {libelleType}
            </p>
          </div>
          {variation !== null && premiere && (
            <div className="rounded-lg border bg-gray-50 p-3">
              <p className="text-xs text-gray-500">Depuis {premiere.annee}</p>
              <p className="text-2xl font-semibold text-gray-900">
                {variation > 0 ? '+' : ''}
                {formatPourcentage(variation)}
              </p>
              <p className="text-xs text-gray-500">
                {formatPrixM2(premiere.prix_m2_median as number)} en {premiere.annee}
              </p>
            </div>
          )}
        </div>
      )}
    </CarteRepere>
  );
}

// ============================================================================
// Changements : un DPE refait, et la réforme de 2026
// ============================================================================

export function ReperesChangements() {
  return (
    <CarteRepere titre="Repère : un DPE refait">
      <div className="flex flex-wrap items-center gap-3 text-sm">
        <div className="rounded-md border bg-gray-50 px-3 py-2 text-gray-500">
          DPE précédent
          <p className="text-xs">retiré des données ouvertes</p>
        </div>
        <span className="text-gray-400">est remplacé par</span>
        <div className="rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-blue-700">
          DPE refait
          <p className="text-xs">affiché dans le tableau : date, adresse, étiquette</p>
        </div>
      </div>
      <div className="flex items-start gap-3 rounded-md border bg-gray-50 px-3 py-2 text-sm text-gray-700">
        <span className="shrink-0 rounded bg-blue-700 px-2 py-0.5 text-xs font-semibold text-white">
          1er janv. 2026
        </span>
        <span>
          Nouveau coefficient de l’électricité dans le calcul (2,3 → 1,9) : certains logements chauffés à
          l’électricité gagnent une lettre sans travaux. Ces DPE refaits sont ceux marqués « Recalcul 2026
          probable ».
        </span>
      </div>
    </CarteRepere>
  );
}
