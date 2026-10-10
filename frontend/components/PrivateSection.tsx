'use client';

import type { ReactNode } from 'react';
import { Lock } from 'lucide-react';
import AccessCodeForm from '@/components/AccessCodeForm';
import { useAccess } from '@/components/AccessProvider';

interface PrivateSectionProps {
  children: ReactNode;
  // Pour une saisie en cours (modale) : le contenu reste monté et, si l'accès est
  // perdu, un popup de code se superpose pour pouvoir continuer sans perdre la saisie.
  // À n'utiliser que pour un contenu déjà ouvert en mode déverrouillé.
  reauth?: boolean;
}

// Par défaut : n'affiche (et ne monte) son contenu que si l'accès privé est déverrouillé.
// Masquage d'affichage seulement : la protection des données reste côté backend.
export default function PrivateSection({ children, reauth = false }: PrivateSectionProps) {
  const { state, unlocked } = useAccess();

  if (!reauth) return unlocked ? <>{children}</> : null;

  return (
    <>
      {children}
      {state === 'locked' && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 px-4">
          <AccessCodeForm
            title="Session expirée"
            description="Saisissez le code pour continuer. Votre saisie est conservée."
          />
        </div>
      )}
    </>
  );
}

interface AccessGateProps {
  children: ReactNode;
  title?: string;
}

// Garde de page (Explorer, Companies) : monte la page seulement si l'accès est déverrouillé.
export function AccessGate({ children, title = 'Zone privée' }: AccessGateProps) {
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
