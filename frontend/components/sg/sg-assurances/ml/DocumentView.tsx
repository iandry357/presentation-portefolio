'use client';

import { useState, useRef } from 'react';
import { fetchSgYolo, fetchSgNer, YoloDetection, NerEntity } from '@/lib/sgApi';

// ─── Couleurs par classe YOLO ───────────────────────────────────
const YOLO_COLORS: Record<string, string> = {
  amount_block:   '#3b82f6', // blue
  date_block:     '#10b981', // green
  name_block:     '#f59e0b', // amber
  address_block:  '#8b5cf6', // purple
};

// ─── Couleurs par entité NER ────────────────────────────────────
const NER_COLORS: Record<string, string> = {
  MONTANT:        'bg-blue-100 text-blue-700 border-blue-200',
  DATE:           'bg-green-100 text-green-700 border-green-200',
  NOM_ASSURE:     'bg-amber-100 text-amber-700 border-amber-200',
  ADRESSE:        'bg-purple-100 text-purple-700 border-purple-200',
  NUMERO_POLICE:  'bg-red-100 text-red-700 border-red-200',
};

// ─── Exemples pré-chargés (placeholders — PNGs à ajouter) ──────
const SAMPLE_DOCS = [
  { file: 'mma_auto.png',       label: 'CG Auto — MMA' },
  { file: 'mma_habitation.png', label: 'CG Habitation — MMA' },
  { file: 'axa_auto.png',       label: 'CG Auto — AXA' },
  { file: 'ccf_habitation.png', label: 'CG Habitation — CCF' },
];

interface YoloOverlayProps {
  src: string;
  detections: YoloDetection[];
  imgW: number;
  imgH: number;
}

function YoloOverlay({ src, detections, imgW, imgH }: YoloOverlayProps) {
  return (
    <div className="relative inline-block w-full">
      <img src={src} alt="Document" className="w-full object-contain rounded" />
      <svg
        className="absolute inset-0 w-full h-full"
        viewBox={`0 0 ${imgW} ${imgH}`}
        preserveAspectRatio="none"
      >
        {detections.map((d, i) => (
          <g key={i}>
            <rect
              x={d.x1} y={d.y1}
              width={d.x2 - d.x1} height={d.y2 - d.y1}
              fill="none"
              stroke={YOLO_COLORS[d.class_name] ?? '#6b7280'}
              strokeWidth="6"
            />
            <rect
              x={d.x1} y={d.y1 - 22}
              width={(d.class_name.length * 8) + 16} height="22"
              fill={YOLO_COLORS[d.class_name] ?? '#6b7280'}
              rx="3"
            />
            <text
              x={d.x1 + 8} y={d.y1 - 6}
              fill="white"
              fontSize="14"
              fontWeight="bold"
            >
              {d.class_name} {Math.round(d.score * 100)}%
            </text>
          </g>
        ))}
      </svg>
    </div>
  );
}

function NerHighlight({ text, entities }: { text: string; entities: NerEntity[] }) {
  if (!entities.length) return <p className="text-sm text-gray-700 whitespace-pre-wrap">{text}</p>;

  const sorted = [...entities].sort((a, b) => a.start - b.start);
  const parts: React.ReactNode[] = [];
  let cursor = 0;

  sorted.forEach((e, i) => {
    if (e.start > cursor) parts.push(<span key={`t${i}`}>{text.slice(cursor, e.start)}</span>);
    parts.push(
      <span
        key={`e${i}`}
        className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded border text-xs font-medium mx-0.5 ${NER_COLORS[e.label] ?? 'bg-gray-100 text-gray-700'}`}
        title={`${e.label} — ${Math.round(e.score * 100)}%`}
      >
        {e.text}
        <span className="opacity-60 text-[10px]">{e.label}</span>
      </span>
    );
    cursor = e.end;
  });

  if (cursor < text.length) parts.push(<span key="tail">{text.slice(cursor)}</span>);
  return <p className="text-sm text-gray-700 leading-7 whitespace-pre-wrap">{parts}</p>;
}

export default function DocumentView() {
  const [preview, setPreview]         = useState<string | null>(null);
  const [imgDims, setImgDims]         = useState<{ w: number; h: number } | null>(null);
  const [extractedText, setExtractedText] = useState<string>('');
  const [detections, setDetections]   = useState<YoloDetection[]>([]);
  const [entities, setEntities]       = useState<NerEntity[]>([]);
  const [loading, setLoading]         = useState(false);
  const [error, setError]             = useState<string | null>(null);
  const [selectedSample, setSelectedSample] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver]       = useState(false);

  const runAnalysis = async (file: File, previewUrl: string) => {
    setLoading(true);
    setError(null);
    setDetections([]);
    setEntities([]);

    // Dimensions image pour le SVG overlay
    const img = new Image();
    img.src = previewUrl;
    await new Promise(r => { img.onload = r; });
    setImgDims({ w: img.naturalWidth, h: img.naturalHeight });

    try {
      const [yoloRes, nerRes] = await Promise.all([
        fetchSgYolo(file),
        fetchSgNer(extractedText || file.name),
      ]);
      setDetections(yoloRes.detections);
      setEntities(nerRes.entities);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Erreur inconnue');
    } finally {
      setLoading(false);
    }
  };

  const handleFile = async (file: File) => {
    if (!file.type.startsWith('image/')) {
      setError('Veuillez uploader une image (PNG, JPG).');
      return;
    }
    const url = URL.createObjectURL(file);
    setPreview(url);
    await runAnalysis(file, url);
  };

  const handleSample = async (filename: string) => {
    setSelectedSample(filename);
    const res  = await fetch(`/sg-assurances/samples/${filename}`);
    const blob = await res.blob();
    const file = new File([blob], filename, { type: 'image/png' });
    const url  = URL.createObjectURL(blob);
    setPreview(url);
    await runAnalysis(file, url);
  };

  const handleReset = () => {
    setPreview(null);
    setImgDims(null);
    setDetections([]);
    setEntities([]);
    setError(null);
    setSelectedSample(null);
    setExtractedText('');
    if (inputRef.current) inputRef.current.value = '';
  };

  return (
    <div className="space-y-4">

      {/* Header */}
      <div className="bg-white border rounded-lg p-4">
        <h3 className="font-semibold text-gray-900 mb-1">Analyse de documents — YOLO + NER</h3>
        <p className="text-sm text-gray-500">
          Uploadez une image de document d'assurance. Le modèle détecte les zones (YOLO) et extrait les entités nommées (NER).
        </p>
      </div>

      {/* Exemples pré-chargés */}
      <div className="bg-white border rounded-lg p-4">
        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">
          Exemples — cliquez pour analyser
        </p>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          {SAMPLE_DOCS.map(({ file, label }) => (
            <button
              key={file}
              onClick={() => handleSample(file)}
              className={`border-2 rounded-lg overflow-hidden transition-colors text-left ${
                selectedSample === file ? 'border-blue-500' : 'border-transparent hover:border-blue-300'
              }`}
            >
              <img
                src={`/sg-assurances/samples/${file}`}
                alt={label}
                className="w-full h-24 object-cover bg-gray-100"
              />
              <p className="text-xs text-gray-500 px-2 py-1 truncate">{label}</p>
            </button>
          ))}
        </div>
      </div>

      {/* Zone upload */}
      {!preview && (
        <div
          onDrop={e => { e.preventDefault(); setDragOver(false); const f = e.dataTransfer.files[0]; if (f) handleFile(f); }}
          onDragOver={e => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onClick={() => inputRef.current?.click()}
          className={`border-2 border-dashed rounded-lg p-10 text-center cursor-pointer transition-colors ${
            dragOver ? 'border-blue-400 bg-blue-50' : 'border-gray-300 hover:border-blue-300 hover:bg-gray-50'
          }`}
        >
          <p className="text-3xl mb-2">📄</p>
          <p className="text-sm font-medium text-gray-700">Glissez une image ou cliquez pour choisir</p>
          <p className="text-xs text-gray-400 mt-1">PNG, JPG — page de document d'assurance</p>
          <input
            ref={inputRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={e => e.target.files?.[0] && handleFile(e.target.files[0])}
          />
        </div>
      )}

      {/* Résultats */}
      {preview && (
        <div className="space-y-4">

          {/* YOLO — image avec overlay */}
          <div className="border rounded-lg overflow-hidden bg-white">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide px-3 py-2 border-b">
              Détection zones — YOLO {detections.length > 0 && `(${detections.length} zones)`}
            </p>
            <div className="p-3">
              {loading && <div className="flex items-center justify-center h-48 text-gray-400 animate-pulse">Analyse en cours...</div>}
              {!loading && imgDims && (
                <YoloOverlay src={preview} detections={detections} imgW={imgDims.w} imgH={imgDims.h} />
              )}
            </div>
          </div>

          {/* Légende YOLO */}
          {detections.length > 0 && (
            <div className="border rounded-lg bg-white p-3">
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Légende</p>
              <div className="flex flex-wrap gap-2">
                {[...new Set(detections.map(d => d.class_name))].map(cls => (
                  <span key={cls} className="flex items-center gap-1.5 text-xs text-gray-600">
                    <span className="w-3 h-3 rounded-sm inline-block" style={{ background: YOLO_COLORS[cls] ?? '#6b7280' }} />
                    {cls}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* NER — texte avec entités surlignées */}
          <div className="border rounded-lg bg-white overflow-hidden">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide px-3 py-2 border-b">
              Extraction entités — NER {entities.length > 0 && `(${entities.length} entités)`}
            </p>
            <div className="p-4">
              {loading && <div className="h-4 bg-gray-200 rounded animate-pulse w-2/3" />}
              {!loading && entities.length === 0 && (
                <div className="space-y-2">
                  <p className="text-xs text-gray-400 mb-2">Collez ou tapez le texte du document pour l'analyse NER :</p>
                  <textarea
                    rows={4}
                    value={extractedText}
                    onChange={e => setExtractedText(e.target.value)}
                    placeholder="Ex: M. Dupont Jean, police n° 123456, montant 5 000 €, date d'effet 01/01/2024..."
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300 resize-none"
                  />
                  <button
                    onClick={async () => {
                      if (!extractedText.trim()) return;
                      setLoading(true);
                      try {
                        const res = await fetchSgNer(extractedText);
                        setEntities(res.entities);
                      } catch (e: unknown) {
                        setError(e instanceof Error ? e.message : 'Erreur NER');
                      } finally {
                        setLoading(false);
                      }
                    }}
                    disabled={!extractedText.trim()}
                    className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
                  >
                    Analyser le texte
                  </button>
                </div>
              )}
              {!loading && entities.length > 0 && (
                <NerHighlight text={extractedText} entities={entities} />
              )}
            </div>
          </div>

          {/* Error */}
          {error && <div className="text-red-500 text-sm p-4 border border-red-200 rounded-lg">{error}</div>}

          {/* Reset */}
          <button onClick={handleReset} className="text-xs text-gray-400 hover:text-gray-600 transition-colors">
            ← Analyser un autre document
          </button>
        </div>
      )}
    </div>
  );
}