'use client';

import Link from 'next/link';
import { Badge } from '@/components/ui/badge';
import { TopOffre, TopOffreProche } from '@/types';

const CRITERES: Record<TopOffreProche['critere'], string> = {
  ft_id: 'Même identifiant France Travail',
  titre_entreprise: 'Même titre et même entreprise',
};

interface DoublonDialogProps {
  offre: TopOffre;
  doublons: TopOffreProche[];
  busy: boolean;
  onCreerQuandMeme: () => void;
  onUtiliser: (jobOfferId: number) => void;
  onAnnuler: () => void;
}

// Un doublon n'est jamais bloquant : l'utilisateur choisit de garder une offre existante ou de créer quand même.
export default function DoublonDialog({
  offre,
  doublons,
  busy,
  onCreerQuandMeme,
  onUtiliser,
  onAnnuler,
}: DoublonDialogProps) {
  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
      onClick={busy ? undefined : onAnnuler}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="doublon-titre"
        className="bg-white rounded-lg w-full max-w-lg shadow-xl flex flex-col max-h-[90vh]"
        onClick={e => e.stopPropagation()}
      >
        <div className="p-6 pb-3 shrink-0">
          <h2 id="doublon-titre" className="text-base font-semibold text-gray-900">
            Une offre proche existe déjà
          </h2>
          <p className="text-sm text-gray-600 mt-1">
            « {offre.titre} » ressemble à {doublons.length > 1 ? 'des offres' : 'une offre'} déjà présente
            dans vos offres. Gardez l&apos;existante ou créez un nouveau brouillon.
          </p>
        </div>

        <ul className="px-6 space-y-2 overflow-y-auto">
          {doublons.map(d => (
            <li key={d.job_offer_id} className="border rounded-lg p-3 flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-sm font-medium text-gray-900 break-words">{d.title}</p>
                <p className="text-xs text-gray-500">{d.company_name ?? 'Entreprise non renseignée'}</p>
                <div className="flex flex-wrap items-center gap-2 mt-1.5">
                  <Badge variant="outline" className="text-xs">{d.status}</Badge>
                  <span className="text-xs text-gray-500">{CRITERES[d.critere]}</span>
                  <Link
                    href={`/jobs/${d.job_offer_id}`}
                    target="_blank"
                    className="text-xs text-blue-600 hover:underline"
                  >
                    Voir
                  </Link>
                </div>
              </div>
              <button
                onClick={() => onUtiliser(d.job_offer_id)}
                disabled={busy}
                className="shrink-0 px-3 py-1.5 text-sm border rounded-lg text-gray-700 hover:bg-gray-50 transition-colors disabled:opacity-50"
              >
                Utiliser celle-ci
              </button>
            </li>
          ))}
        </ul>

        <div className="p-6 pt-4 flex justify-end gap-2 shrink-0">
          <button
            onClick={onAnnuler}
            disabled={busy}
            className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900 disabled:opacity-50"
          >
            Annuler
          </button>
          <button
            onClick={onCreerQuandMeme}
            disabled={busy}
            className="px-4 py-2 text-sm rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-medium transition-colors disabled:opacity-50"
          >
            Créer quand même
          </button>
        </div>
      </div>
    </div>
  );
}
