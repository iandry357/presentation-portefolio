'use client';

import { useEffect, useState } from 'react';
import { fetchSgTopicModeling, TopicModelingResponse } from '@/lib/sgApi';
import DocumentView from './DocumentView';
import { cn } from '@/lib/utils';
import TopicView from './TopicView';

type MlTab = 'topics' | 'documents';

const TABS: { id: MlTab; label: string; icon: string }[] = [
  { id: 'topics',    label: 'Topic Modeling', icon: '📋' },
  { id: 'documents', label: 'Documents',      icon: '📄' },
];


export default function MlView() {
  const [tab, setTab]         = useState<MlTab>('topics');
  const [topics, setTopics]   = useState<TopicModelingResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState<string | null>(null);

  useEffect(() => {
    if (tab !== 'topics' || topics) return;
    setLoading(true);
    setError(null);
    fetchSgTopicModeling()
      .then(setTopics)
      .catch(() => setError('Impossible de charger les données ML.'))
      .finally(() => setLoading(false));
  }, [tab]);

  return (
    <div className="space-y-4 overflow-x-hidden">
      {/* Onglets */}
      <div className="flex gap-1 bg-gray-100 rounded-lg p-1">
        {TABS.map(({ id, label, icon }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={cn(
              'flex-1 flex items-center justify-center gap-2 px-3 py-2 text-sm font-medium rounded-md transition-colors',
              tab === id ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'
            )}
          >
            <span>{icon}</span>
            <span>{label}</span>
          </button>
        ))}
      </div>

      {/* Contenu */}
      {tab === 'topics' && (
        <>
          {loading && (
            <div className="bg-white border rounded-lg p-8 text-center text-sm text-gray-400">Chargement…</div>
          )}
          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-600">{error}</div>
          )}
          {!loading && !error && topics && <TopicView data={topics} />}
        </>
      )}

      {tab === 'documents' && <DocumentView />}
    </div>
  );
}