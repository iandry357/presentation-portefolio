'use client';

import { useEffect, useRef, useState } from 'react';
import { Lock } from 'lucide-react';
import AccessCodeForm from '@/components/AccessCodeForm';

interface AccessUnlockButtonProps {
  // desktop : popover flottant sous le bouton ; mobile : formulaire déplié dans le menu
  variant: 'desktop' | 'mobile';
}

// Bouton « Déverrouiller » + formulaire de code. Rendu seulement quand l'accès est verrouillé :
// au déverrouillage, Header le remplace par « Verrouiller », ce qui ferme le panneau.
export default function AccessUnlockButton({ variant }: AccessUnlockButtonProps) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (e: PointerEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('pointerdown', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('pointerdown', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [open]);

  const isDesktop = variant === 'desktop';

  return (
    <div ref={rootRef} className={isDesktop ? 'relative ml-2' : 'mt-1'}>
      <button
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className={
          isDesktop
            ? 'inline-flex items-center gap-1.5 px-3 py-2 rounded-md text-sm font-medium border border-gray-300 text-gray-700 hover:bg-gray-100 transition-colors'
            : 'flex w-full items-center gap-2 px-4 py-3 rounded-md text-sm font-medium border border-gray-300 text-gray-700 hover:bg-gray-100 transition-colors'
        }
      >
        <Lock className="w-4 h-4" />
        Déverrouiller
      </button>

      {open && (
        <div className={isDesktop ? 'absolute right-0 top-full mt-2 w-80 z-50' : 'mt-2'}>
          <AccessCodeForm
            title="Accès privé"
            description="Saisissez le code pour ouvrir Jobs, Explorer et Companies."
          />
        </div>
      )}
    </div>
  );
}
