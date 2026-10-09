'use client';

import { useRef, useState, type FormEvent } from 'react';
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
