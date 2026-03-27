 
'use client';

import { useState } from 'react';
import { createExternalJob } from '@/lib/api';
import { ExternalJobOfferCreate, JobOfferDetail } from '@/types';

interface ExternalJobFormProps {
  onSuccess: (job: JobOfferDetail, triggerEnrichment: boolean) => void;
  onCancel: () => void;
}

const EMPTY_FORM: ExternalJobOfferCreate = {
  title: '',
  description: '',
  company_name: '',
  company_description: '',
  location_label: '',
  source_offer: '',
  offer_url: '',
  contract_type: '',
  experience_label: '',
  work_time: '',
  salary_label: '',
  sector_label: '',
  trigger_enrichment: false,
  published_at: '',
};

export default function ExternalJobForm({ onSuccess, onCancel }: ExternalJobFormProps) {
  const [form, setForm] = useState<ExternalJobOfferCreate>(EMPTY_FORM);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const set = (field: keyof ExternalJobOfferCreate, value: string | boolean) =>
    setForm(f => ({ ...f, [field]: value }));

  const isValid =
    form.title.trim().length >= 2 &&
    form.description.trim().length >= 10 &&
    form.company_name.trim().length >= 2 &&
    form.company_description.trim().length >= 10 &&
    form.location_label.trim().length >= 2 && 
    form.published_at.trim().length > 0;

  const handleSubmit = async () => {
    if (!isValid) return;
    setLoading(true);
    setError(null);
    try {
      const job = await createExternalJob(form);
      console.log('trigger_enrichment au submit:', form.trigger_enrichment);
      console.log('job reçu:', job);
      onSuccess(job, form.trigger_enrichment);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erreur lors de l\'ajout');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">

      {/* Champs obligatoires */}
      <div className="space-y-3">
        <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">
          Informations obligatoires
        </p>

        <Field label="Intitulé du poste *">
          <input
            type="text"
            value={form.title}
            onChange={e => set('title', e.target.value)}
            placeholder="ex: Data Scientist Senior"
            className={inputCls}
          />
        </Field>

        <Field label="Entreprise *">
          <input
            type="text"
            value={form.company_name}
            onChange={e => set('company_name', e.target.value)}
            placeholder="ex: Société Générale"
            className={inputCls}
          />
        </Field>

        <Field label="Présentation de l'entreprise *">
          <textarea
            value={form.company_description}
            onChange={e => set('company_description', e.target.value)}
            placeholder="Décrivez l'entreprise..."
            rows={20}
            className={inputCls}
          />
        </Field>

        <Field label="Localisation *">
          <input
            type="text"
            value={form.location_label}
            onChange={e => set('location_label', e.target.value)}
            placeholder="ex: Paris 75001"
            className={inputCls}
          />
        </Field>

        <Field label="Date de publication *">
            <input
                type="date"
                value={form.published_at}
                onChange={e => set('published_at', e.target.value)}
                className={inputCls}
            />
        </Field>

        <Field label="Description du poste *">
          <textarea
            value={form.description}
            onChange={e => set('description', e.target.value)}
            placeholder="Collez ici la description complète de l'offre..."
            rows={30}
            className={inputCls}
          />
        </Field>
      </div>

      {/* Champs optionnels */}
      <div className="space-y-3 pt-2 border-t border-gray-200 dark:border-gray-700">
        <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">
          Informations optionnelles
        </p>

        <div className="grid grid-cols-2 gap-3">
          <Field label="Source">
            <input
              type="text"
              value={form.source_offer}
              onChange={e => set('source_offer', e.target.value)}
              placeholder="ex: LinkedIn"
              className={inputCls}
            />
          </Field>

          <Field label="Type de contrat">
            <input
              type="text"
              value={form.contract_type}
              onChange={e => set('contract_type', e.target.value)}
              placeholder="ex: CDI"
              className={inputCls}
            />
          </Field>

          <Field label="Expérience requise">
            <input
              type="text"
              value={form.experience_label}
              onChange={e => set('experience_label', e.target.value)}
              placeholder="ex: 3-5 ans"
              className={inputCls}
            />
          </Field>

          <Field label="Temps de travail">
            <input
              type="text"
              value={form.work_time}
              onChange={e => set('work_time', e.target.value)}
              placeholder="ex: Temps plein"
              className={inputCls}
            />
          </Field>

          <Field label="Salaire">
            <input
              type="text"
              value={form.salary_label}
              onChange={e => set('salary_label', e.target.value)}
              placeholder="ex: 45-55k€"
              className={inputCls}
            />
          </Field>

          <Field label="Secteur">
            <input
              type="text"
              value={form.sector_label}
              onChange={e => set('sector_label', e.target.value)}
              placeholder="ex: Finance"
              className={inputCls}
            />
          </Field>
        </div>

        <Field label="URL de l'offre">
          <input
            type="url"
            value={form.offer_url}
            onChange={e => set('offer_url', e.target.value)}
            placeholder="https://..."
            className={inputCls}
          />
        </Field>
      </div>

      {/* Checkbox enrichissement */}
      {/* <div className="flex items-center gap-3 pt-2 border-t border-gray-200 dark:border-gray-700">
        <input
          type="checkbox"
          id="trigger_enrichment"
          checked={form.trigger_enrichment}
          onChange={e => set('trigger_enrichment', e.target.checked)}
          className="w-4 h-4 rounded border-gray-300 text-blue-600"
        />
        <label htmlFor="trigger_enrichment" className="text-sm text-gray-700 dark:text-gray-300">
          Lancer l'enrichissement après ajout
        </label>
      </div> */}

      {error && (
        <p className="text-sm text-red-500">{error}</p>
      )}

      <div className="flex justify-end gap-2 pt-2">
        <button
          onClick={onCancel}
          className="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white"
        >
          Annuler
        </button>
        <button
          onClick={handleSubmit}
          disabled={loading || !isValid}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium disabled:opacity-50"
        >
          {loading ? 'Ajout en cours...' : 'Ajouter l\'offre'}
        </button>
      </div>
    </div>
  );
}

// ============================================================================
// Helpers UI
// ============================================================================

const inputCls = "w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-white";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <label className="text-xs text-gray-500 dark:text-gray-400">{label}</label>
      {children}
    </div>
  );
}