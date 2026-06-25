'use client';

import { useState, useMemo } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
  ScatterChart, Scatter, ZAxis, CartesianGrid, ReferenceLine,
} from 'recharts';
import { ClusteringResponse, TherapeuticInsightResponse, ClusterInsight, TargetSignal } from '@/lib/sanofiApi';

// ---------------------------------------------------------------------------
// Constantes
// ---------------------------------------------------------------------------

const CLUSTER_COLORS = [
  '#3b82f6','#8b5cf6','#ec4899','#f59e0b','#10b981',
  '#06b6d4','#f97316','#84cc16','#6366f1','#14b8a6','#e11d48',
];

const PROFILE_COLORS: Record<string, string> = {
  'Mature':       '#10b981',  // vert
  'Émergent':     '#6366f1',  // indigo
  'Actif':        '#f59e0b',  // ambre
  'Exploratoire': '#94a3b8',  // gris-bleu
};

const PROFILE_LABELS: Record<string, string> = {
  'Mature':       'Cibles validées, médicaments approuvés',
  'Émergent':     'Forte activité biologique, pipeline en construction',
  'Actif':        'Médicaments existants, biologie moins documentée',
  'Exploratoire': 'Territoire peu exploré — signaux faibles potentiels',
};

const PHASE_RANK: Record<string, number> = {
  PHASE1: 1, PHASE2: 2, PHASE3: 3, PHASE4: 4, APPROVAL: 5, APPROVED: 5,
};

const STAGE_LABEL: Record<string, string> = {
  PHASE1: 'Phase I', PHASE2: 'Phase II', PHASE3: 'Phase III',
  PHASE4: 'Phase IV', APPROVAL: 'Approuvé', APPROVED: 'Approuvé',
};

// ---------------------------------------------------------------------------
// Interfaces
// ---------------------------------------------------------------------------

interface Props {
  data: ClusteringResponse;
  insight: TherapeuticInsightResponse;
}

// ---------------------------------------------------------------------------
// Sous-composant — Tooltip scatter plot
// ---------------------------------------------------------------------------

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function ScatterTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-3 shadow-lg text-xs max-w-[220px]">
      <p className="font-semibold text-gray-900 mb-1">{d.label}</p>
      <p className="text-gray-500">Bio score : <span className="text-gray-800 font-medium">{d.y.toFixed(3)}</span></p>
      <p className="text-gray-500">Drug rate : <span className="text-gray-800 font-medium">{(d.x * 100).toFixed(1)}%</span></p>
      <span
        className="inline-block mt-1 px-2 py-0.5 rounded-full text-white text-[10px] font-medium"
        style={{ backgroundColor: PROFILE_COLORS[d.profile] }}
      >
        {d.profile}
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sous-composant — Badge profil
// ---------------------------------------------------------------------------

function ProfileBadge({ profile }: { profile: string }) {
  return (
    <span
      className="inline-flex items-center px-2 py-0.5 rounded-full text-white text-[10px] font-medium"
      style={{ backgroundColor: PROFILE_COLORS[profile] ?? '#94a3b8' }}
    >
      {profile}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Sous-composant — Panneau signaux d'un cluster
// ---------------------------------------------------------------------------

function SignalsPanel({ cluster }: { cluster: ClusterInsight }) {
  const medianScore = useMemo(() => {
    if (!cluster.targets.length) return 0;
    const sorted = [...cluster.targets].sort((a, b) => a.score - b.score);
    const mid = Math.floor(sorted.length / 2);
    return sorted.length % 2 !== 0
      ? sorted[mid].score
      : (sorted[mid - 1].score + sorted[mid].score) / 2;
  }, [cluster.targets]);

  const strongSignals = useMemo(
    () => [...cluster.targets]
      .sort((a, b) => b.score - a.score)
      .slice(0, 10),
    [cluster.targets]
  );

  const weakSignals = useMemo(
    () => cluster.targets
      .filter(t => t.score < medianScore)
      .sort((a, b) => b.frequency - a.frequency)
      .slice(0, 10),
    [cluster.targets, medianScore]
  );

  const TargetRow = ({ t, showScore = true }: { t: TargetSignal; showScore?: boolean }) => (
    <tr className="border-b last:border-0 hover:bg-gray-50">
      <td className="px-3 py-2">
        <span className="font-medium text-blue-700">{t.symbol}</span>
        {t.approved_name && (
          <span className="ml-2 text-[10px] text-gray-500 italic">{t.approved_name}</span>
        )}
        <span className="ml-1 text-[10px] text-gray-300">{t.ensembl_id}</span>
      </td>
      {showScore && (
        <td className="px-3 py-2 text-right text-gray-700 tabular-nums">
          {t.score.toFixed(3)}
        </td>
      )}
      <td className="px-3 py-2 text-right tabular-nums text-gray-500">
        {t.frequency}×
      </td>
      <td className="px-3 py-2 text-right">
        {t.has_approved_drug ? (
          <span className="text-green-600 text-xs font-medium">✓ Approuvé</span>
        ) : t.max_clinical_stage ? (
          <span className="text-amber-600 text-xs">
            {STAGE_LABEL[t.max_clinical_stage] ?? t.max_clinical_stage}
          </span>
        ) : (
          <span className="text-gray-300 text-xs">—</span>
        )}
      </td>
    </tr>
  );

  return (
    <div className="space-y-4">
      {/* Header cluster */}
      <div className="flex items-center justify-between">
        <div>
          <h4 className="font-semibold text-gray-900">{cluster.label}</h4>
          <p className="text-xs text-gray-500 mt-0.5">
            {cluster.count} essais · {cluster.targets.length} cibles biologiques · {cluster.diseases_searched.length} conditions analysées
          </p>
        </div>
        <div className="text-right">
          <ProfileBadge profile={cluster.profile} />
          <p className="text-[10px] text-gray-400 mt-1 max-w-[180px]">
            {PROFILE_LABELS[cluster.profile]}
          </p>
        </div>
      </div>

      {/* Encart explicatif signaux */}
      <details className="mb-2">
        <summary className="text-xs text-blue-600 cursor-pointer hover:underline select-none">
          Comment lire les signaux ?
        </summary>
        <div className="mt-2 space-y-2 text-xs text-gray-600 bg-gray-50 rounded-lg p-3">
          <p><span className="font-medium text-gray-800">Signaux forts —</span> cibles les mieux documentées scientifiquement pour ce cluster. Un score élevé signifie de nombreuses évidences convergentes : génétique, essais cliniques, littérature. Ce sont les cibles que Sanofi connaît et travaille probablement déjà.</p>
          <p><span className="font-medium text-gray-800">Signaux faibles —</span> cibles avec un score modeste mais qui apparaissent dans plusieurs diseases du cluster. Une fréquence élevée indique une cible transversale répétée — potentiellement sous-exploitée. Ces cibles ne se voient pas dans une analyse maladie par maladie.</p>
        </div>
      </details>

      {/* Métriques */}
      <div className="grid grid-cols-2 gap-3">
        <div className="bg-gray-50 rounded-lg p-3">
          <p className="text-xs text-gray-500">Bio score moyen</p>
          <p className="text-xl font-bold text-gray-900 mt-1">{cluster.bio_score_avg.toFixed(3)}</p>
        </div>
        <div className="bg-gray-50 rounded-lg p-3">
          <p className="text-xs text-gray-500">Médicaments approuvés</p>
          <p className="text-xl font-bold text-gray-900 mt-1">{(cluster.approved_drug_rate * 100).toFixed(0)}%</p>
        </div>
      </div>

      {/* Signaux forts */}
      <div>
        <h5 className="text-xs font-semibold text-gray-700 uppercase tracking-wide mb-2">
          Signaux forts — top score
        </h5>
        {strongSignals.length === 0 ? (
          <p className="text-xs text-gray-400">Aucune cible disponible</p>
        ) : (
          <div className="border rounded-lg overflow-hidden">
            <table className="w-full text-xs">
              <thead className="bg-gray-50 border-b">
                <tr>
                  <th className="text-left px-3 py-2 text-gray-500 font-medium">Cible</th>
                  <th className="text-right px-3 py-2 text-gray-500 font-medium">Score</th>
                  <th className="text-right px-3 py-2 text-gray-500 font-medium">Fréq.</th>
                  <th className="text-right px-3 py-2 text-gray-500 font-medium">Stade</th>
                </tr>
              </thead>
              <tbody>
                {strongSignals.map(t => <TargetRow key={t.ensembl_id} t={t} showScore={true} />)}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Signaux faibles */}
      <div>
        <h5 className="text-xs font-semibold text-gray-700 uppercase tracking-wide mb-1">
          Signaux faibles — fréquence transversale
        </h5>
        <p className="text-[10px] text-gray-400 mb-2">
          Score {'<'} médiane ({medianScore.toFixed(3)}) — cibles apparaissant dans plusieurs diseases
        </p>
        {weakSignals.length === 0 ? (
          <p className="text-xs text-gray-400">Aucun signal faible détecté</p>
        ) : (
          <div className="border rounded-lg overflow-hidden">
            <table className="w-full text-xs">
              <thead className="bg-gray-50 border-b">
                <tr>
                  <th className="text-left px-3 py-2 text-gray-500 font-medium">Cible</th>
                  <th className="text-right px-3 py-2 text-gray-500 font-medium">Fréq.</th>
                  <th className="text-right px-3 py-2 text-gray-500 font-medium">Stade</th>
                </tr>
              </thead>
              <tbody>
                {weakSignals.map(t => <TargetRow key={t.ensembl_id} t={t} showScore={false} />)}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Composant principal
// ---------------------------------------------------------------------------

export default function ClusteringView({ data, insight }: Props) {
  const [selectedClusterId, setSelectedClusterId] = useState<number | null>(null);

  // Données bar chart — triées par count décroissant
  const sortedClusters = useMemo(
    () => [...data.clusters].sort((a, b) => b.count - a.count),
    [data.clusters]
  );

  const chartData = sortedClusters.map((c, i) => ({
    name: c.label,
    trials: c.count,
    color: CLUSTER_COLORS[i % CLUSTER_COLORS.length],
  }));

  // Données phases par cluster
  const phaseByCluster = sortedClusters.map((c, i) => {
    const trials = data.trials.filter(t => t.cluster_id === c.cluster_id);
    const phases: Record<string, number> = {};
    trials.forEach(t => {
      const p = t.phase?.startsWith('PHASE') ? t.phase.split(',')[0].trim() : 'OTHER';
      phases[p] = (phases[p] || 0) + 1;
    });
    return { label: c.label, total: trials.length, phases, color: CLUSTER_COLORS[i % CLUSTER_COLORS.length] };
  });

  // Données scatter plot — depuis insight
  const scatterData = insight.clusters.map((c, i) => ({
    x: c.approved_drug_rate,
    y: c.bio_score_avg,
    z: c.count,
    label: c.label,
    profile: c.profile,
    cluster_id: c.cluster_id,
    color: PROFILE_COLORS[c.profile] ?? '#94a3b8',
  }));

  // Médianes pour les lignes de référence
  const medianBio = useMemo(() => {
    const sorted = [...insight.clusters].map(c => c.bio_score_avg).sort((a, b) => a - b);
    const mid = Math.floor(sorted.length / 2);
    return sorted.length % 2 !== 0 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
  }, [insight.clusters]);

  const medianDrug = useMemo(() => {
    const sorted = [...insight.clusters].map(c => c.approved_drug_rate).sort((a, b) => a - b);
    const mid = Math.floor(sorted.length / 2);
    return sorted.length % 2 !== 0 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
  }, [insight.clusters]);

  // Cluster sélectionné
  const selectedCluster = useMemo(
    () => insight.clusters.find(c => c.cluster_id === selectedClusterId) ?? null,
    [insight.clusters, selectedClusterId]
  );

  return (
    <div className="space-y-6">

      {/* Header */}
      <div className="bg-white border rounded-lg p-4">
        <h3 className="font-semibold text-gray-900 mb-1">Clustering des essais cliniques</h3>
        <p className="text-sm text-gray-500">
          {data.total_trials} essais → {data.n_clusters} clusters — KMeans mixte TF-IDF + embeddings VoyageAI
        </p>
      </div>

      {/* Bar chart */}
      <div className="bg-white border rounded-lg p-4">
        <h4 className="text-sm font-semibold text-gray-700 mb-4">Essais par cluster</h4>
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={chartData} layout="vertical" margin={{ left: 8, right: 24 }}>
            <XAxis type="number" tick={{ fontSize: 11 }} />
            <YAxis type="category" dataKey="name" width={220} tick={{ fontSize: 11 }} />
            <Tooltip formatter={(val) => [`${val} essais`, 'Essais']} contentStyle={{ fontSize: 12 }} />
            <Bar dataKey="trials" radius={[0, 4, 4, 0]}>
              {chartData.map((entry, i) => <Cell key={i} fill={entry.color} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Table phases */}
      <div className="bg-white border rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="text-left px-4 py-2 text-gray-600 font-medium">Cluster</th>
              <th className="text-right px-4 py-2 text-gray-600 font-medium">P1</th>
              <th className="text-right px-4 py-2 text-gray-600 font-medium">P2</th>
              <th className="text-right px-4 py-2 text-gray-600 font-medium">P3</th>
              <th className="text-right px-4 py-2 text-gray-600 font-medium">P4</th>
              <th className="text-right px-4 py-2 text-gray-600 font-medium">Autre</th>
            </tr>
          </thead>
          <tbody>
            {phaseByCluster.map((c, i) => (
              <tr key={i} className="border-b last:border-0 hover:bg-gray-50">
                <td className="px-4 py-2 flex items-center gap-2">
                  <span className="w-3 h-3 rounded-full shrink-0" style={{ backgroundColor: c.color }} />
                  {c.label}
                </td>
                <td className="px-4 py-2 text-right text-blue-400">{c.phases['PHASE1'] || '-'}</td>
                <td className="px-4 py-2 text-right text-green-400">{c.phases['PHASE2'] || '-'}</td>
                <td className="px-4 py-2 text-right text-yellow-400">{c.phases['PHASE3'] || '-'}</td>
                <td className="px-4 py-2 text-right text-pink-400">{c.phases['PHASE4'] || '-'}</td>
                <td className="px-4 py-2 text-right text-gray-400">{c.phases['OTHER'] || '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* ── Therapeutic Insight ── */}
      <div className="bg-white border rounded-lg p-4">
        <div className="flex items-center justify-between mb-1">
          <h3 className="font-semibold text-gray-900">Therapeutic Insight</h3>
          <span className="text-xs text-gray-400">
            Généré le {new Date(insight.generated_at).toLocaleDateString('fr-FR')}
          </span>
        </div>
        <p className="text-sm text-gray-500 mb-4">
          Profils biologiques des clusters — OpenTargets · {insight.clusters.reduce((acc, c) => acc + c.targets.length, 0)} cibles agrégées
        </p>

        {/* Légende profils */}
        <div className="flex flex-wrap gap-3 mb-6">
          {Object.entries(PROFILE_COLORS).map(([profile, color]) => (
            <div key={profile} className="flex items-center gap-1.5 text-xs text-gray-600">
              <span className="w-3 h-3 rounded-full shrink-0" style={{ backgroundColor: color }} />
              <span className="font-medium">{profile}</span>
              <span className="text-gray-400">— {PROFILE_LABELS[profile]}</span>
            </div>
          ))}
        </div>

        {/* Scatter plot */}
        <div className="mb-2">
          <h4 className="text-sm font-semibold text-gray-700 mb-1">
            Positionnement biologique des clusters
          </h4>
          <p className="text-xs text-gray-400 mb-4">
            Cliquer sur un cluster pour explorer ses cibles biologiques
          </p>
          <ResponsiveContainer width="100%" height={320}>
            <ScatterChart margin={{ top: 16, right: 24, bottom: 24, left: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis
                type="number" dataKey="x" name="Drug rate"
                domain={[0, 1]} tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
                tick={{ fontSize: 11 }} label={{ value: 'Approved drug rate', position: 'insideBottom', offset: -12, fontSize: 11, fill: '#94a3b8' }}
              />
              <YAxis
                type="number" dataKey="y" name="Bio score"
                domain={[0, 'auto']} tick={{ fontSize: 11 }}
                label={{ value: 'Bio score avg', angle: -90, position: 'insideLeft', offset: 12, fontSize: 11, fill: '#94a3b8' }}
              />
              <ZAxis type="number" dataKey="z" range={[60, 300]} />
              <Tooltip content={<ScatterTooltip />} />
              <ReferenceLine x={medianDrug} stroke="#e2e8f0" strokeDasharray="4 4" />
              <ReferenceLine y={medianBio} stroke="#e2e8f0" strokeDasharray="4 4" />
              <Scatter
                data={scatterData}
                shape={(props: any) => {
                  const { cx, cy, fill, payload } = props;
                  const isSelected = payload.cluster_id === selectedClusterId;
                  return (
                    <circle
                      cx={cx} cy={cy}
                      r={isSelected ? 14 : 10}
                      fill={fill}
                      fillOpacity={isSelected ? 1 : 0.75}
                      stroke={isSelected ? '#1e293b' : 'white'}
                      strokeWidth={isSelected ? 2 : 1}
                      style={{ cursor: 'pointer' }}
                      onClick={() => setSelectedClusterId(
                        payload.cluster_id === selectedClusterId ? null : payload.cluster_id
                      )}
                    />
                  );
                }}
                fill="#8884d8"
              >
                {scatterData.map((entry, i) => (
                  <Cell key={i} fill={entry.color} />
                ))}
              </Scatter>
            </ScatterChart>
          </ResponsiveContainer>
        </div>

        {/* Encart explicatif scatter */}
        <details className="mb-4">
          <summary className="text-xs text-blue-600 cursor-pointer hover:underline select-none">
            Comment lire ce graphe ?
          </summary>
          <div className="mt-3 space-y-3 text-xs text-gray-600 bg-gray-50 rounded-lg p-4">
            <div>
              <p className="font-semibold text-gray-800 mb-1">Les axes</p>
              <p><span className="font-medium">Axe X — Taux de médicaments approuvés :</span> proportion des cibles biologiques du cluster ayant au moins un médicament approuvé sur le marché. Plus c'est élevé, plus le terrain est balisé pharmaceutiquement.</p>
              <p className="mt-1"><span className="font-medium">Axe Y — Score biologique moyen :</span> niveau de documentation scientifique des cibles — agrège les évidences génétiques, essais cliniques et littérature. Plus c'est élevé, plus les cibles sont bien connues scientifiquement.</p>
            </div>
            <div>
              <p className="font-semibold text-gray-800 mb-1">Les quadrants</p>
              <div className="grid grid-cols-2 gap-2">
                <div className="bg-white rounded p-2 border-l-2" style={{ borderColor: PROFILE_COLORS['Mature'] }}>
                  <p className="font-medium text-gray-800">Mature</p>
                  <p className="text-gray-500">Cibles bien documentées + médicaments existants. Territoire validé par Sanofi.</p>
                </div>
                <div className="bg-white rounded p-2 border-l-2" style={{ borderColor: PROFILE_COLORS['Émergent'] }}>
                  <p className="font-medium text-gray-800">Émergent</p>
                  <p className="text-gray-500">Forte activité biologique mais pipeline encore en construction. Opportunités R&D actives.</p>
                </div>
                <div className="bg-white rounded p-2 border-l-2" style={{ borderColor: PROFILE_COLORS['Actif'] }}>
                  <p className="font-medium text-gray-800">Actif</p>
                  <p className="text-gray-500">Médicaments existants mais biologie moins documentée. Potentiel de repositionnement.</p>
                </div>
                <div className="bg-white rounded p-2 border-l-2" style={{ borderColor: PROFILE_COLORS['Exploratoire'] }}>
                  <p className="font-medium text-gray-800">Exploratoire</p>
                  <p className="text-gray-500">Territoire peu cartographié. Risque élevé, mais opportunités non adressées par la concurrence.</p>
                </div>
              </div>
            </div>
            <div>
              <p className="font-semibold text-gray-800 mb-1">Les lignes pointillées</p>
              <p>Représentent la médiane des 11 clusters — elles séparent les clusters au-dessus et en-dessous de la moyenne du portefeuille Sanofi.</p>
            </div>
          </div>
        </details>

        {/* Table récap profils */}
        <div className="border rounded-lg overflow-hidden mb-6">
          <table className="w-full text-xs">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="text-left px-3 py-2 text-gray-500 font-medium">Cluster</th>
                <th className="text-right px-3 py-2 text-gray-500 font-medium">Cibles</th>
                <th className="text-right px-3 py-2 text-gray-500 font-medium">Bio score</th>
                <th className="text-right px-3 py-2 text-gray-500 font-medium">Drug rate</th>
                <th className="text-right px-3 py-2 text-gray-500 font-medium">Profil</th>
              </tr>
            </thead>
            <tbody>
              {insight.clusters.map((c) => (
                <tr
                  key={c.cluster_id}
                  className={`border-b last:border-0 cursor-pointer transition-colors ${
                    selectedClusterId === c.cluster_id ? 'bg-blue-50' : 'hover:bg-gray-50'
                  }`}
                  onClick={() => setSelectedClusterId(
                    c.cluster_id === selectedClusterId ? null : c.cluster_id
                  )}
                >
                  <td className="px-3 py-2 font-medium text-gray-800">{c.label}</td>
                  <td className="px-3 py-2 text-right text-gray-600">{c.targets.length}</td>
                  <td className="px-3 py-2 text-right text-gray-600 tabular-nums">{c.bio_score_avg.toFixed(3)}</td>
                  <td className="px-3 py-2 text-right text-gray-600 tabular-nums">{(c.approved_drug_rate * 100).toFixed(0)}%</td>
                  <td className="px-3 py-2 text-right">
                    <ProfileBadge profile={c.profile} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Panneau signaux — affiché si cluster sélectionné */}
        {selectedCluster && (
          <div className="border border-blue-100 rounded-lg p-4 bg-blue-50/30">
            <SignalsPanel cluster={selectedCluster} />
          </div>
        )}

        {!selectedCluster && (
          <p className="text-xs text-gray-400 text-center py-4">
            Cliquer sur un cluster dans le scatter plot ou la table pour explorer ses signaux biologiques
          </p>
        )}
      </div>
    </div>
  );
}