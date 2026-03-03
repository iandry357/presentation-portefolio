import Link from 'next/link';
import { MapPin, Clock, Briefcase, Euro, ExternalLink } from 'lucide-react';
import { JobOfferSummary, JobStatus } from '@/types';
import { FT_BASE_URL } from '@/lib/api';


// ============================================================================
// Badge statut
// ============================================================================

const STATUS_STYLES: Record<JobStatus, string> = {
  nouveau:  'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300',
  existant: 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300',
  ferme:    'bg-red-100 text-red-600 dark:bg-red-900 dark:text-red-300',
  consulte: 'bg-blue-100 text-blue-600 dark:bg-blue-900 dark:text-blue-300',
  postule:  'bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300',
};

const STATUS_LABELS: Record<JobStatus, string> = {
  nouveau:  'Nouveau',
  existant: 'Existant',
  ferme:    'Fermé',
  consulte: 'Consulté',
  postule:  'Postulé',
};

function StatusBadge({ status }: { status: JobStatus }) {
  return (
    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${STATUS_STYLES[status]}`}>
      {STATUS_LABELS[status]}
    </span>
  );
}

// ============================================================================
// Formatage date
// ============================================================================

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '';
  const date = new Date(dateStr);
  const now = new Date();
  const diffDays = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24));
  if (diffDays === 0) return "Aujourd'hui";
  if (diffDays === 1) return 'Hier';
  if (diffDays < 7) return `Il y a ${diffDays} jours`;
  return date.toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' });
}

// ============================================================================
// JobCard
// ============================================================================

interface JobCardProps {
  offer: JobOfferSummary;
}

export default function JobCard({ offer }: JobCardProps) {
  return (
    <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-5 hover:shadow-md transition-shadow">

      {/* Header */}
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex-1 min-w-0">
          <Link
            href={`/jobs/${offer.id}`}
            className="text-base font-semibold text-gray-900 dark:text-white hover:text-blue-600 dark:hover:text-blue-400 transition-colors line-clamp-2"
          >
            {offer.title}
          </Link>
          {offer.company_name && (
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
              {offer.company_name}
            </p>
          )}
        </div>
        <StatusBadge status={offer.status} />
      </div>

      {/* Infos clés */}
      <div className="flex flex-wrap gap-x-4 gap-y-1.5 text-sm text-gray-600 dark:text-gray-400 mb-3">
        {offer.location_label && (
          <span className="flex items-center gap-1">
            <MapPin className="w-3.5 h-3.5 shrink-0" />
            {offer.location_label}
          </span>
        )}
        {offer.contract_label && (
          <span className="flex items-center gap-1">
            <Briefcase className="w-3.5 h-3.5 shrink-0" />
            {offer.contract_label}
          </span>
        )}
        {offer.work_time && (
          <span className="flex items-center gap-1">
            <Clock className="w-3.5 h-3.5 shrink-0" />
            {offer.work_time}
          </span>
        )}
        {offer.salary_label && (
          <span className="flex items-center gap-1">
            <Euro className="w-3.5 h-3.5 shrink-0" />
            {offer.salary_label}
          </span>
        )}
      </div>

      {/* Expérience + secteur */}
      {(offer.experience_label || offer.sector_label) && (
        <div className="flex flex-wrap gap-2 mb-4">
          {offer.experience_label && (
            <span className="text-xs bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 px-2 py-0.5 rounded">
              {offer.experience_label}
            </span>
          )}
          {offer.sector_label && (
            <span className="text-xs bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 px-2 py-0.5 rounded">
              {offer.sector_label}
            </span>
          )}
        </div>
      )}

      {offer.description && (
        <p className="text-xs text-gray-500 dark:text-gray-400 line-clamp-2 mb-3">
          {offer.description.split(' ').slice(0, 20).join(' ')}...
        </p>
      )}

      {/* Footer */}
      <div className="flex items-center justify-between pt-3 border-t border-gray-100 dark:border-gray-700">
        <span className="text-xs text-gray-400 dark:text-gray-500">
          {formatDate(offer.ft_published_at)}
        </span>
        <div className="flex items-center gap-3">
          
            <a
              href={`${FT_BASE_URL}${offer.ft_id}`}
              target="_blank"
              rel="noopener noreferrer"
              onClick={e => e.stopPropagation()}
              className="inline-flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400 hover:text-blue-600 dark:hover:text-blue-400 transition-colors"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              Voir l'offre
            </a>
          
          <Link
            href={`/jobs/${offer.id}`}
            className="text-xs font-medium text-blue-600 dark:text-blue-400 hover:underline"
          >
            {offer.has_enriched ? 'Voir la fiche' : 'Détail →'}
          </Link>
        </div>
      </div>
    </div>
  );
}