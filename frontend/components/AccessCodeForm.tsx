'use client';

import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Lock } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { useAccess } from '@/components/AccessProvider';
import { formatRemainingTime } from '@/lib/session';

interface AccessCodeFormProps {
  title?: string;
  description?: string;
}

export default function AccessCodeForm({
  title = 'Accès privé',
  description = 'Saisissez le code pour accéder à cette zone.',
}: AccessCodeFormProps) {
  const { unlock } = useAccess();
  const [code, setCode] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!code || submitting) return;

    setSubmitting(true);
    setError(null);

    try {
      const result = await unlock(code);

      if (result.ok) {
        setCode(''); // AccessGate bascule sur le contenu : le formulaire disparaît
        return;
      }

      if (result.reason === 'invalid') {
        setError('Code incorrect.');
      } else if (result.reason === 'blocked') {
        setError(
          result.retryAfterSeconds
            ? `Trop de tentatives. Réessayez dans ${formatRemainingTime(result.retryAfterSeconds * 1000)}.`
            : result.message
        );
      } else {
        setError('Erreur de connexion. Réessayez dans un instant.');
      }
    } catch {
      setError('Erreur de connexion. Réessayez dans un instant.');
    } finally {
      setSubmitting(false);
    }

    setCode('');
    inputRef.current?.focus();
  }

  return (
    <Card className="w-full max-w-sm mx-auto">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Lock className="w-5 h-5" />
          {title}
        </CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <Input
            ref={inputRef}
            type="password"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            placeholder="Code d'accès"
            aria-label="Code d'accès"
            aria-invalid={error !== null}
            autoComplete="off"
          />
          {error && (
            <p role="alert" className="text-sm text-red-600">
              {error}
            </p>
          )}
          <Button type="submit" className="w-full" disabled={!code || submitting}>
            {submitting ? 'Vérification…' : 'Déverrouiller'}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

interface AccessUnlockButtonProps {
  // desktop : popover flottant sous le bouton ; mobile : formulaire déplié dans le menu
  variant: 'desktop' | 'mobile';
}

// Bouton « Déverrouiller » + formulaire de code. Rendu seulement quand l'accès est verrouillé :
// au déverrouillage, Header le remplace par « Verrouiller », ce qui ferme le panneau.
export function AccessUnlockButton({ variant }: AccessUnlockButtonProps) {
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
