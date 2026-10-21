'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { ChevronLeft, ChevronRight, RefreshCw } from 'lucide-react';
import {
  createTopDecision,
  deleteTopDecision,
  deleteTypeEntreprise,
  getTop,
  getTopStats,
  setTypeEntreprise,
} from '@/lib/api';
import { LISTES } from '@/lib/topOffres';
import { cn } from '@/lib/utils';
import {
  TopDecisionType,
  TopListe,
  TopOffre,
  TopOffreProche,
  TopResponse,
  TopTri,
  TypeEntrepriseCorrigeable,
} from '@/types';
import TopOffreCard from './TopOffreCard';
import DoublonDialog from './DoublonDialog';

// Paramètres
const PERIODES = [3, 7, 14, 30];
const JOURS_DEFAUT = 7;
const DELAI_MESSAGE_MS = 8000;
const JOURS_CIBLES = 30;   // période demandée à /stats, uniquement pour récupérer les intitulés des cibles

const TRIS: { id: TopTri; label: string }[] = [
  { id: 'pertinence', label: 'Pertinence' },
  { id: 'recent', label: 'Plus récentes' },
];

interface Message {
  texte: string;
  erreur?: boolean;
  lien?: { href: string; label: string };
  annulerId?: string;   // id_unique d'une décision « pas intéressé » ou « expirée » annulable
}

interface DoublonsEnAttente {
  offre: TopOffre;
  doublons: TopOffreProche[];
}

export default function TopDuJourView() {
  const [jours, setJours] = useState(JOURS_DEFAUT);
  const [inclureExclues, setInclureExclues] = useState(false);
  const [onglet, setOnglet] = useState<TopListe>('a_lire');
  const [page, setPage] = useState(1);
  const [tri, setTri] = useState<TopTri>('pertinence');
  const [cible, setCible] = useState('');   // '' : tous les métiers
  const [cibles, setCibles] = useState<Record<string, string>>({});
  const [data, setData] = useState<TopResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [doublons, setDoublons] = useState<DoublonsEnAttente | null>(null);
  const [message, setMessage] = useState<Message | null>(null);

  // Rechargement silencieux : pas de squelette (après une décision, une correction de type)
  const load = useCallback(async (silencieux = false) => {
    if (!silencieux) setLoading(true);
    setError(null);
    try {
      // Le serveur ramène à la dernière page si la demande la dépasse : l'affichage suit `data.page`
      setData(await getTop({ jours, inclureExclues, liste: onglet, page, tri, cible: cible || undefined }));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erreur de chargement');
    } finally {
      setLoading(false);
    }
  }, [jours, inclureExclues, onglet, page, tri, cible]);


  useEffect(() => {
    load();
  }, [load]);

  // Intitulés des cibles pour le sélecteur ; une erreur laisse simplement le sélecteur vide
  useEffect(() => {
    getTopStats(JOURS_CIBLES).then(r => setCibles(r.cibles)).catch(() => {});
  }, []);

  // Le message disparaît seul
  useEffect(() => {
    if (!message) return;
    const timer = setTimeout(() => setMessage(null), DELAI_MESSAGE_MS);
    return () => clearTimeout(timer);
  }, [message]);

  const decider = async (
    offre: TopOffre,
    decision: TopDecisionType,
    options: { confirmer?: boolean; utiliserJobOfferId?: number } = {},
  ) => {
    setBusyId(offre.id_unique);
    try {
      const res = await createTopDecision({
        id_unique: offre.id_unique,
        decision,
        confirmer: options.confirmer,
        utiliser_job_offer_id: options.utiliserJobOfferId,
      });

      // Doublon : rien n'est créé, l'utilisateur choisit
      if (res.resultat === 'doublon_detecte') {
        setDoublons({ offre, doublons: res.doublons });
        return;
      }

      setDoublons(null);
      if (decision === 'pas_interesse' || decision === 'expire') {
        setMessage({
          texte: decision === 'expire' ? 'Offre marquée expirée.' : 'Offre écartée.',
          annulerId: offre.id_unique,
        });
      } else {
        setMessage({
          texte: options.utiliserJobOfferId
            ? 'Offre rattachée à une offre existante.'
            : 'Brouillon créé.',
          lien: res.job_offer_id
            ? { href: `/jobs/${res.job_offer_id}`, label: 'Ouvrir dans /jobs' }
            : undefined,
        });
      }
      await load(true);
    } catch (e) {
      setDoublons(null);
      setMessage({ texte: e instanceof Error ? e.message : 'Erreur', erreur: true });
    } finally {
      setBusyId(null);
    }
  };

  const annuler = async (idUnique: string) => {
    setMessage(null);
    try {
      await deleteTopDecision(idUnique);
      setMessage({ texte: "Décision annulée : l'offre revient dans la liste." });
      await load(true);
    } catch (e) {
      setMessage({ texte: e instanceof Error ? e.message : 'Erreur', erreur: true });
    }
  };

  const changerType = async (offre: TopOffre, type: TypeEntrepriseCorrigeable | null) => {
    if (!offre.entreprise_normalise) return;
    setBusyId(offre.id_unique);
    try {
      if (type === null) {
        await deleteTypeEntreprise(offre.entreprise_normalise);
      } else {
        await setTypeEntreprise(offre.entreprise_normalise, { type_entreprise: type });
      }
      await load(true);
    } catch (e) {
      setMessage({ texte: e instanceof Error ? e.message : 'Erreur', erreur: true });
    } finally {
      setBusyId(null);
    }
  };

  const offres = data && data.liste === onglet ? data.offres : [];
  const total = data && data.liste === onglet ? data.total : 0;
  const annulerId = message?.annulerId;

  // Barre de pagination : affichée en haut (barre fixe) et en bas de la liste
  const pagination = data && data.liste === onglet && data.nb_pages > 1 ? (
    <div className="flex items-center justify-center gap-4 text-sm text-gray-600">
      <button
        onClick={() => setPage(data.page - 1)}
        disabled={loading || data.page <= 1}
        className="inline-flex items-center gap-1 px-3 py-1.5 border rounded-lg bg-white hover:bg-gray-50 transition-colors disabled:opacity-50"
      >
        <ChevronLeft className="w-4 h-4" />
        Précédent
      </button>
      <span>Page {data.page} / {data.nb_pages}</span>
      <button
        onClick={() => setPage(data.page + 1)}
        disabled={loading || data.page >= data.nb_pages}
        className="inline-flex items-center gap-1 px-3 py-1.5 border rounded-lg bg-white hover:bg-gray-50 transition-colors disabled:opacity-50"
      >
        Suivant
        <ChevronRight className="w-4 h-4" />
      </button>
    </div>
  ) : null;

  return (
    <div className="space-y-4">

      {/* Onglets, réglages et pagination : fixes sous l'en-tête du site (écran large) */}
      <div className="flex flex-wrap items-center justify-between gap-3 md:sticky md:top-16 z-40 bg-gray-50 py-2">
        <div role="tablist" className="inline-flex rounded-lg border bg-white p-1">
          {LISTES.map(({ id, label }) => (
            <button
              key={id}
              role="tab"
              aria-selected={onglet === id}
              onClick={() => { setOnglet(id); setPage(1); }}
              className={cn(
                'px-4 py-1.5 text-sm font-medium rounded-md transition-colors',
                onglet === id ? 'bg-blue-50 text-blue-700' : 'text-gray-600 hover:bg-gray-50',
              )}
            >
              {label}
              {data ? ` (${data.compteurs[id]})` : ''}
            </button>
          ))}
        </div>

        <div className="flex flex-wrap items-center gap-4 text-sm text-gray-600">
          <label className="inline-flex items-center gap-2">
            Période
            <select
              value={jours}
              onChange={e => { setJours(Number(e.target.value)); setPage(1); }}
              className="text-sm border border-gray-200 rounded px-2 py-1 bg-white text-gray-700"
            >
              {PERIODES.map(j => (
                <option key={j} value={j}>{j} jours</option>
              ))}
            </select>
          </label>
          <label className="inline-flex items-center gap-2">
            Tri
            <select
              value={tri}
              onChange={e => { setTri(e.target.value as TopTri); setPage(1); }}
              className="text-sm border border-gray-200 rounded px-2 py-1 bg-white text-gray-700"
            >
              {TRIS.map(({ id, label }) => (
                <option key={id} value={id}>{label}</option>
              ))}
            </select>
          </label>
          <label className="inline-flex items-center gap-2">
            Métier cible
            <select
              value={cible}
              onChange={e => { setCible(e.target.value); setPage(1); }}
              className="text-sm border border-gray-200 rounded px-2 py-1 bg-white text-gray-700"
            >
              <option value="">Tous</option>
              {Object.entries(cibles).map(([id, intitule]) => (
                <option key={id} value={id}>{intitule}</option>
              ))}
            </select>
          </label>
          <label className="inline-flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={inclureExclues}
              onChange={e => { setInclureExclues(e.target.checked); setPage(1); }}
              className="w-4 h-4 rounded border-gray-300"
            />
            Inclure les entreprises exclues
          </label>
          <button
            onClick={() => load()}
            disabled={loading}
            title="Rafraîchir"
            className="p-1.5 text-gray-500 hover:text-gray-700 transition-colors"
          >
            <RefreshCw className={cn('w-4 h-4', loading && 'animate-spin')} />
          </button>
        </div>

        {data && offres.length > 0 && (
          <div className="basis-full flex flex-wrap items-center justify-between gap-3">
            <p className="text-xs text-gray-500">
              Offres {(data.page - 1) * data.taille + 1} à {(data.page - 1) * data.taille + offres.length} sur {total}.
            </p>
            {pagination}
          </div>
        )}
      </div>

      {/* Message de résultat d'une action */}
      {message && (
        <div
          role="status"
          className={cn(
            'flex flex-wrap items-center gap-3 text-sm px-4 py-3 rounded-lg',
            message.erreur ? 'bg-red-50 text-red-700' : 'bg-green-50 text-green-700',
          )}
        >
          <span>{message.texte}</span>
          {message.lien && (
            <Link href={message.lien.href} className="font-medium underline">
              {message.lien.label}
            </Link>
          )}
          {annulerId && (
            <button onClick={() => annuler(annulerId)} className="font-medium underline">
              Annuler
            </button>
          )}
        </div>
      )}

      {error && (
        <div className="text-sm text-red-600 bg-red-50 px-4 py-3 rounded-lg">{error}</div>
      )}

      {loading && (
        <div className="space-y-4">
          {[1, 2, 3].map(i => (
            <div key={i} className="h-32 border rounded-lg bg-white animate-pulse" />
          ))}
        </div>
      )}

      {!loading && !error && offres.length === 0 && (
        <p className="text-center text-sm text-gray-500 py-12">
          Aucune offre dans cette liste sur la période choisie.
        </p>
      )}

      {!loading && data && offres.length > 0 && (
        <>
          <div className="space-y-4">
            {offres.map(offre => (
              <TopOffreCard
                key={offre.id_unique}
                offre={offre}
                busy={busyId === offre.id_unique}
                onDecision={(o, decision) => decider(o, decision)}
                onTypeChange={changerType}
              />
            ))}
          </div>
          {pagination && <div className="pt-2">{pagination}</div>}
        </>
      )}

      {/* Doublon détecté : choix de l'utilisateur */}
      {doublons && (
        <DoublonDialog
          offre={doublons.offre}
          doublons={doublons.doublons}
          busy={busyId === doublons.offre.id_unique}
          onCreerQuandMeme={() => decider(doublons.offre, 'interesse', { confirmer: true })}
          onUtiliser={jobOfferId =>
            decider(doublons.offre, 'interesse', { utiliserJobOfferId: jobOfferId })
          }
          onAnnuler={() => setDoublons(null)}
        />
      )}
    </div>
  );
}
