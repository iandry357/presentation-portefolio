'use client';

import { useEffect, useState } from 'react';
import { fetchClustering, fetchForecasting, fetchTopicModeling, ClusteringResponse, ForecastingResponse, TopicModelingResponse } from '@/lib/sanofiApi';
import ClusteringView from './ClusteringView';
import ForecastingView from './ForecastingView';
import TopicView from './TopicView';
import { cn } from '@/lib/utils';

type MlTab = 'clustering' | 'forecasting' | 'topics';

const TABS: { id: MlTab; label: string; icon: string }[] = [
  { id: 'clustering',  label: 'Clustering',    icon: '🔵' },
  { id: 'forecasting', label: 'Forecasting',   icon: '📈' },
  { id: 'topics',      label: 'Topic Modeling', icon: '📋' },
];

export default function MlView() {
  const [tab, setTab] = useState<MlTab>('clustering');
  const [clustering, setClustering] = useState<ClusteringResponse | null>(null);
  const [forecasting, setForecasting] = useState<ForecastingResponse | null>(null);
  const [topics, setTopics] = useState<TopicModelingResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        if (tab === 'clustering' && !clustering) {
          setClustering(await fetchClustering());
        } else if (tab === 'forecasting' && !forecasting) {
          setForecasting(await fetchForecasting());
        } else if (tab === 'topics' && !topics) {
          setTopics(await fetchTopicModeling());
        }
      } catch (e) {
        setError('Impossible de charger les données ML.');
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [tab]);

  return (
    // <div className="space-y-4">
    <div className="space-y-4 overflow-x-hidden">
      {/* Sous-onglets */}
      {/* <div className="flex gap-1 bg-gray-100 rounded-lg p-1"> */}
      <div className="flex gap-1 bg-gray-100 rounded-lg p-1 overflow-x-auto">
        {TABS.map(({ id, label, icon }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={cn(
              'flex-1 flex items-center justify-center gap-2 px-3 py-2 text-sm font-medium rounded-md transition-colors',
              tab === id
                ? 'bg-white text-gray-900 shadow-sm'
                : 'text-gray-500 hover:text-gray-700'
            )}
          >
            <span>{icon}</span>
            <span>{label}</span>
          </button>
        ))}
      </div>

      {/* Contenu */}
      {loading && (
        <div className="bg-white border rounded-lg p-8 text-center text-sm text-gray-400">
          Chargement…
        </div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-600">
          {error}
        </div>
      )}

      {!loading && !error && (
        <>
          {tab === 'clustering' && clustering && <ClusteringView data={clustering} />}
          {tab === 'forecasting' && forecasting && <ForecastingView data={forecasting} />}
          {tab === 'topics' && topics && <TopicView data={topics} />}
        </>
      )}
    </div>
  );
}