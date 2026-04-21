"use client";

import { FilterOptions } from "@/types/index";

interface ExploreFiltersProps {
  filters: FilterOptions;
  values: {
    titre: string;
    source: string;
    type_contrat: string;
    localisation_libelle: string;
    periode_jours: string;
    entreprise_nom: string;
  };
  onChange: (key: string, value: string) => void;
  onReset: () => void;
}

const PERIODE_OPTIONS = [
  { label: "Toutes périodes", value: "" },
  { label: "7 derniers jours", value: "7" },
  { label: "30 derniers jours", value: "30" },
  { label: "90 derniers jours", value: "90" },
];

const SOURCE_LABELS: Record<string, string> = {
  france_travail_api:   "France Travail",
  gmail_linkedin:       "LinkedIn",
  gmail_apec:           "APEC",
  gmail_hellowork:      "Hellowork",
  gmail_talent:         "Talent",
  gmail_jobijoba:       "Jobijoba",
  gmail_freework:       "Free-Work",
  gmail_wttj:           "WTTJ",
  gmail_indeed:         "Indeed",
  gmail_france_travail: "France Travail (email)",
};

export default function ExploreFilters({
  filters,
  values,
  onChange,
  onReset,
}: ExploreFiltersProps) {
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4 space-y-3">
      {/* Titre */}
      <div>
        <label className="block text-xs font-medium text-gray-600 mb-1">
          Titre
        </label>
        <input
          type="text"
          value={values.titre}
          onChange={e => onChange("titre", e.target.value)}
          placeholder="Rechercher un titre..."
          className="w-full border border-gray-200 rounded px-3 py-1.5 text-sm focus:outline-none focus:border-gray-400"
        />
      </div>

      {/* Source */}
      <div>
        <label className="block text-xs font-medium text-gray-600 mb-1">
          Source
        </label>
        <select
          value={values.source}
          onChange={e => onChange("source", e.target.value)}
          className="w-full border border-gray-200 rounded px-3 py-1.5 text-sm focus:outline-none focus:border-gray-400"
        >
          <option value="">Toutes les sources</option>
          {filters.sources.map(s => (
            <option key={s} value={s}>
              {SOURCE_LABELS[s] ?? s}
            </option>
          ))}
        </select>
      </div>

      {/* Type de contrat */}
      <div>
        <label className="block text-xs font-medium text-gray-600 mb-1">
          Type de contrat
        </label>
        <select
          value={values.type_contrat}
          onChange={e => onChange("type_contrat", e.target.value)}
          className="w-full border border-gray-200 rounded px-3 py-1.5 text-sm focus:outline-none focus:border-gray-400"
        >
          <option value="">Tous les contrats</option>
          {filters.types_contrat.map(t => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
      </div>

      {/* Entreprise */}
      <div>
        <label className="block text-xs font-medium text-gray-600 mb-1">
          Entreprise
        </label>
        <select
          value={values.entreprise_nom}
          onChange={e => onChange("entreprise_nom", e.target.value)}
          className="w-full border border-gray-200 rounded px-3 py-1.5 text-sm focus:outline-none focus:border-gray-400"
        >
          <option value="">Toutes les entreprises</option>
          
          {filters.entreprise_nom.map(r => (
            <option key={r} value={r}>{r}</option>
          ))}
        </select>
      </div>


      {/* Région */}
      <div>
        <label className="block text-xs font-medium text-gray-600 mb-1">
          Région
        </label>
        <select
          value={values.localisation_libelle}
          onChange={e => onChange("localisation_libelle", e.target.value)}
          className="w-full border border-gray-200 rounded px-3 py-1.5 text-sm focus:outline-none focus:border-gray-400"
        >
          <option value="">Toutes les régions</option>
          {filters.regions.map(r => (
            <option key={r} value={r}>{r}</option>
          ))}
        </select>
      </div>

      {/* Période */}
      <div>
        <label className="block text-xs font-medium text-gray-600 mb-1">
          Période
        </label>
        <select
          value={values.periode_jours}
          onChange={e => onChange("periode_jours", e.target.value)}
          className="w-full border border-gray-200 rounded px-3 py-1.5 text-sm focus:outline-none focus:border-gray-400"
        >
          {PERIODE_OPTIONS.map(o => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
      </div>

      {/* Reset */}
      <button
        onClick={onReset}
        className="w-full text-xs text-gray-500 hover:text-gray-700 underline pt-1"
      >
        Réinitialiser les filtres
      </button>
    </div>
  );
}