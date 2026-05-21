'use client';

import { useEffect, useState } from 'react';
import { fetchPressReleases, PressReleaseItem } from '@/lib/sanofiApi';

export default function PressReleasesView() {
  const [items, setItems] = useState<PressReleaseItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    fetchPressReleases({ limit: 50 })
      .then(res => { setItems(res.items); setTotal(res.total); })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="flex items-center justify-center h-48 text-gray-400">Chargement...</div>;
  if (error) return <div className="text-red-500 p-4">{error}</div>;

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-900">Press Releases Sanofi</h2>
        <span className="text-sm text-gray-500">{total} résultats</span>
      </div>

      <div className="space-y-3">
        {items.map(item => (
          <div key={item.id} className="border rounded-lg p-4 bg-white hover:shadow-sm transition-shadow">
            <a
              href={item.url ?? '#'}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm font-medium text-blue-700 hover:underline block mb-1"
            >
              {item.title}
            </a>
            <div className="flex gap-x-4 text-xs text-gray-500">
              {item.date && <span>📅 {item.date}</span>}
              {item.source_name && <span>🗞️ {item.source_name}</span>}
            </div>
          </div>
        ))}

        {items.length === 0 && (
          <div className="text-center text-gray-400 text-sm py-12">
            Aucun press release disponible.
          </div>
        )}
      </div>
    </div>
  );
}