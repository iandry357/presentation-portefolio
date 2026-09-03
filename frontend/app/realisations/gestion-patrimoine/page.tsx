'use client';

import { useState } from 'react';
import Link from 'next/link';
import ProfilGenerator from '@/components/gestion-patrimoine/ProfilGenerator';
import ChatAssistant from '@/components/gestion-patrimoine/ChatAssistant';
import { Profil } from '@/lib/gestionPatrimoineApi';

export default function GestionPatrimoinePage() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [profil, setProfil] = useState<Profil | null>(null);

  return (
    <div className="container mx-auto px-4 py-8 overflow-hidden">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-gray-500 mb-6">
        <Link href="/realisations" className="hover:text-gray-700 transition-colors">
          Réalisations
        </Link>
        <span>/</span>
        <span className="text-gray-900 font-medium">Gestion Patrimoine</span>
      </div>

      {/* Titre */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 mb-1">Gestion Patrimoine</h1>
        <p className="text-sm text-gray-500">
          Copilote d&apos;ingénierie patrimoniale · RAG juridique CGI · Qwen2.5-Instruct (OVH)
        </p>
      </div>

      {/* Flux séquentiel : ProfilGenerator d'abord, ChatAssistant une fois le profil généré */}
      {!profil || !sessionId ? (
        <ProfilGenerator
          onProfilGenerated={(newSessionId, newProfil) => {
            setSessionId(newSessionId);
            setProfil(newProfil);
          }}
        />
      ) : (
        <ChatAssistant sessionId={sessionId} profil={profil} />
      )}
    </div>
  );
}