'use client';

import { useState, useRef } from 'react';
import { ExternalLink, MapPin, Briefcase, Clock, Euro, Building2, CheckCircle, FileText, Sparkles, NotebookPen, Factory } from 'lucide-react';
import { JobOfferDetail, JobEnriched } from '@/types';
import RecalculButton from '@/components/jobs/RecalculButton';
import CollapsibleSection from '@/components/jobs/CollapsibleSection';
import JobNotes from '@/components/jobs/JobNotes';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { updateJobStatus, enrichJob, FT_BASE_URL } from '@/lib/api';
// import CompanySection from '@/components/jobs/CompanyDetail';
import CompanySection from '@/components/jobs/CompanySection';

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

function AnimatedDots() {
  return (
    <span className="inline-flex gap-0.5">
      <span className="animate-bounce [animation-delay:0ms]">.</span>
      <span className="animate-bounce [animation-delay:150ms]">.</span>
      <span className="animate-bounce [animation-delay:300ms]">.</span>
    </span>
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
  const [enregistre, setEnregistre] = useState(offer.status === 'enregistre');
  const [notes, setNotes] = useState<string | null>(offer.notes);
  const [companyOpen, setCompanyOpen] = useState(false);
  const companyRef = useRef<HTMLDivElement>(null);
  const [companyProfileId, setCompanyProfileId] = useState<number | null>(
    offer.company_profile_id
  );

  // États des accordéons
  const [ficheOpen, setFicheOpen] = useState(false);
  const [descOpen, setDescOpen] = useState(false);
  const [notesOpen, setNotesOpen] = useState(false);

  // Refs pour le scroll
  const ficheRef = useRef<HTMLDivElement>(null);
  const descRef = useRef<HTMLDivElement>(null);
  const notesRef = useRef<HTMLDivElement>(null);

  // const scrollTo = (ref: React.RefObject<HTMLDivElement>, open: () => void) => {
  const scrollTo = (ref: React.RefObject<HTMLDivElement | null>, open: () => void) => {
    open();
    setTimeout(() => {
      ref.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 50);
  };

  const handlePostule = async () => {
    try {
      await updateJobStatus(offer.id, 'postule');
      setStatus('postule');
    } catch (e) {
      console.error(e);
    }
  };

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

  const handleEnregistre = async () => {
    try {
      await updateJobStatus(offer.id, 'enregistre');
      setEnregistre(true);
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="space-y-4">

      {/* ── Header offre ─────────────────────────────────────────────────── */}
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

          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2">
            {status !== 'postule' ? (
              <button
                onClick={handlePostule}
                className="shrink-0 inline-flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg text-sm font-medium transition-colors"
              >
                Postuler
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

            {!enregistre ? (
              <button
                onClick={handleEnregistre}
                className="shrink-0 inline-flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors"
              >
                Enregistrer
              </button>
            ) : (
              <span className="shrink-0 inline-flex items-center gap-2 px-4 py-2 bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 rounded-lg text-sm font-medium">
                Enregistré
              </span>
            )}
          </div>
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

        <a
          href={`${FT_BASE_URL}${offer.ft_id}`}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-2 text-sm text-blue-600 dark:text-blue-400 hover:underline"
        >
          <ExternalLink className="w-4 h-4" />
          Voir l'offre sur France Travail
        </a>
      </div>

      {/* ── Barre sticky de navigation ───────────────────────────────────── */}
      <div className="sticky top-16 z-20 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg px-3 py-2 flex items-center gap-1 shadow-sm">
        <span className="text-xs text-gray-400 dark:text-gray-500 mr-2 shrink-0">Aller à :</span>

        <button
          onClick={() => scrollTo(ficheRef, () => setFicheOpen(true))}
          className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
            ficheOpen
              ? 'bg-purple-100 dark:bg-purple-900/40 text-purple-700 dark:text-purple-300'
              : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800'
          }`}
        >
          <Sparkles className="w-3.5 h-3.5" />
          Fiche synthétique
        </button>

        {offer.description && (
          <button
            onClick={() => scrollTo(descRef, () => setDescOpen(true))}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
              descOpen
                ? 'bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300'
                : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800'
            }`}
          >
            <FileText className="w-3.5 h-3.5" />
            Description
          </button>
        )}

        <button
          onClick={() => scrollTo(notesRef, () => setNotesOpen(true))}
          className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
            notesOpen
              ? 'bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300'
              : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800'
          }`}
        >
          <NotebookPen className="w-3.5 h-3.5" />
          Mes notes
        </button>

        <button
          onClick={() => scrollTo(companyRef, () => setCompanyOpen(true))}
          className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
            companyOpen
              ? 'bg-indigo-100 dark:bg-indigo-900/40 text-indigo-700 dark:text-indigo-300'
              : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800'
          }`}
        >
          <Factory className="w-3.5 h-3.5" />
          Fiche entreprise
        </button>
      </div>

      {/* ── Fiche enrichie (accordéon) ───────────────────────────────────── */}
      <div ref={ficheRef}>
        <CollapsibleSection
          title="Fiche synthétique"
          icon={<Sparkles className="w-4 h-4" />}
          isOpen={ficheOpen}
          onToggle={() => setFicheOpen(prev => !prev)}
          badge={
            enriched ? (
              <span className="text-xs text-gray-400 dark:text-gray-500">
                Mis à jour le {new Date(enriched.updated_at).toLocaleDateString('fr-FR')}
              </span>
            ) : null
          }
        >
          <div className="space-y-6 pt-4">
            {!enriched && (
              <div className="text-center py-8 space-y-3">
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  La fiche synthétique n'a pas encore été générée.
                </p>
                {enriching && (
                  <p className="text-sm text-blue-500 dark:text-blue-400">
                    Génération en cours — profitez-en pour lire la description ou prendre vos notes.
                  </p>
                )}
                {enrichError && (
                  <p className="text-sm text-red-500 dark:text-red-400">{enrichError}</p>
                )}
                <button
                  onClick={handleEnrich}
                  disabled={enriching}
                  className="inline-flex items-center gap-2 px-4 py-2 bg-gray-900 dark:bg-white text-white dark:text-gray-900 rounded-lg text-sm font-medium hover:bg-gray-800 dark:hover:bg-gray-100 transition-colors disabled:opacity-50"
                >
                  {enriching ? <>Génération en cours<AnimatedDots /></> : 'Générer la fiche'}
                </button>
              </div>
            )}

            {enriched && (
              <div className="space-y-6">
                {enriched.summary && (
                  <Section title="Synthèse">
                    <div className="prose prose-sm dark:prose-invert max-w-none break-words overflow-hidden">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {enriched.summary}
                      </ReactMarkdown>
                    </div>
                  </Section>
                )}

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

                <RecalculButton
                  jobId={offer.id}
                  recalculCount={enriched.recalcul_count}
                  recalculRemaining={enriched.recalcul_remaining}
                  onRecalcul={onEnrichedUpdate}
                />
              </div>
            )}
          </div>
        </CollapsibleSection>
      </div>

      {/* ── Description brute (accordéon) ───────────────────────────────── */}
      {offer.description && (
        <div ref={descRef}>
          <CollapsibleSection
            title="Description du poste"
            icon={<FileText className="w-4 h-4" />}
            isOpen={descOpen}
            onToggle={() => setDescOpen(prev => !prev)}
          >
            <p className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-line leading-relaxed pt-4">
              {offer.description}
            </p>
          </CollapsibleSection>
        </div>
      )}

      {/* ── Mes notes (accordéon) ────────────────────────────────────────── */}
      <div ref={notesRef}>
        <CollapsibleSection
          title="Mes notes"
          icon={<NotebookPen className="w-4 h-4" />}
          isOpen={notesOpen}
          onToggle={() => setNotesOpen(prev => !prev)}
        >
          <JobNotes jobId={offer.id} initialNotes={notes} onNotesSaved={setNotes} />
        </CollapsibleSection>
      </div>

      <div ref={companyRef}>
        <CollapsibleSection
          title="Fiche entreprise"
          icon={<Factory className="w-4 h-4" />}
          isOpen={companyOpen}
          onToggle={() => setCompanyOpen(prev => !prev)}
          keepMounted
        >
          {/* <CompanySection
            jobId={offer.id}
            companyName={offer.company_name}
            companyProfileId={companyProfileId}
            onProfileCreated={setCompanyProfileId}
          /> */}
          <CompanySection
            jobId={offer.id}
            companyName={offer.company_name}
            companyProfileId={companyProfileId}
            companyDescription={offer.company_description}
            onProfileCreated={setCompanyProfileId}
          />
        </CollapsibleSection>
      </div>

    </div>

    
  );
}