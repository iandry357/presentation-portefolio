'use client';

import { useEffect, useMemo, useState } from 'react';
import { libelleArrondissement } from '@/lib/immobilier';
import { COULEURS } from './ImmobilierCharts';
import type { Point } from './ImmobilierCharts';

// Paramètres
const URL_CONTOURS = '/immobilier/arrondissements-paris.geojson';   // Ville de Paris (Paris Data), licence ODbL
const LARGEUR = 520;
const MARGE = 8;
// Rampe séquentielle bleue de la palette de référence : étapes 100, 250, 400, 550, 700
const RAMPE = ['#cde2fb', '#86b6ef', '#3987e5', '#1c5cab', '#0d366b'];
const COULEUR_SANS_DONNEE = COULEURS.grille;
const ENCRE = '#0b0b0b';

type Position = number[];
type Anneau = Position[];

interface Entite {
  properties: { c_ar: number };
  geometry:
    | { type: 'Polygon'; coordinates: Anneau[] }
    | { type: 'MultiPolygon'; coordinates: Anneau[][] };
}

interface Contours {
  features: Entite[];
}

interface Forme {
  id: number;                    // numéro d'arrondissement (1 à 20)
  chemin: string;
  centre: [number, number];
}

// Les contours sont téléchargés une seule fois, même si la vue est montée plusieurs fois
let chargement: Promise<Contours> | null = null;

function chargerContours(): Promise<Contours> {
  if (!chargement) {
    const requete = fetch(URL_CONTOURS).then(r => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json() as Promise<Contours>;
    });
    requete.catch(() => {
      chargement = null;         // permet une nouvelle tentative
    });
    chargement = requete;
  }
  return chargement;
}

// Centre de gravité d'un anneau fermé (formule du polygone)
function centroide(anneau: [number, number][]): [number, number] {
  let aire = 0;
  let cx = 0;
  let cy = 0;
  for (let i = 0; i < anneau.length - 1; i++) {
    const [x0, y0] = anneau[i];
    const [x1, y1] = anneau[i + 1];
    const croise = x0 * y1 - x1 * y0;
    aire += croise;
    cx += (x0 + x1) * croise;
    cy += (y0 + y1) * croise;
  }
  return aire === 0 ? anneau[0] : [cx / (3 * aire), cy / (3 * aire)];
}

// Longitude / latitude -> coordonnées du dessin (projection plane corrigée de la latitude de Paris)
function construireFormes(contours: Contours): { formes: Forme[]; hauteur: number } {
  const polygones = (e: Entite): Anneau[][] =>
    e.geometry.type === 'Polygon' ? [e.geometry.coordinates] : e.geometry.coordinates;

  let minLon = Infinity;
  let maxLon = -Infinity;
  let minLat = Infinity;
  let maxLat = -Infinity;
  for (const e of contours.features) {
    for (const polygone of polygones(e)) {
      for (const anneau of polygone) {
        for (const [lon, lat] of anneau) {
          minLon = Math.min(minLon, lon);
          maxLon = Math.max(maxLon, lon);
          minLat = Math.min(minLat, lat);
          maxLat = Math.max(maxLat, lat);
        }
      }
    }
  }

  const kx = Math.cos((((minLat + maxLat) / 2) * Math.PI) / 180);
  const echelle = (LARGEUR - 2 * MARGE) / ((maxLon - minLon) * kx);
  const hauteur = (maxLat - minLat) * echelle + 2 * MARGE;
  const projeter = ([lon, lat]: Position): [number, number] => [
    MARGE + (lon - minLon) * kx * echelle,
    MARGE + (maxLat - lat) * echelle,
  ];

  const formes = contours.features.map(e => {
    const parties = polygones(e).map(polygone => polygone.map(anneau => anneau.map(projeter)));
    const chemin = parties
      .flatMap(polygone =>
        polygone.map(
          anneau => `M${anneau.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join('L')}Z`,
        ),
      )
      .join('');
    const principal = parties.reduce((a, b) => (b[0].length > a[0].length ? b : a));
    return { id: e.properties.c_ar, chemin, centre: centroide(principal[0]) };
  });

  return { formes, hauteur };
}

interface Props {
  points: Point[];               // `id` = numéro d'arrondissement ; les points sans `id` sont ignorés
  selection: number | null;
  onSelect: (id: number) => void;
  formater: (valeur: number) => string;
  legende: string;
}

export default function CarteParis({ points, selection, onSelect, formater, legende }: Props) {
  const [contours, setContours] = useState<Contours | null>(null);
  const [erreur, setErreur] = useState(false);
  const [survol, setSurvol] = useState<number | null>(null);
  const [pointeur, setPointeur] = useState<{ x: number; y: number } | null>(null);

  useEffect(() => {
    chargerContours().then(setContours).catch(() => setErreur(true));
  }, []);

  const geometrie = useMemo(() => (contours ? construireFormes(contours) : null), [contours]);

  if (erreur) {
    return <p className="text-sm text-gray-400 py-8 text-center">Carte indisponible.</p>;
  }
  if (!geometrie) {
    return <div className="h-64 rounded-lg bg-gray-50 animate-pulse" />;
  }

  const parId = new Map<number, Point>();
  for (const p of points) {
    if (p.id !== undefined) parId.set(p.id, p);
  }
  const valeurs = [...parId.values()].map(p => p.valeur);
  const min = Math.min(...valeurs);
  const max = Math.max(...valeurs);

  // Cinq classes de même largeur entre le minimum et le maximum affichés
  const classe = (valeur: number) =>
    max === min ? 2 : Math.min(RAMPE.length - 1, Math.floor(((valeur - min) / (max - min)) * RAMPE.length));

  const formeSelection = geometrie.formes.find(f => f.id === selection);
  const formeSurvol = geometrie.formes.find(f => f.id === survol && f.id !== selection);
  const pointSurvol = survol !== null ? parId.get(survol) : undefined;
  const sansDonnee = geometrie.formes.some(f => !parId.has(f.id));

  return (
    <div
      className="relative mx-auto max-w-2xl"
      onPointerMove={e => {
        const zone = e.currentTarget.getBoundingClientRect();
        setPointeur({ x: e.clientX - zone.left, y: e.clientY - zone.top });
      }}
    >
      <svg
        viewBox={`0 0 ${LARGEUR} ${geometrie.hauteur}`}
        className="w-full h-auto"
        role="group"
        aria-label="Carte des arrondissements de Paris"
      >
        {geometrie.formes.map(f => {
          const p = parId.get(f.id);
          const rang = p ? classe(p.valeur) : null;
          return (
            <g key={f.id}>
              <path
                d={f.chemin}
                fill={rang === null ? COULEUR_SANS_DONNEE : RAMPE[rang]}
                stroke={COULEURS.surface}
                strokeWidth={1.5}
                strokeLinejoin="round"
                role="button"
                tabIndex={0}
                aria-pressed={selection === f.id}
                aria-label={`${libelleArrondissement(f.id)} : ${p ? formater(p.valeur) : 'pas de donnée'}`}
                className="outline-none cursor-pointer"
                onClick={() => onSelect(f.id)}
                onKeyDown={e => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    onSelect(f.id);
                  }
                }}
                onPointerEnter={() => setSurvol(f.id)}
                onPointerLeave={() => setSurvol(null)}
                onFocus={() => setSurvol(f.id)}
                onBlur={() => setSurvol(null)}
              />
              <text
                x={f.centre[0]}
                y={f.centre[1]}
                textAnchor="middle"
                dominantBaseline="central"
                fontSize={12}
                fontWeight={600}
                fill={rang === null ? COULEURS.texteSecondaire : rang >= 2 ? '#ffffff' : ENCRE}
                pointerEvents="none"
              >
                {f.id}
              </text>
            </g>
          );
        })}

        {/* Contours par-dessus les voisins : la sélection ne doit pas être mangée par l'arrondissement d'à côté */}
        {formeSurvol && (
          <path d={formeSurvol.chemin} fill="none" stroke={COULEURS.texteSecondaire} strokeWidth={2} pointerEvents="none" />
        )}
        {formeSelection && (
          <path d={formeSelection.chemin} fill="none" stroke={ENCRE} strokeWidth={3} pointerEvents="none" />
        )}
      </svg>

      {survol !== null && pointeur && (
        <div
          className="pointer-events-none absolute z-10 rounded-md border bg-white px-3 py-2 shadow-sm text-xs"
          style={{ left: pointeur.x + 12, top: pointeur.y + 12 }}
        >
          <p className="text-gray-500 mb-1">Paris {libelleArrondissement(survol)}</p>
          {pointSurvol ? (
            <p className="flex items-center gap-2">
              <span className="font-semibold text-gray-900">{formater(pointSurvol.valeur)}</span>
              {pointSurvol.detail && <span className="text-gray-400">{pointSurvol.detail}</span>}
            </p>
          ) : (
            <p className="text-gray-400">Pas de donnée</p>
          )}
        </div>
      )}

      {valeurs.length > 0 && (
        <div className="mt-3 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-gray-600">
          <span>{formater(min)}</span>
          <span className="flex gap-0.5">
            {RAMPE.map(couleur => (
              <span
                key={couleur}
                className="inline-block w-8 h-3 rounded-sm"
                style={{ backgroundColor: couleur }}
              />
            ))}
          </span>
          <span>{formater(max)}</span>
          <span className="text-gray-400">· {legende}</span>
          {sansDonnee && (
            <span className="inline-flex items-center gap-1 ml-2">
              <span
                className="inline-block w-3 h-3 rounded-sm"
                style={{ backgroundColor: COULEUR_SANS_DONNEE }}
              />
              pas de donnée
            </span>
          )}
        </div>
      )}

      <p className="mt-2 text-[11px] text-gray-400">
        Contours : Ville de Paris (Paris Data), licence ODbL.
      </p>
    </div>
  );
}
