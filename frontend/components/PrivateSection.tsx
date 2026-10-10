'use client';

import type { ReactNode } from 'react';
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
