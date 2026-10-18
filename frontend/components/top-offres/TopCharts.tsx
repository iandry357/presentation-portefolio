'use client';

import type { ReactNode } from 'react';
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
import { PointJour, formatDateCourte } from '@/lib/topOffres';

// ============================================================================
// Couleurs : palette de référence du guide de visualisation (thème clair)
// ============================================================================

export const COULEURS = {
  surface: '#ffffff',          // fond des cartes (bg-white) : sert aux interstices entre segments
  texteSecondaire: '#52514e',
  texteDiscret: '#898781',
  grille: '#e1e0d9',
  axe: '#c3c2b7',
  slot1: '#2a78d6',            // catégoriel, série 1 (bleu)
  slot2: '#eb6834',            // catégoriel, série 2 (orange)
  ordinal500: '#256abf',       // rampe ordinale du bleu, du plus foncé au plus clair
  ordinal350: '#5598e7',
  ordinal250: '#86b6ef',
} as const;

const SURVOL = 'rgba(11,11,11,0.04)';

export type ModeAffichage = 'graphique' | 'tableau';

export interface Barre {
  nom: string;
  nb: number;
  couleur: string;
}

// ============================================================================
// Éléments communs
// ============================================================================

export function CarteGraphique({
  titre,
  sousTitre,
  className,
  children,
}: {
  titre: string;
  sousTitre?: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <section className={cn('border rounded-lg bg-white p-4', className)}>
      <h3 className="text-sm font-semibold text-gray-900">{titre}</h3>
      {sousTitre && <p className="text-xs text-gray-500 mt-0.5">{sousTitre}</p>}
      <div className="mt-3">{children}</div>
    </section>
  );
}

function Vide() {
  return <p className="text-sm text-gray-400 py-8 text-center">Aucune donnée pour cette période.</p>;
}

function Tableau({ colonnes, lignes }: { colonnes: string[]; lignes: (string | number)[][] }) {
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
                <td
                  key={j}
                  className={cn('py-1.5 text-gray-700', j > 0 && 'text-right tabular-nums')}
                >
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

function Legende({ elements }: { elements: { nom: string; couleur: string; detail?: string }[] }) {
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-600 mb-2">
      {elements.map(element => (
        <li key={element.nom} className="inline-flex items-center gap-1.5">
          <span className="inline-block w-3 h-3 rounded-sm" style={{ backgroundColor: element.couleur }} />
          {element.nom}
          {element.detail && <span className="text-gray-400">{element.detail}</span>}
        </li>
      ))}
    </ul>
  );
}

interface LigneInfobulle {
  nom: string;
  valeur: number;
  couleur: string;
  detail?: string;
}

// La valeur d'abord, le nom ensuite ; un trait court de la couleur de la série
function Infobulle({ titre, lignes }: { titre?: string; lignes: LigneInfobulle[] }) {
  return (
    <div className="rounded-md border bg-white px-3 py-2 shadow-sm text-xs">
      {titre && <p className="text-gray-500 mb-1">{titre}</p>}
      {lignes.map(ligne => (
        <p key={ligne.nom} className="flex items-center gap-2">
          <span className="inline-block w-3 h-0.5 rounded" style={{ backgroundColor: ligne.couleur }} />
          <span className="font-semibold text-gray-900">{ligne.valeur}</span>
          <span className="text-gray-500">{ligne.nom}</span>
          {ligne.detail && <span className="text-gray-400">{ligne.detail}</span>}
        </p>
      ))}
    </div>
  );
}

function tronquer(texte: string, max: number): string {
  return texte.length > max ? `${texte.slice(0, max - 1)}…` : texte;
}

// ============================================================================
// À lire et zone grise par jour : colonnes empilées
// ============================================================================

type PointAffiche = PointJour & { libelle: string };

function InfobulleColonnes({
  active,
  payload,
}: {
  active?: boolean;
  payload?: ReadonlyArray<{ payload?: PointAffiche }>;
}) {
  const point = payload?.[0]?.payload;
  if (!active || !point) return null;
  return (
    <Infobulle
      titre={point.libelle}
      lignes={[
        { nom: 'À lire', valeur: point.a_lire, couleur: COULEURS.ordinal500 },
        { nom: 'Zone grise', valeur: point.zone_grise, couleur: COULEURS.ordinal250 },
      ]}
    />
  );
}

export function ColonnesParJour({ serie, mode }: { serie: PointJour[]; mode: ModeAffichage }) {
  if (serie.length === 0) return <Vide />;

  if (mode === 'tableau') {
    return (
      <Tableau
        colonnes={['Jour', 'À lire', 'Zone grise']}
        lignes={serie.map(p => [formatDateCourte(p.jour), p.a_lire, p.zone_grise])}
      />
    );
  }

  const donnees: PointAffiche[] = serie.map(p => ({ ...p, libelle: formatDateCourte(p.jour) }));

  return (
    <>
      <Legende
        elements={[
          { nom: 'À lire', couleur: COULEURS.ordinal500 },
          { nom: 'Zone grise', couleur: COULEURS.ordinal250 },
        ]}
      />
      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={donnees} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid vertical={false} stroke={COULEURS.grille} strokeWidth={1} />
          <XAxis
            dataKey="libelle"
            tick={{ fontSize: 11, fill: COULEURS.texteDiscret }}
            tickLine={false}
            axisLine={{ stroke: COULEURS.axe }}
            interval="preserveStartEnd"
          />
          <YAxis
            tick={{ fontSize: 11, fill: COULEURS.texteDiscret }}
            tickLine={false}
            axisLine={false}
            allowDecimals={false}
            width={36}
          />
          <Tooltip cursor={{ fill: SURVOL }} content={<InfobulleColonnes />} />
          <Bar
            dataKey="a_lire"
            stackId="liste"
            fill={COULEURS.ordinal500}
            stroke={COULEURS.surface}
            strokeWidth={2}
            maxBarSize={24}
          />
          <Bar
            dataKey="zone_grise"
            stackId="liste"
            fill={COULEURS.ordinal250}
            stroke={COULEURS.surface}
            strokeWidth={2}
            maxBarSize={24}
            radius={[4, 4, 0, 0]}
          />
        </BarChart>
      </ResponsiveContainer>
    </>
  );
}

// ============================================================================
// Barres horizontales triées (catégories, cibles, secteurs)
// ============================================================================

function InfobulleBarre({
  active,
  payload,
}: {
  active?: boolean;
  payload?: ReadonlyArray<{ payload?: Barre }>;
}) {
  const barre = payload?.[0]?.payload;
  if (!active || !barre) return null;
  return <Infobulle lignes={[{ nom: barre.nom, valeur: barre.nb, couleur: barre.couleur }]} />;
}

export function BarresHorizontales({
  barres,
  colonneNom,
  mode,
}: {
  barres: Barre[];
  colonneNom: string;
  mode: ModeAffichage;
}) {
  if (barres.length === 0) return <Vide />;

  if (mode === 'tableau') {
    return <Tableau colonnes={[colonneNom, 'Offres']} lignes={barres.map(b => [b.nom, b.nb])} />;
  }

  const donnees = barres.map(b => ({ ...b, nomCourt: tronquer(b.nom, 26) }));

  return (
    <ResponsiveContainer width="100%" height={barres.length * 34 + 16}>
      <BarChart
        data={donnees}
        layout="vertical"
        margin={{ top: 4, right: 40, left: 0, bottom: 4 }}
        barCategoryGap={10}
      >
        <XAxis type="number" hide />
        <YAxis
          type="category"
          dataKey="nomCourt"
          width={150}
          tick={{ fontSize: 11, fill: COULEURS.texteSecondaire }}
          tickLine={false}
          axisLine={{ stroke: COULEURS.axe }}
          interval={0}
        />
        <Tooltip cursor={{ fill: SURVOL }} content={<InfobulleBarre />} />
        <Bar dataKey="nb" radius={[0, 4, 4, 0]} maxBarSize={24}>
          {donnees.map(d => (
            <Cell key={d.nom} fill={d.couleur} />
          ))}
          <LabelList dataKey="nb" position="right" fontSize={11} fill={COULEURS.texteSecondaire} />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

// ============================================================================
// Répartition en une barre à 100 % (type d'annonceur)
// ============================================================================

function InfobulleRepartition({
  active,
  parts,
  total,
}: {
  active?: boolean;
  parts: Barre[];
  total: number;
}) {
  if (!active) return null;
  return (
    <Infobulle
      lignes={parts.map(p => ({
        nom: p.nom,
        valeur: p.nb,
        couleur: p.couleur,
        detail: `${Math.round((100 * p.nb) / total)} %`,
      }))}
    />
  );
}

export function BarreRepartition({ parts, mode }: { parts: Barre[]; mode: ModeAffichage }) {
  const total = parts.reduce((somme, p) => somme + p.nb, 0);
  if (total === 0) return <Vide />;

  const pct = (nb: number) => `${Math.round((100 * nb) / total)} %`;

  if (mode === 'tableau') {
    return (
      <Tableau
        colonnes={['Type', 'Offres', 'Part']}
        lignes={parts.map(p => [p.nom, p.nb, pct(p.nb)])}
      />
    );
  }

  // Une seule ligne, une clé par part (les noms ne servent pas de clés de données)
  const ligne: Record<string, number | string> = { nom: '' };
  parts.forEach((p, i) => {
    ligne[`p${i}`] = p.nb;
  });

  return (
    <>
      <Legende
        elements={parts.map(p => ({ nom: p.nom, couleur: p.couleur, detail: `${p.nb} · ${pct(p.nb)}` }))}
      />
      <ResponsiveContainer width="100%" height={56}>
        <BarChart
          data={[ligne]}
          layout="vertical"
          stackOffset="expand"
          margin={{ top: 0, right: 0, left: 0, bottom: 0 }}
        >
          <XAxis type="number" hide domain={[0, 1]} />
          <YAxis type="category" dataKey="nom" hide />
          <Tooltip cursor={false} content={<InfobulleRepartition parts={parts} total={total} />} />
          {parts.map((p, i) => (
            <Bar
              key={p.nom}
              dataKey={`p${i}`}
              stackId="part"
              fill={p.couleur}
              stroke={COULEURS.surface}
              strokeWidth={2}
              maxBarSize={24}
              radius={i === 0 ? [4, 0, 0, 4] : i === parts.length - 1 ? [0, 4, 4, 0] : 0}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </>
  );
}
