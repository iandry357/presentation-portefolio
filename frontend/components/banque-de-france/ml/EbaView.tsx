'use client';

import { EbaScoresResponse, EbaRecord } from '@/lib/banqueApi';

interface Props {
  data: EbaScoresResponse;
}

const RATIO_LABELS: Record<string, string> = {
  cet1_ratio: 'CET1 (solvabilité)',
  leverage_ratio: 'Levier',
  npl_ratio: 'NPL (qualité actifs)',
};

function latestPerBank(records: EbaRecord[]): EbaRecord[] {
  const byBank = new Map<string, EbaRecord>();
  for (const r of records) {
    const current = byBank.get(r.bank_name);
    if (!current || r.period > current.period) byBank.set(r.bank_name, r);
  }
  return Array.from(byBank.values()).sort((a, b) => b.composite_score - a.composite_score);
}

function ScoreBadge({ score }: { score: number }) {
  const pct = (score * 100).toFixed(1);
  const color = score >= 0 ? 'text-green-700 bg-green-50' : 'text-red-700 bg-red-50';
  return (
    <span className={`text-sm font-semibold px-2 py-1 rounded ${color}`}>
      {score >= 0 ? '+' : ''}{pct} pts
    </span>
  );
}

function GapRow({ label, gap }: { label: string; gap: number }) {
  const pct = (gap * 100).toFixed(2);
  const color = gap >= 0 ? 'text-green-600' : 'text-red-600';
  return (
    <div className="flex items-center justify-between text-xs">
      <span className="text-gray-500">{label}</span>
      <span className={`font-medium ${color}`}>{gap >= 0 ? '+' : ''}{pct} pts</span>
    </div>
  );
}

export default function EbaView({ data }: Props) {
  const latest = latestPerBank(data.records);

  return (
    <div className="space-y-6 w-full max-w-full overflow-hidden">
      <div className="bg-white border rounded-lg p-4">
        <h3 className="font-semibold text-gray-900 mb-1">Scoring composite EBA — Banques françaises</h3>
        <p className="text-sm text-gray-500 mb-2">{data.methodology.description}</p>
        <p className="text-xs text-gray-400">{data.methodology.coverage_note}</p>
        {data.methodology.not_a_regulatory_score && (
          <p className="text-xs text-amber-600 mt-2">
            ⚠️ Indicateur comparatif, pas un score réglementaire officiel.
          </p>
        )}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {latest.map(record => (
          <div key={record.lei_code} className="bg-white border rounded-lg p-4">
            <div className="flex items-center justify-between mb-3">
              <div>
                <p className="font-semibold text-gray-900 text-sm">{record.bank_name}</p>
                <p className="text-xs text-gray-400">{record.period}</p>
              </div>
              <ScoreBadge score={record.composite_score} />
            </div>
            <div className="space-y-1.5 pt-2 border-t">
              {Object.entries(record.gaps_vs_eu_average).map(([key, gap]) => (
                <GapRow key={key} label={RATIO_LABELS[key] ?? key} gap={gap} />
              ))}
            </div>
          </div>
        ))}
      </div>

      <p className="text-xs text-gray-400 text-center">
        Écarts exprimés vs moyenne simple UE ({data.methodology.eu_average_definition.split('(')[0].trim()}).
      </p>
    </div>
  );
}