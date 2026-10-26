'use client';

import dynamic from 'next/dynamic';
import { useRef, useState } from 'react';
import { GeorisquesReponse, Risque, getGeorisques } from '@/lib/immobilierBdnbApi';
import { CarteGraphique } from '../ImmobilierCharts';
import type { PointCarte } from './CarteClic';
import Lecture from './Lecture';

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
  const dernier = useRef(0);   // ignore la réponse d'un clic dépassé par un clic plus récent

  async function choisir(lat: number, lon: number) {
    const numero = ++dernier.current;
    setPoint({ lat, lon });
    setEnCours(true);
    setErreur(null);
    try {
      const r = await getGeorisques(lat, lon);
      if (numero === dernier.current) setReponse(r);
    } catch (e) {
      if (numero === dernier.current) {
        setReponse(null);
        setErreur(e instanceof Error ? e.message : 'Erreur inattendue');
      }
    } finally {
      if (numero === dernier.current) setEnCours(false);
    }
  }

  const trier = (famille: Risque['famille']) =>
    (reponse?.risques ?? [])
      .filter(r => r.famille === famille)
      .sort((a, b) => Number(identifie(b.statut_adresse)) - Number(identifie(a.statut_adresse)));

  return (
    <CarteGraphique
      titre="Risques"
      sousTitre="Cliquez sur la carte : risques naturels et technologiques recensés à ce point de Paris"
    >
      <Lecture
        voir="Les risques que Géorisques recense à l’endroit cliqué, avec leur statut à ce point et pour l’ensemble de la commune."
        retenir="« Risque non Connu » ou « non Concerne » à l’adresse signifie qu’aucun aléa n’est cartographié à ce point, pas qu’il n’existe pas."
        attention="Information générale, non contractuelle ; elle ne remplace pas l’état des risques réglementaire d’une vente ou d’une location."
      />

      <CarteClic point={point} onChoix={choisir} />

      <div className="mt-4" aria-live="polite">
        {!point && <p className="text-sm text-gray-500">Cliquez sur un point de la carte pour afficher ses risques.</p>}
        {enCours && <p className="text-sm text-gray-500 animate-pulse">Interrogation de Géorisques…</p>}
        {erreur && <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{erreur}</p>}

        {reponse && !enCours && (
          <>
            <p className="text-sm text-gray-700">
              Adresse la plus proche : <span className="font-medium text-gray-900">{reponse.adresse ?? 'non trouvée'}</span>
            </p>
            <Famille titre="Risques naturels" risques={trier('naturel')} />
            <Famille titre="Risques technologiques" risques={trier('technologique')} />
            {reponse.risques.length === 0 && <p className="text-sm text-gray-500 mt-3">Aucun risque recensé.</p>}
            <p className="mt-4 text-[11px] text-gray-400">
              Source : Géorisques (ministère de la Transition écologique, BRGM), API ouverte. Fond de carte © OpenStreetMap.
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
