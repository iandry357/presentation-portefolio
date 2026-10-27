'use client';

import dynamic from 'next/dynamic';
import { useRef, useState } from 'react';
import { GeorisquesReponse, PointReponse, Risque, getGeorisques, getPoint } from '@/lib/immobilierBdnbApi';
import { CarteGraphique } from '../ImmobilierCharts';
import type { PointCarte } from './CarteClic';
import Lecture from './Lecture';
import PanneauPoint from './PanneauPoint';

// Leaflet touche à `window` : la carte n'est rendue que côté navigateur
const CarteClic = dynamic(() => import('./CarteClic'), {
  ssr: false,
  loading: () => <div className="h-80 rounded-lg bg-gray-50 animate-pulse" />,
});

// « Risque non Connu » / « Risque non Concerne » : rien d'identifié à ce point
function identifie(statut: string | null): boolean {
  return !!statut && !/\bnon\b/i.test(statut);
}

function CarteRisque({ risque }: { risque: Risque }) {
  const actif = identifie(risque.statut_adresse);
  return (
    <li className={actif ? 'border border-amber-300 bg-amber-50 rounded-lg p-3' : 'border bg-gray-50 rounded-lg p-3'}>
      <p className="text-sm font-semibold text-gray-900">{risque.libelle}</p>
      <p className="text-xs text-gray-700 mt-1">À ce point : {risque.statut_adresse ?? 'non renseigné'}</p>
      <p className="text-xs text-gray-500">Commune : {risque.statut_commune ?? 'non renseigné'}</p>
    </li>
  );
}

function Famille({ titre, risques }: { titre: string; risques: Risque[] }) {
  if (risques.length === 0) return null;
  return (
    <div className="mt-4">
      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">{titre}</p>
      <ul className="grid gap-2 sm:grid-cols-2">
        {risques.map(r => (
          <CarteRisque key={r.libelle} risque={r} />
        ))}
      </ul>
    </div>
  );
}

export default function RisquesView() {
  const [point, setPoint] = useState<PointCarte | null>(null);
  const [reponse, setReponse] = useState<GeorisquesReponse | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [enCours, setEnCours] = useState(false);
  const [infoPoint, setInfoPoint] = useState<PointReponse | null>(null);
  const [erreurPoint, setErreurPoint] = useState<string | null>(null);
  const [enCoursPoint, setEnCoursPoint] = useState(false);
  const dernier = useRef(0);   // ignore la réponse d'un clic dépassé par un clic plus récent

  // Géorisques et la Géoplateforme sont interrogés en parallèle : une panne de l'un ne bloque pas l'autre
  function choisir(lat: number, lon: number) {
    const numero = ++dernier.current;
    const courant = () => numero === dernier.current;
    setPoint({ lat, lon });
    setEnCours(true);
    setErreur(null);
    setEnCoursPoint(true);
    setErreurPoint(null);

    getGeorisques(lat, lon)
      .then(r => { if (courant()) setReponse(r); })
      .catch(e => {
        if (!courant()) return;
        setReponse(null);
        setErreur(e instanceof Error ? e.message : 'Erreur inattendue');
      })
      .finally(() => { if (courant()) setEnCours(false); });

    getPoint(lat, lon)
      .then(r => { if (courant()) setInfoPoint(r); })
      .catch(e => {
        if (!courant()) return;
        setInfoPoint(null);
        setErreurPoint(e instanceof Error ? e.message : 'Erreur inattendue');
      })
      .finally(() => { if (courant()) setEnCoursPoint(false); });
  }

  const trier = (famille: Risque['famille']) =>
    (reponse?.risques ?? [])
      .filter(r => r.famille === famille)
      .sort((a, b) => Number(identifie(b.statut_adresse)) - Number(identifie(a.statut_adresse)));

  return (
    <CarteGraphique
      titre="Carte"
      sousTitre="Cliquez sur la carte : adresse, parcelle et risques recensés à ce point de Paris"
    >
      <Lecture
        voir="L’adresse la plus proche, la parcelle cadastrale et la zone d’urbanisme du point cliqué, puis les risques que Géorisques recense à cet endroit, avec leur statut à ce point et pour l’ensemble de la commune."
        retenir="« Risque non Connu » ou « non Concerne » à l’adresse signifie qu’aucun aléa n’est cartographié à ce point, pas qu’il n’existe pas."
        attention="La zone d’urbanisme est donnée à titre indicatif : le règlement du plan local d’urbanisme fait foi. Information générale, non contractuelle ; elle ne remplace pas l’état des risques réglementaire d’une vente ou d’une location."
      />

      <CarteClic point={point} onChoix={choisir} />

      <PanneauPoint point={point} donnees={infoPoint} enCours={enCoursPoint} erreur={erreurPoint} />

      <div className="mt-4" aria-live="polite">
        {!point && <p className="text-sm text-gray-500">Cliquez sur un point de la carte pour afficher son adresse, sa parcelle et ses risques.</p>}
        {enCours && <p className="text-sm text-gray-500 animate-pulse">Interrogation de Géorisques…</p>}
        {erreur && <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{erreur}</p>}

        {reponse && !enCours && (
          <>
            <p className="text-sm text-gray-700">
              Adresse retenue par Géorisques : <span className="font-medium text-gray-900">{reponse.adresse ?? 'non trouvée'}</span>
            </p>
            <Famille titre="Risques naturels" risques={trier('naturel')} />
            <Famille titre="Risques technologiques" risques={trier('technologique')} />
            {reponse.risques.length === 0 && <p className="text-sm text-gray-500 mt-3">Aucun risque recensé.</p>}
            <p className="mt-4 text-[11px] text-gray-400">
              Source : Géorisques (ministère de la Transition écologique, BRGM), API ouverte. Adresse, parcelle, urbanisme, fond de carte et cadastre : IGN (Géoplateforme, API Carto).
              {reponse.url_rapport && (
                <>
                  {' '}
                  <a href={reponse.url_rapport} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
                    Rapport complet
                  </a>
                </>
              )}
            </p>
          </>
        )}
      </div>
    </CarteGraphique>
  );
}
