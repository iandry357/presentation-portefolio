'use client';

import { useEffect, useState } from 'react';
import {
  fetchBdfClassification,
  fetchBdfClassificationExamples,
  ClassificationResponse,
  ClassificationExample,
} from '@/lib/banqueApi';

export default function ClassificationView() {
  const [examples, setExamples] = useState<ClassificationExample[]>([]);
  const [examplesLoading, setExamplesLoading] = useState(true);
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);

  const [text, setText] = useState('');
  const [result, setResult] = useState<ClassificationResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchBdfClassificationExamples()
      .then(res => setExamples(res.examples))
      .catch(() => setError('Impossible de charger les exemples de démo.'))
      .finally(() => setExamplesLoading(false));
  }, []);

  const handleSelectExample = (index: number) => {
    setSelectedIndex(index);
    setText(examples[index].text);
    setResult(null);
    setError(null);
  };

  const handleSubmit = async () => {
    if (!text.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await fetchBdfClassification(text);
      setResult(res);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Erreur inconnue');
    } finally {
      setLoading(false);
    }
  };

  const trueLabels = selectedIndex !== null ? examples[selectedIndex].true_labels : [];

  return (
    <div className="space-y-4">
      <div className="bg-white border rounded-lg p-4">
        <h3 className="font-semibold text-gray-900 mb-1">Classification multi-label — Griefs ACPR</h3>
        <p className="text-sm text-gray-500">
          Corps sentence-camembert-base fine-tuné + têtes k-NN one-vs-rest, une par catégorie.
          Choisissez une décision réelle de démo pour comparer la prédiction du modèle à la vérité terrain.
        </p>
      </div>

      <div className="bg-white border rounded-lg p-4 space-y-3">
        <label className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
          Décision ACPR (exemple de démo)
        </label>
        {examplesLoading ? (
          <div className="h-9 bg-gray-100 rounded-lg animate-pulse" />
        ) : (
          <select
            value={selectedIndex ?? ''}
            onChange={e => handleSelectExample(Number(e.target.value))}
            className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
          >
            <option value="" disabled>Sélectionner une décision...</option>
            {examples.map((ex, i) => (
              <option key={ex.decision_number} value={i}>
                {ex.decision_number} — {ex.true_labels.length > 0 ? ex.true_labels.join(', ') : 'Autre'}
              </option>
            ))}
          </select>
        )}

        {text && (
          <textarea
            value={text}
            onChange={e => setText(e.target.value)}
            rows={6}
            className="w-full border rounded-lg px-3 py-2 text-xs text-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-300 resize-none"
          />
        )}

        <button
          onClick={handleSubmit}
          disabled={loading || !text.trim()}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? '...' : 'Analyser'}
        </button>
      </div>

      {error && <div className="text-red-500 text-sm p-4 border border-red-200 rounded-lg">{error}</div>}

      {result && (
        <div className="bg-white border rounded-lg p-4 space-y-3">
          <div className="flex items-center justify-between">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Griefs détectés</p>
            {selectedIndex !== null && (
              <p className="text-xs text-gray-400">
                Vérité terrain : {trueLabels.length > 0 ? trueLabels.join(', ') : 'Autre'}
              </p>
            )}
          </div>
          {result.predictions.map(pred => {
            const isTruePositive = pred.predicted && trueLabels.includes(pred.category);
            const isFalsePositive = pred.predicted && !trueLabels.includes(pred.category);
            const isFalseNegative = !pred.predicted && trueLabels.includes(pred.category);
            return (
              <div key={pred.category} className="space-y-1">
                <div className="flex items-center justify-between text-sm">
                  <span className={pred.predicted ? 'font-medium text-gray-900' : 'text-gray-500'}>
                    {pred.predicted ? '✅' : '—'} {pred.category}
                    {isFalsePositive && <span className="text-xs text-amber-600 ml-1">(faux positif)</span>}
                    {isFalseNegative && <span className="text-xs text-red-600 ml-1">(manqué)</span>}
                  </span>
                  <span className="text-xs text-gray-400">
                    {Math.round(pred.score * 100)}% (seuil {Math.round(pred.threshold * 100)}%)
                  </span>
                </div>
                <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                  <div
                    className={isTruePositive ? 'h-full bg-green-600' : pred.predicted ? 'h-full bg-amber-500' : 'h-full bg-gray-300'}
                    style={{ width: `${Math.round(pred.score * 100)}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}