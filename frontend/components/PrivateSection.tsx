'use client';

import type { ReactNode } from 'react';
import { useAccess } from '@/components/AccessProvider';

// N'affiche (et ne monte) son contenu que si l'accès privé est déverrouillé.
// Masquage d'affichage seulement : la protection des données reste côté backend.
export default function PrivateSection({ children }: { children: ReactNode }) {
  const { unlocked } = useAccess();
  return unlocked ? <>{children}</> : null;
}
