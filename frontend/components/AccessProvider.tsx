'use client';

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react';
import { getAccessStatus, lockAccess, setForbiddenHandler, unlockAccess } from '@/lib/api';
import { POLL_INTERVAL_MS, POLL_THRESHOLD_SECONDS, shouldPoll } from '@/lib/access';
import type { AccessStatus, UnlockResult } from '@/types';

type AccessState = 'loading' | 'locked' | 'unlocked';

interface AccessContextValue {
  state: AccessState;
  unlocked: boolean;
  unlock: (code: string) => Promise<UnlockResult>;
  lock: () => Promise<void>;
  refresh: () => Promise<void>;
}

const AccessContext = createContext<AccessContextValue | null>(null);

export default function AccessProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AccessState>('loading');
  // Instant d'expiration estimé (ms), aligné sur le serveur à chaque réponse
  const [expiresAt, setExpiresAt] = useState<number | null>(null);

  const applyStatus = useCallback((status: AccessStatus) => {
    if (status.unlocked && status.expires_in_seconds !== null) {
      setState('unlocked');
      setExpiresAt(Date.now() + status.expires_in_seconds * 1000);
    } else {
      setState('locked');
      setExpiresAt(null);
    }
  }, []);

  // Lecture seule côté serveur. En cas d'échec réseau : on garde l'état courant,
  // sauf au tout premier appel où le privé reste masqué par sécurité.
  const refresh = useCallback(async () => {
    try {
      applyStatus(await getAccessStatus());
    } catch {
      setState((prev) => (prev === 'loading' ? 'locked' : prev));
    }
  }, [applyStatus]);

  const unlock = useCallback(
    async (code: string) => {
      const result = await unlockAccess(code);
      if (result.ok) applyStatus(result.status);
      return result;
    },
    [applyStatus]
  );

  const lock = useCallback(async () => {
    try {
      await lockAccess();
      applyStatus({ unlocked: false, expires_in_seconds: null });
    } catch {
      await refresh(); // l'état affiché doit refléter le serveur
    }
  }, [applyStatus, refresh]);

  // Au chargement
  useEffect(() => {
    refresh();
  }, [refresh]);

  // Tout 403 d'un appel API resynchronise l'état d'accès (accès perdu → verrouillé)
  useEffect(() => {
    setForbiddenHandler(refresh);
    return () => setForbiddenHandler(null);
  }, [refresh]);

  // Au retour sur l'onglet
  useEffect(() => {
    const onVisible = () => {
      if (document.visibilityState === 'visible') refresh();
    };
    document.addEventListener('visibilitychange', onVisible);
    return () => document.removeEventListener('visibilitychange', onVisible);
  }, [refresh]);

  // Prochaine resynchronisation : à (fin - seuil), puis toutes les POLL_INTERVAL_MS,
  // et une dernière fois à l'expiration. Pas de tick : un seul minuteur à la fois.
  useEffect(() => {
    if (expiresAt === null) return;

    const remaining = (expiresAt - Date.now()) / 1000;
    const delayMs = shouldPoll(remaining)
      ? Math.min(POLL_INTERVAL_MS, remaining * 1000)
      : (remaining - POLL_THRESHOLD_SECONDS) * 1000;

    const timer = setTimeout(() => {
      if (document.visibilityState === 'visible') refresh();
    }, Math.max(delayMs, 1000));

    return () => clearTimeout(timer);
  }, [expiresAt, refresh]);

  return (
    <AccessContext.Provider
      value={{ state, unlocked: state === 'unlocked', unlock, lock, refresh }}
    >
      {children}
    </AccessContext.Provider>
  );
}

export function useAccess(): AccessContextValue {
  const ctx = useContext(AccessContext);
  if (!ctx) throw new Error('useAccess doit être utilisé dans un AccessProvider');
  return ctx;
}
