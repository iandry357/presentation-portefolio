// Logique client de l'accès privé.
// Le jeton vit côté serveur (cookie httpOnly) : aucun état d'accès n'est stocké ici.

// ─── Paramètres configurables ────────────────────────────────────────────────
export const POLL_THRESHOLD_SECONDS = 5 * 60; // le polling ne démarre que sous ce seuil
export const POLL_INTERVAL_MS = 60 * 1000;    // intervalle de resynchronisation sous le seuil

// Resynchroniser sur /access/status seulement quand la fin de session approche
export function shouldPoll(remainingSeconds: number | null): boolean {
  return remainingSeconds !== null && remainingSeconds <= POLL_THRESHOLD_SECONDS;
}
