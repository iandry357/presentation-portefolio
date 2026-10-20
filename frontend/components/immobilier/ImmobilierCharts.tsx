'use client';

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { cn } from '@/lib/utils';
import { COULEURS } from '@/components/top-offres/TopCharts';
import type { ModeAffichage } from '@/components/top-offres/TopCharts';

// Cartes, palette et mode d'affichage viennent de Top Offres : un seul point de dépendance
export { CarteGraphique, COULEURS } from '@/components/top-offres/TopCharts';
export type { ModeAffichage } from '@/components/top-offres/TopCharts';

// Paramètres
const SURVOL = 'rgba(11,11,11,0.04)';
const COULEUR_DEFAUT = COULEURS.slot1;
const HAUTEUR_COLONNES = 280;
const PAS_BARRE = 28;          // hauteur allouée à chaque barre horizontale
const COMPACT = new Intl.NumberFormat('fr-FR', { notation: 'compact', maximumFractionDigits: 1 });

export interface Point {
  nom: string;                 // étiquette de la barre ou de la colonne
  valeur: number;
  detail?: string;             // précision affichée dans l'infobulle et dans le tableau
  couleur?: string;            // emphase : défaut COULEURS.slot1
}

interface Props {
  points: Point[];
  colonneNom: string;
  colonneValeur: string;
  colonneDetail?: string;
  formater: (valeur: number) => string;
  mode: ModeAffichage;
}

// ============================================================================
// Éléments communs
// ============================================================================

function Vide() {
  return <p className="text-sm text-gray-400 py-8 text-center">Aucune donnée pour ce filtre.</p>;
}

function Tableau({ colonnes, lignes }: { colonnes: string[]; lignes: string[][] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-xs text-gray-500 border-b">
            {colonnes.map((colonne, i) => (
              <th key={colonne} className={cn('py-1.5 font-medium', i > 0 && 'text-right')}>
                {colonne}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {lignes.map((ligne, i) => (
            <tr key={i} className="border-b last:border-0">
              {ligne.map((cellule, j) => (
                <td key={j} className={cn('py-1.5 text-gray-700', j > 0 && 'text-right tabular-nums')}>
                  {cellule}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function VueTableau({ points, colonneNom, colonneValeur, colonneDetail = 'Détail', formater }: Omit<Props, 'mode'>) {
  const avecDetail = points.some(p => p.detail);
  return (
    <Tableau
      colonnes={[colonneNom, colonneValeur, ...(avecDetail ? [colonneDetail] : [])]}
      lignes={points.map(p => [p.nom, formater(p.valeur), ...(avecDetail ? [p.detail ?? ''] : [])])}
    />
  );
}

// La valeur d'abord, le nom ensuite ; un trait court de la couleur de la marque
function InfobullePoint({
  active,
  payload,
  formater,
}: {
  active?: boolean;
  payload?: ReadonlyArray<{ payload?: Point }>;
  formater: (valeur: number) => string;
}) {
  const point = payload?.[0]?.payload;
  if (!active || !point) return null;
  return (
    <div className="rounded-md border bg-white px-3 py-2 shadow-sm text-xs">
      <p className="text-gray-500 mb-1">{point.nom}</p>
      <p className="flex items-center gap-2">
        <span
          className="inline-block w-3 h-0.5 rounded"
          style={{ backgroundColor: point.couleur ?? COULEUR_DEFAUT }}
        />
        <span className="font-semibold text-gray-900">{formater(point.valeur)}</span>
        {point.detail && <span className="text-gray-400">{point.detail}</span>}
      </p>
    </div>
  );
}

// ============================================================================
// Colonnes (étiquettes A à G, années)
// ============================================================================

export function Colonnes(props: Props) {
  const { points, formater, mode } = props;
  if (points.length === 0) return <Vide />;
  if (mode === 'tableau') return <VueTableau {...props} />;

  return (
    <ResponsiveContainer width="100%" height={HAUTEUR_COLONNES}>
      <BarChart data={points} margin={{ top: 20, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid vertical={false} stroke={COULEURS.grille} strokeWidth={1} />
        <XAxis
          dataKey="nom"
          tick={{ fontSize: 11, fill: COULEURS.texteSecondaire }}
          tickLine={false}
          axisLine={{ stroke: COULEURS.axe }}
          interval={0}
        />
        <YAxis
          tick={{ fontSize: 11, fill: COULEURS.texteDiscret }}
          tickLine={false}
          axisLine={false}
          allowDecimals={false}
          width={44}
          tickFormatter={(v: number) => COMPACT.format(v)}
        />
        <Tooltip cursor={{ fill: SURVOL }} content={<InfobullePoint formater={formater} />} />
        <Bar dataKey="valeur" radius={[4, 4, 0, 0]} maxBarSize={24}>
          {points.map(p => (
            <Cell key={p.nom} fill={p.couleur ?? COULEUR_DEFAUT} />
          ))}
          <LabelList
            dataKey="valeur"
            position="top"
            fontSize={11}
            fill={COULEURS.texteSecondaire}
            formatter={(valeur: unknown) => formater(Number(valeur))}
          />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

// ============================================================================
// Barres horizontales (arrondissements)
// ============================================================================

export function BarresHorizontales(props: Props) {
  const { points, formater, mode } = props;
  if (points.length === 0) return <Vide />;
  if (mode === 'tableau') return <VueTableau {...props} />;

  return (
    <ResponsiveContainer width="100%" height={points.length * PAS_BARRE + 16}>
      <BarChart
        data={points}
        layout="vertical"
        margin={{ top: 4, right: 80, left: 0, bottom: 4 }}
        barCategoryGap={8}
      >
        <XAxis type="number" hide />
        <YAxis
          type="category"
          dataKey="nom"
          width={48}
          tick={{ fontSize: 11, fill: COULEURS.texteSecondaire }}
          tickLine={false}
          axisLine={{ stroke: COULEURS.axe }}
          interval={0}
        />
        <Tooltip cursor={{ fill: SURVOL }} content={<InfobullePoint formater={formater} />} />
        <Bar dataKey="valeur" radius={[0, 4, 4, 0]} maxBarSize={20}>
          {points.map(p => (
            <Cell key={p.nom} fill={p.couleur ?? COULEUR_DEFAUT} />
          ))}
          <LabelList
            dataKey="valeur"
            position="right"
            fontSize={11}
            fill={COULEURS.texteSecondaire}
            formatter={(valeur: unknown) => formater(Number(valeur))}
          />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
