'use client';

import { BarChart, Bar, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { formatPourcentage } from '@/lib/immobilier';
import { COULEURS } from '../ImmobilierCharts';
import type { ModeAffichage } from '../ImmobilierCharts';

// Paramètres
const SURVOL = 'rgba(11,11,11,0.04)';
const PAS_BARRE = 40;          // hauteur allouée à chaque barre
const EPAISSEUR_MAX = 24;
const LARGEUR_NOMS = 120;
const ECART = 2;               // interstice entre segments, en px (trait de la couleur du fond)

export interface SerieEmpilee {
  id: string;
  libelle: string;
  couleur: string;
}

export interface BarreEmpilee {
  nom: string;                           // étiquette de la barre (période, énergie)
  detail?: string;                       // base de la barre, affichée sous le nom (ex. « 490 173 DPE »)
  valeurs: Record<string, number>;       // valeur par série (id de la série -> valeur) ; chaque barre est ramenée à 100 %
}

interface Props {
  barres: BarreEmpilee[];
  series: SerieEmpilee[];                // dans l'ordre d'empilement
  mode: ModeAffichage;
  colonneNom: string;
  colonneDetail?: string;
  formaterEffectif?: (valeur: number) => string;   // si fourni, l'effectif de chaque segment s'ajoute au pourcentage
}

function totalBarre(barre: BarreEmpilee, series: SerieEmpilee[]): number {
  return series.reduce((somme, s) => somme + (barre.valeurs[s.id] ?? 0), 0);
}

function part(valeur: number, total: number): string {
  return total ? formatPourcentage((100 * valeur) / total) : '—';
}

// ============================================================================
// Éléments communs
// ============================================================================

function Legende({ series }: { series: SerieEmpilee[] }) {
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1 mb-3 text-xs text-gray-600" aria-label="Légende">
      {series.map(s => (
        <li key={s.id} className="inline-flex items-center gap-1.5">
          <span className="inline-block w-3 h-3 rounded-sm" style={{ backgroundColor: s.couleur }} />
          {s.libelle}
        </li>
      ))}
    </ul>
  );
}

// Nom de la barre, avec sa base en plus petit dessous : un pourcentage sur peu de logements doit se voir
function EtiquetteBarre({
  x = 0,
  y = 0,
  payload,
  barres,
}: {
  x?: number;
  y?: number;
  payload?: { value: string };
  barres: BarreEmpilee[];
}) {
  const detail = barres.find(b => b.nom === payload?.value)?.detail;
  return (
    <text x={x - 6} y={y} textAnchor="end" fontSize={11} fill={COULEURS.texteSecondaire}>
      <tspan x={x - 6} dy={detail ? -2 : 4}>{payload?.value}</tspan>
      {detail && (
        <tspan x={x - 6} dy={12} fontSize={10} fill={COULEURS.texteDiscret}>{detail}</tspan>
      )}
    </text>
  );
}

// Une infobulle pour toutes les séries : la valeur d'abord, le nom ensuite
function Infobulle({
  active,
  payload,
  barres,
  series,
  formaterEffectif,
}: {
  active?: boolean;
  payload?: ReadonlyArray<{ payload?: { nom: string } }>;
  barres: BarreEmpilee[];
  series: SerieEmpilee[];
  formaterEffectif?: (valeur: number) => string;
}) {
  const barre = barres.find(b => b.nom === payload?.[0]?.payload?.nom);
  if (!active || !barre) return null;
  const total = totalBarre(barre, series);
  return (
    <div className="rounded-md border bg-white px-3 py-2 shadow-sm text-xs">
      <p className="text-gray-500 mb-1">
        {barre.nom}
        {barre.detail ? ` · ${barre.detail}` : ''}
      </p>
      {series.map(s => {
        const valeur = barre.valeurs[s.id] ?? 0;
        return (
          <p key={s.id} className="flex items-center gap-2">
            <span className="inline-block w-3 h-0.5 rounded" style={{ backgroundColor: s.couleur }} />
            <span className="font-semibold text-gray-900">{part(valeur, total)}</span>
            <span className="text-gray-500">{s.libelle}</span>
            {formaterEffectif && <span className="text-gray-400">{formaterEffectif(valeur)}</span>}
          </p>
        );
      })}
    </div>
  );
}

// ============================================================================
// Vue tableau : toutes les valeurs, sans passer par l'infobulle
// ============================================================================

function VueTableau({ barres, series, colonneNom, colonneDetail = 'Base', formaterEffectif }: Omit<Props, 'mode'>) {
  const avecDetail = barres.some(b => b.detail);
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-xs text-gray-500 border-b">
            <th className="py-1.5 font-medium">{colonneNom}</th>
            {series.map(s => (
              <th key={s.id} className="py-1.5 font-medium text-right">{s.libelle}</th>
            ))}
            {avecDetail && <th className="py-1.5 font-medium text-right">{colonneDetail}</th>}
          </tr>
        </thead>
        <tbody>
          {barres.map(barre => {
            const total = totalBarre(barre, series);
            return (
              <tr key={barre.nom} className="border-b last:border-0">
                <td className="py-1.5 text-gray-700">{barre.nom}</td>
                {series.map(s => {
                  const valeur = barre.valeurs[s.id] ?? 0;
                  return (
                    <td key={s.id} className="py-1.5 text-right tabular-nums text-gray-700">
                      {part(valeur, total)}
                      {formaterEffectif && (
                        <span className="block text-xs text-gray-400">{formaterEffectif(valeur)}</span>
                      )}
                    </td>
                  );
                })}
                {avecDetail && (
                  <td className="py-1.5 text-right tabular-nums text-gray-700">{barre.detail ?? ''}</td>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ============================================================================
// Barres horizontales empilées à 100 %
// ============================================================================

export default function BarresEmpilees(props: Props) {
  const { barres, series, mode, formaterEffectif } = props;
  if (barres.length === 0) {
    return <p className="text-sm text-gray-400 py-8 text-center">Aucune donnée.</p>;
  }
  if (mode === 'tableau') return <VueTableau {...props} />;

  const donnees = barres.map(b => ({
    nom: b.nom,
    ...Object.fromEntries(series.map(s => [s.id, b.valeurs[s.id] ?? 0])),
  }));

  return (
    <div>
      <Legende series={series} />
      <ResponsiveContainer width="100%" height={barres.length * PAS_BARRE + 28}>
        <BarChart
          data={donnees}
          layout="vertical"
          stackOffset="expand"
          margin={{ top: 4, right: 12, left: 0, bottom: 4 }}
          barCategoryGap={8}
        >
          <XAxis
            type="number"
            ticks={[0, 0.5, 1]}
            tickFormatter={(v: number) => `${Math.round(v * 100)} %`}
            tick={{ fontSize: 11, fill: COULEURS.texteDiscret }}
            tickLine={false}
            axisLine={{ stroke: COULEURS.axe }}
          />
          <YAxis
            type="category"
            dataKey="nom"
            width={LARGEUR_NOMS}
            tick={<EtiquetteBarre barres={barres} />}
            tickLine={false}
            axisLine={{ stroke: COULEURS.axe }}
            interval={0}
          />
          <Tooltip
            cursor={{ fill: SURVOL }}
            content={<Infobulle barres={barres} series={series} formaterEffectif={formaterEffectif} />}
          />
          {series.map((s, i) => (
            <Bar
              key={s.id}
              dataKey={s.id}
              stackId="part"
              fill={s.couleur}
              stroke={COULEURS.surface}
              strokeWidth={ECART}
              maxBarSize={EPAISSEUR_MAX}
              radius={i === series.length - 1 ? [0, 4, 4, 0] : 0}
              isAnimationActive={false}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
