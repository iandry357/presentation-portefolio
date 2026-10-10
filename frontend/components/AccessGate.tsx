'use client';

import type { ReactNode } from 'react';
import { Lock } from 'lucide-react';
import { useAccess } from '@/components/AccessProvider';

interface AccessGateProps {
  children: ReactNode;
  title?: string;
}

export default function AccessGate({ children, title = 'Zone privée' }: AccessGateProps) {
  const { state } = useAccess();

  // Rien n'est monté tant que l'état n'est pas connu : évite des appels API voués au 403
  if (state === 'loading') {
    return <div className="min-h-[50vh]" aria-busy="true" />;
  }

  if (state === 'locked') {
    return (
      <div className="px-4 py-16 text-center">
        <Lock className="w-8 h-8 mx-auto mb-3 text-gray-400" />
        <h1 className="text-lg font-semibold text-gray-900">{title}</h1>
        <p className="mt-1 text-sm text-gray-500">
          Zone privée. Utilisez le bouton « Déverrouiller » en haut de la page.
        </p>
      </div>
    );
  }

  return <>{children}</>;
}
