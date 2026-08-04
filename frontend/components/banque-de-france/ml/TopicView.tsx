'use client';

import { useState } from 'react';
import { TopicModelingResponse } from '@/lib/banqueApi';

const COLORS = ['#3b82f6', '#8b5cf6', '#ec4899', '#f59e0b', '#10b981'];

interface Props {
  data: TopicModelingResponse;
}

export default function TopicView({ data }: Props) {
  const [expanded, setExpanded] = useState<Record<number, boolean>>({});

  const byTopic = data.topics.map(t => ({
    ...t,
    docs: data.docs
      .filter(d => d.dominant_topic === t.topic_id)
      .sort((a, b) => b.confidence - a.confidence),
  }));

  return (
    <div className="space-y-6 w-full max-w-full overflow-hidden">
      <div className="bg-white border rounded-lg p-4">
        <h3 className="font-semibold text-gray-900 mb-1">Topic Modeling — Veille Banque de France</h3>
        <p className="text-sm text-gray-500">
          {data.total_docs} documents analysés → {data.n_topics} topics LDA
        </p>
      </div>

      {byTopic.map((topic, i) => (
        <div key={topic.topic_id} className="bg-white border rounded-lg overflow-hidden">
          <div
            className="flex items-center gap-3 px-4 py-3 border-b border-l-4"
            style={{ borderLeftColor: COLORS[i % COLORS.length] }}
          >
            <span className="text-lg font-bold" style={{ color: COLORS[i % COLORS.length] }}>
              #{topic.topic_id}
            </span>
            <div>
              <p className="font-semibold text-gray-900 text-sm">{topic.label}</p>
              <p className="text-xs text-gray-400">{topic.docs.length} documents</p>
            </div>
          </div>

          <div className="px-4 py-2 border-b bg-gray-50 flex flex-wrap gap-1 overflow-hidden">
            {topic.keywords.slice(0, 8).map(kw => (
              <span key={kw} className="text-xs bg-white border rounded px-2 py-0.5 text-gray-600">
                {kw}
              </span>
            ))}
          </div>

          <div className="divide-y">
            {topic.docs.slice(0, expanded[topic.topic_id] ? topic.docs.length : 5).map(doc => (
              <div key={doc.id} className="px-4 py-2 flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0 w-0">
                  {doc.url ? (
                    <a
                      href={doc.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm text-blue-700 hover:underline truncate block"
                    >
                      {doc.title}
                    </a>
                  ) : (
                    <p className="text-sm text-gray-800 truncate">{doc.title}</p>
                  )}
                  <p className="text-xs text-gray-400 mt-0.5">{doc.date}</p>
                </div>
                <span className="text-xs text-gray-400 shrink-0">{Math.round(doc.confidence * 100)}%</span>
              </div>
            ))}

            {topic.docs.length > 5 && (
              <button
                onClick={() => setExpanded(e => ({ ...e, [topic.topic_id]: !e[topic.topic_id] }))}
                className="px-4 py-2 text-xs text-blue-600 hover:underline text-left w-full"
              >
                {expanded[topic.topic_id] ? '− Réduire' : `+ ${topic.docs.length - 5} autres documents`}
              </button>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}