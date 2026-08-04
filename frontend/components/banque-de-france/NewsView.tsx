'use client';

import { useEffect, useState } from 'react';
import { fetchBdfNews, NewsItem } from '@/lib/banqueApi';

const PAGE_SIZE = 20;

export default function NewsView() {
  const [items, setItems]     = useState<NewsItem[]>([]);
  const [total, setTotal]     = useState(0);
  const [page, setPage]       = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    fetchBdfNews({ limit: PAGE_SIZE, offset: page * PAGE_SIZE })
      .then(res => { setItems(res.items); setTotal(res.total); })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [page]);

  const totalPages = Math.ceil(total / PAGE_SIZE);

  if (error) return <div className="text-red-500 p-4">{error}</div>;

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-900">Actualités Banque de France</h2>
        <span className="text-sm text-gray-500">{total} résultats</span>
      </div>

      {loading ? (
        <div className="space-y-3">
          {[...Array(PAGE_SIZE)].map((_, i) => (
            <div key={i} className="border rounded-lg p-4 bg-white animate-pulse h-16" />
          ))}
        </div>
      ) : (
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
                {item.source && <span>🗞️ {item.source}</span>}
              </div>
            </div>
          ))}
        </div>
      )}

      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-6">
          <button
            onClick={() => setPage(p => p - 1)}
            disabled={page === 0 || loading}
            className="px-4 py-2 text-sm border rounded-lg text-gray-600 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            ← Précédent
          </button>
          <span className="text-sm text-gray-500">
            Page {page + 1} / {totalPages}
          </span>
          <button
            onClick={() => setPage(p => p + 1)}
            disabled={page >= totalPages - 1 || loading}
            className="px-4 py-2 text-sm border rounded-lg text-gray-600 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            Suivant →
          </button>
        </div>
      )}
    </div>
  );
}