'use client';

import { useState } from 'react';
import { genererProfil, Profil, THEMATIQUES } from '@/lib/gestionPatrimoineApi';

interface Props {
  onProfilGenerated: (sessionId: string, profil: Profil) => void;
}

export default function ProfilGenerator({ onProfilGenerated }: Props) {
  const [thematique, setThematique] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleGenerate = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await genererProfil(thematique || undefined);
      onProfilGenerated(res.session_id, res.profil);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Erreur inconnue');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="border rounded-lg p-6 bg-white max-w-xl">
      <h2 className="text-lg font-semibold text-gray-900 mb-1">Générer un profil client</h2>
      <p className="text-sm text-gray-500 mb-4">
        Profil client fictif RGPD-safe, généré pour illustrer le copilote patrimonial.
      </p>

      <label className="block text-xs font-medium text-gray-600 mb-1">
        Thématique (optionnel — tirage aléatoire sinon)
      </label>
      <select
        value={thematique}
        onChange={e => setThematique(e.target.value)}
        className="w-full border rounded-lg px-3 py-2 text-sm mb-4 focus:outline-none focus:ring-2 focus:ring-emerald-300"
      >
        <option value="">Aléatoire</option>
        {THEMATIQUES.map(t => (
          <option key={t.value} value={t.value}>{t.label}</option>
        ))}
      </select>

      <button
        onClick={handleGenerate}
        disabled={loading}
        className="px-4 py-2 bg-emerald-600 text-white rounded-lg text-sm font-medium hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        {loading ? 'Génération...' : 'Générer un profil'}
      </button>

      {error && (
        <div className="text-red-500 text-sm mt-4 p-3 border border-red-200 rounded-lg">{error}</div>
      )}
    </div>
  );
}