'use client';

import { useState } from 'react';
import { ExternalLink, MapPin, Briefcase, Clock, Euro, Building2, CheckCircle } from 'lucide-react';
import { JobOfferDetail, JobEnriched } from '@/types';
import { updateJobStatus, enrichJob } from '@/lib/api';
import RecalculButton from '@/components/jobs/RecalculButton';
import ReactMarkdown from 'react-markdown';

// ============================================================================
// Section helper
// ============================================================================

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold text-gray-900 dark:text-white border-b border-gray-100 dark:border-gray-700 pb-1">
        {title}
      </h3>
      {children}
    </div>
  );
}

// ============================================================================
// JobDetail
// ============================================================================

interface JobDetailProps {
  offer: JobOfferDetail;
  enriched: JobEnriched | null;
  onEnrichedUpdate: (enriched: JobEnriched) => void;
}

export default function JobDetail({ offer, enriched, onEnrichedUpdate }: JobDetailProps) {
  const [status, setStatus] = useState(offer.status);
  const [enriching, setEnriching] = useState(false);
  const [enrichError, setEnrichError] = useState<string | null>(null);

  // ============================================================================
  // Marquer comme postulé
  // ============================================================================

  const handlePostule = async () => {
    try {
      await updateJobStatus(offer.id, 'postule');
      setStatus('postule');
    } catch (e) {
      console.error(e);
    }
  };

  // ============================================================================
  // Enrichissement initial
  // ============================================================================

  const handleEnrich = async () => {
    setEnriching(true);
    setEnrichError(null);
    try {
      const result = await enrichJob(offer.id);
      onEnrichedUpdate(result);
    } catch (e) {
      setEnrichError(e instanceof Error ? e.message : 'Erreur enrichissement');
    } finally {
      setEnriching(false);
    }
  };

  return (
    <div className="space-y-8">

      {/* Header offre */}
      <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-6 space-y-4">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-xl font-bold text-gray-900 dark:text-white">{offer.title}</h1>
            {offer.company_name && (
              <p className="text-gray-500 dark:text-gray-400 mt-1 flex items-center gap-1.5">
                <Building2 className="w-4 h-4" />
                {offer.company_name}
                {offer.company_url && (
                  <a href={offer.company_url} target="_blank" rel="noopener noreferrer"
                    className="ml-1 text-blue-500 hover:text-blue-600">
                    <ExternalLink className="w-3.5 h-3.5" />
                  </a>
                )}
              </p>
            )}
          </div>

          {/* Bouton postuler */}
          {status !== 'postule' ? (
            <button
              onClick={handlePostule}
              className="shrink-0 inline-flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg text-sm font-medium transition-colors"
            >
              Marquer comme postulé
            </button>
          ) : (
            <span className="shrink-0 inline-flex items-center gap-2 px-4 py-2 bg-green-100 dark:bg-green-900 text-green-700 dark:text-green-300 rounded-lg text-sm font-medium">
              <CheckCircle className="w-4 h-4" />
              Postulé
              {offer.applied_at && (
                <span className="text-xs opacity-70 ml-1">
                  {new Date(offer.applied_at).toLocaleDateString('fr-FR')}
                </span>
              )}
            </span>
          )}
        </div>

        {/* Infos clés */}
        <div className="flex flex-wrap gap-x-5 gap-y-2 text-sm text-gray-600 dark:text-gray-400">
          {offer.location_label && (
            <span className="flex items-center gap-1.5"><MapPin className="w-4 h-4" />{offer.location_label}</span>
          )}
          {offer.contract_label && (
            <span className="flex items-center gap-1.5"><Briefcase className="w-4 h-4" />{offer.contract_label}</span>
          )}
          {offer.work_time && (
            <span className="flex items-center gap-1.5"><Clock className="w-4 h-4" />{offer.work_time}</span>
          )}
          {offer.salary_label && (
            <span className="flex items-center gap-1.5"><Euro className="w-4 h-4" />{offer.salary_label}</span>
          )}
        </div>

        {/* Lien offre originale */}
        {offer.offer_url && (
          <a
            href={offer.offer_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 text-sm text-blue-600 dark:text-blue-400 hover:underline"
          >
            <ExternalLink className="w-4 h-4" />
            Voir l'offre sur France Travail
          </a>
        )}
      </div>

      {/* Description brute */}
      {offer.description && (
        <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-6">
          <Section title="Description du poste">
            <p className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-line leading-relaxed">
              {offer.description}
            </p>
          </Section>
        </div>
      )}

      {/* Fiche enrichie */}
      <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-6 space-y-6">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold text-gray-900 dark:text-white">
            Fiche synthétique
          </h2>
          {enriched && (
            <span className="text-xs text-gray-400 dark:text-gray-500">
              Mis à jour le {new Date(enriched.updated_at).toLocaleDateString('fr-FR')}
            </span>
          )}
        </div>

        {/* Pas encore enrichi */}
        {!enriched && (
          <div className="text-center py-8 space-y-3">
            <p className="text-sm text-gray-500 dark:text-gray-400">
              La fiche synthétique n'a pas encore été générée.
            </p>
            {enrichError && (
              <p className="text-sm text-red-500 dark:text-red-400">{enrichError}</p>
            )}
            <button
              onClick={handleEnrich}
              disabled={enriching}
              className="inline-flex items-center gap-2 px-4 py-2 bg-gray-900 dark:bg-white text-white dark:text-gray-900 rounded-lg text-sm font-medium hover:bg-gray-800 dark:hover:bg-gray-100 transition-colors disabled:opacity-50"
            >
              {enriching ? 'Génération en cours...' : 'Générer la fiche'}
            </button>
          </div>
        )}

        {/* Fiche enrichie disponible */}
        {enriched && (
          <div className="space-y-6">

            {/* Résumé rédigé */}
            {enriched.summary && (
              <Section title="Synthèse">
                <div
                  className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed prose prose-sm dark:prose-invert max-w-none"
                  dangerouslySetInnerHTML={{ __html: enriched.summary.replace(/\n/g, '<br/>') }}
                />
                {/* <div className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed prose prose-sm dark:prose-invert max-w-none overflow-auto break-words">
                    <ReactMarkdown>
                    {enriched.summary}
                    </ReactMarkdown>
                </div> */}
              </Section>
            )}

            {/* Analyse compatibilité */}
            {enriched.analysis && (
              <Section title="Analyse compatibilité">
                <div className="space-y-3">
                  {(enriched.analysis.strengths as string[])?.length > 0 && (
                    <div>
                      <p className="text-xs font-medium text-green-600 dark:text-green-400 mb-1">Points forts</p>
                      <ul className="space-y-1">
                        {(enriched.analysis.strengths as string[]).map((s, i) => (
                          <li key={i} className="text-sm text-gray-700 dark:text-gray-300 flex items-start gap-2">
                            <span className="text-green-500 mt-0.5">✓</span>{s}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {(enriched.analysis.gaps as string[])?.length > 0 && (
                    <div>
                      <p className="text-xs font-medium text-orange-600 dark:text-orange-400 mb-1">Écarts</p>
                      <ul className="space-y-1">
                        {(enriched.analysis.gaps as string[]).map((g, i) => (
                          <li key={i} className="text-sm text-gray-700 dark:text-gray-300 flex items-start gap-2">
                            <span className="text-orange-500 mt-0.5">△</span>{g}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </Section>
            )}

            {/* Données parsées */}
            {enriched.parsed_data && (
              <Section title="Données extraites">
                <div className="grid grid-cols-2 gap-3 text-sm">
                  {enriched.parsed_data.salary_min != null && (
                    <div>
                        <span className="text-gray-500 dark:text-gray-400">Salaire min</span>
                        <p className="font-medium text-gray-900 dark:text-white">
                        {String(enriched.parsed_data.salary_min)} €
                        </p>
                    </div>
                    )}
                  {enriched.parsed_data.experience_years != null && (
                    <div>
                        <span className="text-gray-500 dark:text-gray-400">Expérience</span>
                        <p className="font-medium text-gray-900 dark:text-white">
                        {String(enriched.parsed_data.experience_years)} ans
                        </p>
                    </div>
                    )}
                  {Array.isArray(enriched.parsed_data.tech_stack) && enriched.parsed_data.tech_stack.length > 0 && (
                    <div className="col-span-2">
                        <span className="text-gray-500 dark:text-gray-400">Stack technique</span>
                        <div className="flex flex-wrap gap-1.5 mt-1">
                        {(enriched.parsed_data.tech_stack as string[]).map((t, i) => (
                            <span key={i} className="text-xs bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 px-2 py-0.5 rounded">
                            {t}
                            </span>
                        ))}
                        </div>
                    </div>
                    )}
                </div>
              </Section>
            )}

            {/* Recalcul */}
            <RecalculButton
              jobId={offer.id}
              recalculCount={enriched.recalcul_count}
              recalculRemaining={enriched.recalcul_remaining}
              onRecalcul={onEnrichedUpdate}
            />
          </div>
        )}
      </div>
    </div>
  );
}