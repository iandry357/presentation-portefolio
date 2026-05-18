'use client';

import { useEffect, useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { fetchPubMed, PubMedItem } from '@/lib/sanofiApi';

export default function PubMedView() {
  const [items, setItems] = useState<PubMedItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    fetchPubMed({ limit: 100 })
      .then(res => { setItems(res.items); setTotal(res.total); })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="flex items-center justify-center h-48 text-gray-400">Chargement...</div>;
  if (error) return <div className="text-red-500 p-4">{error}</div>;

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-900">Publications R&D Sanofi</h2>
        <span className="text-sm text-gray-500">{total} résultats</span>
      </div>

      <div className="space-y-3">
        {items.map(item => (
          <div key={item.id} className="border rounded-lg p-4 bg-white hover:shadow-sm transition-shadow">
            <a
              href={item.url ?? '#'}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm font-medium text-blue-700 hover:underline block mb-2"
            >
              {item.title}
            </a>

            <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-500 mb-2">
              {item.date && <span>📅 {item.date}</span>}
              {item.journal && <span>📖 {item.journal}</span>}
              {item.authors && item.authors.length > 0 && (
                <span>👥 {item.authors.slice(0, 3).join(', ')}{item.authors.length > 3 ? ` +${item.authors.length - 3}` : ''}</span>
              )}
            </div>

            {item.keywords && item.keywords.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {item.keywords.slice(0, 5).map(kw => (
                  <Badge key={kw} variant="outline" className="text-xs">{kw}</Badge>
                ))}
                {item.keywords.length > 5 && (
                  <Badge variant="outline" className="text-xs">+{item.keywords.length - 5}</Badge>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}