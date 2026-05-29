'use client';

import { useState, useRef } from 'react';
import { fetchVitInference, VitInferenceResponse } from '@/lib/savenciaApi';

const RIPENESS_COLORS: Record<string, string> = {
  'Target':    'bg-green-100 text-green-700 border-green-200',
  'NotTarget': 'bg-red-100 text-red-700 border-red-200',
};

const TYPE_COLORS: Record<string, string> = {
  'Semi-Hard':  'bg-blue-100 text-blue-700',
  'Hard':       'bg-purple-100 text-purple-700',
  'Extra-Hard': 'bg-orange-100 text-orange-700',
};

const SAMPLE_IMAGES = [
  { file: 'Extra-Hard_Target.jpg',    label: 'Extra-Hard — Target' },
  { file: 'Extra-Hard_NotTarget.jpg', label: 'Extra-Hard — NotTarget' },
  { file: 'Hard_Target.jpg',          label: 'Hard — Target' },
  { file: 'Hard_NotTarget.jpg',       label: 'Hard — NotTarget' },
  { file: 'Semi-Hard_Target.jpg',     label: 'Semi-Hard — Target' },
  { file: 'Semi-Hard_NotTarget.jpg',  label: 'Semi-Hard — NotTarget' },
];

export default function VitView() {
  const [result, setResult]   = useState<VitInferenceResponse | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const [selectedSample, setSelectedSample] = useState<string | null>(null);

  const handleFile = async (file: File) => {
    if (!file.type.startsWith('image/')) {
      setError('Le fichier doit être une image.');
      return;
    }
    setError(null);
    setResult(null);
    setPreview(URL.createObjectURL(file));
    setLoading(true);
    try {
      const res = await fetchVitInference(file);
      setResult(res);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Erreur inconnue');
    } finally {
      setLoading(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  };

  const handleReset = () => {
    setResult(null);
    setPreview(null);
    setError(null);
    setSelectedSample(null);
    if (inputRef.current) inputRef.current.value = '';
  };

  return (
    <div className="space-y-4">

      {/* Header */}
      <div className="bg-white border rounded-lg p-4">
        <h3 className="font-semibold text-gray-900 mb-1">Détection de maturité fromagère</h3>
        <p className="text-sm text-gray-500">
          Uploadez une photo de meule de fromage — le modèle ViT prédit le type et la maturité (Target / NotTarget) avec une heatmap Grad-CAM.
        </p>
        <p className="text-xs text-gray-400 mt-1">
          Modèle entraîné sur le dataset CR-IDB — Semi-Hard, Hard, Extra-Hard.
        </p>
      </div>

      {/* Exemples pré-chargés — toujours visibles */}
      <div className="bg-white border rounded-lg p-4">
        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">
          Exemples — cliquez pour analyser
        </p>
        <div className="grid grid-cols-3 gap-2">
          {SAMPLE_IMAGES.map(({ file, label }) => (
            <button
              key={file}
              onClick={async () => {
                setSelectedSample(file);
                const res  = await fetch(`/savencia/samples/${file}`);
                const blob = await res.blob();
                handleFile(new File([blob], file, { type: 'image/jpeg' }));
              }}
              // className="border rounded-lg overflow-hidden hover:border-blue-400 transition-colors text-left"
              className={`border-2 rounded-lg overflow-hidden transition-colors text-left ${
                selectedSample === file ? 'border-blue-500' : 'border-transparent hover:border-blue-300'
              }`}
            >
              <img
                src={`/savencia/samples/${file}`}
                alt={label}
                className="w-full h-20 object-cover"
              />
              <p className="text-xs text-gray-500 px-2 py-1 truncate">{label}</p>
            </button>
          ))}
        </div>
      </div>

      {/* Zone upload */}
      {!preview && (
        <div
          onDrop={handleDrop}
          onDragOver={e => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onClick={() => inputRef.current?.click()}
          className={`border-2 border-dashed rounded-lg p-10 text-center cursor-pointer transition-colors ${
            dragOver ? 'border-blue-400 bg-blue-50' : 'border-gray-300 hover:border-blue-300 hover:bg-gray-50'
          }`}
        >
          <p className="text-3xl mb-2">🧀</p>
          <p className="text-sm font-medium text-gray-700">Glissez une image ou cliquez pour choisir</p>
          <p className="text-xs text-gray-400 mt-1">JPG, PNG, WEBP</p>
          <input
            ref={inputRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={e => e.target.files?.[0] && handleFile(e.target.files[0])}
          />
        </div>
      )}

      {/* Preview + résultat */}
      {preview && (
        <div className="space-y-4">

          {/* Images côte à côte */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="border rounded-lg overflow-hidden bg-white">
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide px-3 py-2 border-b">
                Image originale
              </p>
              <img src={preview} alt="Image uploadée" className="w-full object-contain max-h-64" />
            </div>

            <div className="border rounded-lg overflow-hidden bg-white">
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide px-3 py-2 border-b">
                Heatmap Grad-CAM
              </p>
              {loading && (
                <div className="flex items-center justify-center h-64 text-gray-400 animate-pulse">
                  Analyse en cours...
                </div>
              )}
              {result && (
                <img
                  src={`data:image/png;base64,${result.heatmap_base64}`}
                  alt="Heatmap Grad-CAM"
                  className="w-full object-contain max-h-64"
                />
              )}
            </div>
          </div>

          {/* Error */}
          {error && (
            <div className="text-red-500 text-sm p-4 border border-red-200 rounded-lg">{error}</div>
          )}

          {/* Résultat */}
          {result && (
            <div className="border rounded-lg bg-white overflow-hidden">
              <div className="px-4 py-3 border-b">
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Résultat</p>
              </div>
              <div className="p-4 space-y-4">

                {/* Type + Maturité */}
                <div className="flex flex-wrap gap-3 items-center">
                  <span className={`px-3 py-1.5 rounded-full text-sm font-semibold ${TYPE_COLORS[result.cheese_type] ?? 'bg-gray-100 text-gray-700'}`}>
                    🧀 {result.cheese_type}
                  </span>
                  <span className={`px-3 py-1.5 rounded-full text-sm font-semibold border ${RIPENESS_COLORS[result.ripeness] ?? 'bg-gray-100 text-gray-700'}`}>
                    {result.ripeness === 'Target' ? '✅' : '⚠️'} {result.ripeness}
                  </span>
                  <span className="text-sm text-gray-500">
                    Confiance : <strong>{Math.round(result.confidence * 100)}%</strong>
                  </span>
                </div>

                {/* Probabilités toutes classes */}
                <div>
                  <p className="text-xs text-gray-500 mb-2">Probabilités par classe</p>
                  <div className="space-y-1.5">
                    {Object.entries(result.all_probabilities)
                      .sort(([, a], [, b]) => b - a)
                      .map(([cls, prob]) => (
                        <div key={cls} className="flex items-center gap-2">
                          <span className="text-xs text-gray-600 w-40 shrink-0">{cls.replace('_', ' — ')}</span>
                          <div className="flex-1 bg-gray-100 rounded-full h-2">
                            <div
                              className="bg-blue-500 h-2 rounded-full transition-all"
                              style={{ width: `${Math.round(prob * 100)}%` }}
                            />
                          </div>
                          <span className="text-xs text-gray-500 w-10 text-right">{Math.round(prob * 100)}%</span>
                        </div>
                      ))}
                  </div>
                </div>

                {/* Version modèle */}
                <p className="text-xs text-gray-400">
                  Modèle version : {result.model_version}
                </p>
              </div>
            </div>
          )}

          {/* Reset */}
          <button
            onClick={handleReset}
            className="text-xs text-gray-400 hover:text-gray-600 transition-colors"
          >
            ← Analyser une autre image
          </button>
        </div>
      )}
    </div>
  );
}