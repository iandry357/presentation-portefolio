'use client';

import { useEffect, useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { fetchClinicalTrials, ClinicalTrialItem } from '@/lib/sanofiApi';

interface Props {
  phase: string;
  status: string;
}

const STATUS_COLOR: Record<string, string> = {
  RECRUITING: 'bg-green-100 text-green-700',
  COMPLETED: 'bg-gray-100 text-gray-700',
  ACTIVE_NOT_RECRUITING: 'bg-blue-100 text-blue-700',
  NOT_YET_RECRUITING: 'bg-yellow-100 text-yellow-700',
  TERMINATED: 'bg-red-100 text-red-700',
};

export default function ClinicalTrialsView({ phase, status }: Props) {
  const [items, setItems] = useState<ClinicalTrialItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetchClinicalTrials({ limit: 100, phase: phase || undefined, status: status || undefined })
      .then(res => { setItems(res.items); setTotal(res.total); })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [phase, status]);

  if (loading) return <div className="flex items-center justify-center h-48 text-gray-400">Chargement...</div>;
  if (error) return <div className="text-red-500 p-4">{error}</div>;

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-900">Essais Cliniques Sanofi</h2>
        <span className="text-sm text-gray-500">{total} résultats</span>
      </div>

      <div className="space-y-3">
        {items.map(item => (
          <div key={item.id} className="border rounded-lg p-4 bg-white hover:shadow-sm transition-shadow">
            <div className="flex items-start justify-between gap-3 mb-2">
              <a
                href={item.url ?? '#'}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm font-medium text-blue-700 hover:underline flex-1"
              >
                {item.title}
              </a>
              <div className="flex gap-2 shrink-0">
                {item.phase && (
                  <Badge variant="outline" className="text-xs">{item.phase}</Badge>
                )}
                {item.status && (
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_COLOR[item.status] ?? 'bg-gray-100 text-gray-600'}`}>
                    {item.status.replace(/_/g, ' ')}
                  </span>
                )}
              </div>
            </div>

            <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-500">
              {item.date && <span>📅 {item.date}</span>}
              {item.study_type && <span>🔍 {item.study_type}</span>}
              {item.sponsor && <span>🏢 {item.sponsor}</span>}
            </div>

            {item.conditions && item.conditions.length > 0 && (
              <div className="flex flex-wrap gap-1 mt-2">
                {item.conditions.slice(0, 4).map(c => (
                  <Badge key={c} variant="secondary" className="text-xs">{c}</Badge>
                ))}
                {item.conditions.length > 4 && (
                  <Badge variant="secondary" className="text-xs">+{item.conditions.length - 4}</Badge>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}