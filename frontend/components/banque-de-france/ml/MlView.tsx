'use client';

import { useEffect, useState } from 'react';
import { fetchBdfTopicModeling, fetchBdfEbaScores, TopicModelingResponse, EbaScoresResponse } from '@/lib/banqueApi';
import { cn } from '@/lib/utils';
import TopicView from './TopicView';
import EbaView from './EbaView';
import ClassificationView from './ClassificationView';

type MlTab = 'topics' | 'eba' | 'classification';

const TABS: { id: MlTab; label: string; icon: string }[] = [
  { id: 'topics',         label: 'Topic Modeling',  icon: '📋' },
  { id: 'eba',            label: 'Scoring EBA',     icon: '🏦' },
  { id: 'classification', label: 'Classification',  icon: '⚖️' },
];

export default function MlView() {
  const [tab, setTab] = useState<MlTab>('topics');

  const [topics, setTopics] = useState<TopicModelingResponse | null>(null);
  const [topicsLoading, setTopicsLoading] = useState(false);
  const [topicsError, setTopicsError] = useState<string | null>(null);

  const [eba, setEba] = useState<EbaScoresResponse | null>(null);
  const [ebaLoading, setEbaLoading] = useState(false);
  const [ebaError, setEbaError] = useState<string | null>(null);

  useEffect(() => {
    if (tab !== 'topics' || topics) return;
    setTopicsLoading(true);
    setTopicsError(null);
    fetchBdfTopicModeling()
      .then(setTopics)
      .catch(() => setTopicsError('Impossible de charger le topic modeling.'))
      .finally(() => setTopicsLoading(false));
  }, [tab, topics]);

  useEffect(() => {
    if (tab !== 'eba' || eba) return;
    setEbaLoading(true);
    setEbaError(null);
    fetchBdfEbaScores()
      .then(setEba)
      .catch(() => setEbaError('Impossible de charger le scoring EBA.'))
      .finally(() => setEbaLoading(false));
  }, [tab, eba]);

  return (
    <div className="space-y-4 overflow-x-hidden">
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
            <span className="hidden sm:inline">{label}</span>
          </button>
        ))}
      </div>

      {tab === 'topics' && (
        <>
          {topicsLoading && (
            <div className="bg-white border rounded-lg p-8 text-center text-sm text-gray-400">Chargement…</div>
          )}
          {topicsError && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-600">{topicsError}</div>
          )}
          {!topicsLoading && !topicsError && topics && <TopicView data={topics} />}
        </>
      )}

      {tab === 'eba' && (
        <>
          {ebaLoading && (
            <div className="bg-white border rounded-lg p-8 text-center text-sm text-gray-400">Chargement…</div>
          )}
          {ebaError && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-600">{ebaError}</div>
          )}
          {!ebaLoading && !ebaError && eba && <EbaView data={eba} />}
        </>
      )}

      {tab === 'classification' && <ClassificationView />}
    </div>
  );
}