'use client';

import { useEffect, useState } from 'react';
import { fetchNews, NewsItem } from '@/lib/savenciaApi';

interface Props {
  feed_name?: string;
}

const FEED_LABELS: Record<string, string> = {
  savencia_news: 'Savencia',
  agroalimentaire_ia: 'Agroalimentaire IA',
};

const FEED_COLORS: Record<string, string> = {
  savencia_news: 'bg-blue-100 text-blue-700',
  agroalimentaire_ia: 'bg-green-100 text-green-700',
};

export default function NewsView({ feed_name }: Props) {
  const [items, setItems] = useState<NewsItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetchNews({ limit: 50, feed_name: feed_name || undefined })
      .then(res => { setItems(res.items); setTotal(res.total); })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [feed_name]);

  if (loading) return (
    <div className="space-y-3">
      {[...Array(5)].map((_, i) => (
        <div key={i} className="border rounded-lg p-4 bg-white animate-pulse h-16" />
      ))}
    </div>
  );

  if (error) return <div className="text-red-500 p-4">{error}</div>;

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-900">Actualités</h2>
        <span className="text-sm text-gray-500">{total} articles</span>
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
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-gray-500">
              {item.date && <span>📅 {item.date}</span>}
              {item.source_name && <span>🗞️ {item.source_name}</span>}
              {item.feed_name && (
                <span className={`px-2 py-0.5 rounded-full font-medium ${FEED_COLORS[item.feed_name] ?? 'bg-gray-100 text-gray-600'}`}>
                  {FEED_LABELS[item.feed_name] ?? item.feed_name}
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}