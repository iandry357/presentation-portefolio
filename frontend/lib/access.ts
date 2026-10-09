// Logique client de l'accès privé.
// Le jeton vit côté serveur (cookie httpOnly) : aucun état d'accès n'est stocké ici.

// ─── Paramètres configurables ────────────────────────────────────────────────
export const POLL_THRESHOLD_SECONDS = 5 * 60; // le polling ne démarre que sous ce seuil
export const POLL_INTERVAL_MS = 60 * 1000;    // intervalle de resynchronisation sous le seuil

// Resynchroniser sur /access/status seulement quand la fin de session approche
export function shouldPoll(remainingSeconds: number | null): boolean {
  return remainingSeconds !== null && remainingSeconds <= POLL_THRESHOLD_SECONDS;
}

// 875 -> "14:35"
export function formatCountdown(totalSeconds: number): string {
  const s = Math.max(0, Math.ceil(totalSeconds));
  const minutes = Math.floor(s / 60);
  const seconds = s % 60;
  return `${minutes}:${String(seconds).padStart(2, '0')}`;
}
