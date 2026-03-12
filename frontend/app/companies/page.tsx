'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Building2, ChevronRight } from 'lucide-react';
import { CompanyProfileSummary, CompanyLayerStatus } from '@/types';
import { getCompanies, deleteCompany } from '@/lib/api';
import { Trash2 } from 'lucide-react';

// ============================================================================
// Helpers
// ============================================================================

function StatusDot({ status }: { status: CompanyLayerStatus }) {
  const colors: Record<CompanyLayerStatus, string> = {
    done:    'bg-green-500',
    pending: 'bg-yellow-400 animate-pulse',
    failed:  'bg-red-500',
  };
  return <span className={`inline-block w-2 h-2 rounded-full ${colors[status]}`} />;
}

function CompanyCard({ company, onDelete }: { 
    company: CompanyProfileSummary;
    onDelete: (id: number) => void;
    }) {
  const date = new Date(company.created_at).toLocaleDateString('fr-FR');

  return (
    <Link
      href={`/companies/${company.id}`}
      className="block bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4 hover:border-gray-300 dark:hover:border-gray-600 transition-colors"
    >

      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3 min-w-0">
          <Building2 className="w-5 h-5 text-gray-400 shrink-0" />
          <span className="font-medium text-gray-900 dark:text-white truncate">
            {company.name}
          </span>
        </div>
        
        <ChevronRight className="w-4 h-4 text-gray-400 shrink-0 mt-0.5" />
      </div>
      {process.env.NEXT_PUBLIC_ENV !== 'production' && (
            <button
                onClick={e => { e.preventDefault(); onDelete(company.id); }}
                className="p-1.5 text-gray-400 hover:text-red-500 transition-colors"
            >
                <Trash2 className="w-4 h-4" />
            </button>
        )}

      {/* Statuts des 4 couches */}
      <div className="mt-3 flex items-center gap-3 text-xs text-gray-500 dark:text-gray-400">
        <span className="flex items-center gap-1">
          <StatusDot status={company.discovery_status} /> Identité
        </span>
        <span className="flex items-center gap-1">
          <StatusDot status={company.legal_status} /> Légal
        </span>
        <span className="flex items-center gap-1">
          <StatusDot status={company.actualites_status} /> Actualités
        </span>
        <span className="flex items-center gap-1">
          <StatusDot status={company.memo_status} /> Mémo
        </span>
      </div>

      <p className="mt-2 text-xs text-gray-400 dark:text-gray-500">
        Créée le {date}
      </p>
    </Link>
  );
}

// ============================================================================
// Page
// ============================================================================

export default function CompaniesPage() {
  const [companies, setCompanies] = useState<CompanyProfileSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const handleDelete = async (id: number) => {
    try {
        await deleteCompany(id);
        setCompanies(prev => prev.filter(c => c.id !== id));
    } catch (e) {
        console.error(e);
    }
    };

  useEffect(() => {
    getCompanies()
      .then(setCompanies)
      .catch(() => setError('Impossible de charger les fiches entreprises.'))
      .finally(() => setLoading(false));
  }, []);

  return (
    <main className="max-w-3xl mx-auto px-4 py-8 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Fiches entreprises</h1>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
          {companies.length} fiche{companies.length > 1 ? 's' : ''} générée{companies.length > 1 ? 's' : ''}
        </p>
      </div>

      {loading && (
        <p className="text-sm text-gray-500 dark:text-gray-400">Chargement…</p>
      )}

      {error && (
        <p className="text-sm text-red-500 dark:text-red-400">{error}</p>
      )}

      {!loading && !error && companies.length === 0 && (
        <div className="text-center py-16 text-gray-400 dark:text-gray-500 space-y-2">
          <Building2 className="w-10 h-10 mx-auto opacity-30" />
          <p className="text-sm">Aucune fiche entreprise générée pour l'instant.</p>
          <p className="text-xs">Ouvrez le détail d'une offre pour générer la première fiche.</p>
        </div>
      )}

      {!loading && !error && companies.length > 0 && (
        <div className="space-y-3">
          {companies.map(c => (
            <CompanyCard key={c.id} company={c} onDelete={handleDelete} />
          ))}
        </div>
      )}
    </main>
  );
}