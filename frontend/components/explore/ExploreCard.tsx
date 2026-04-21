"use client";

import { ExploreOffer } from "@/types/index";

interface ExploreCardProps {
  offer: ExploreOffer;
}

const SOURCE_LABELS: Record<string, string> = {
  france_travail_api: "France Travail",
  gmail_linkedin:     "LinkedIn",
  gmail_apec:         "APEC",
  gmail_hellowork:    "Hellowork",
  gmail_talent:       "Talent",
  gmail_jobijoba:     "Jobijoba",
  gmail_freework:     "Free-Work",
  gmail_wttj:         "WTTJ",
  gmail_indeed:       "Indeed",
  gmail_france_travail: "France Travail (email)",
};

export default function ExploreCard({ offer }: ExploreCardProps) {
  return (
    <div className="border border-gray-200 rounded-lg p-4 hover:border-gray-400 transition-colors bg-white">
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          {/* Titre */}
          <h3 className="font-semibold text-gray-900 text-sm leading-snug line-clamp-2">
            {offer.url_offre ? (
              <a
                href={offer.url_offre}
                target="_blank"
                rel="noopener noreferrer"
                className="hover:underline"
              >
                {offer.titre}
              </a>
            ) : (
              offer.titre
            )}
          </h3>

          {/* Entreprise + Localisation */}
          <div className="mt-1 text-xs text-gray-500 flex flex-wrap gap-x-2 gap-y-0.5">
            {offer.entreprise_nom && (
              <span className="font-medium text-gray-700">{offer.entreprise_nom}</span>
            )}
            {offer.localisation_libelle && (
              <span>{offer.localisation_libelle}</span>
            )}
          </div>

          {/* Tags */}
          <div className="mt-2 flex flex-wrap gap-1.5">
            {offer.type_contrat_libelle && (
              <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">
                {offer.type_contrat_libelle}
              </span>
            )}
            {offer.salaire_libelle && (
              <span className="text-xs bg-green-50 text-green-700 px-2 py-0.5 rounded">
                {offer.salaire_libelle}
              </span>
            )}
            {offer.experience_libelle && (
              <span className="text-xs bg-blue-50 text-blue-700 px-2 py-0.5 rounded">
                {offer.experience_libelle}
              </span>
            )}
          </div>
        </div>

        {/* Source + Date */}
        <div className="flex flex-col items-end gap-1 shrink-0">
          <span className="text-xs bg-gray-50 border border-gray-200 text-gray-500 px-2 py-0.5 rounded">
            {SOURCE_LABELS[offer.source] ?? offer.source}
          </span>
          {offer.date_publication && (
            <span className="text-xs text-gray-400">
              {offer.date_publication}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}