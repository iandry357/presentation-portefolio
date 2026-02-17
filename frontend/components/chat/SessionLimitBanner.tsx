
'use client';

import { AlertCircle } from 'lucide-react';

interface SessionLimitBannerProps {
  remainingTime: string;
}

export default function SessionLimitBanner({
  remainingTime,
}: SessionLimitBannerProps) {
  return (
    <div className="bg-amber-50 border-l-4 border-amber-400 p-4 mb-4">
      <div className="flex items-start gap-3">
        <AlertCircle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
        <div>
          <h3 className="text-sm font-semibold text-amber-900">
            Limite de questions atteinte
          </h3>
          <p className="text-sm text-amber-700 mt-1">
            Vous avez posé 5 questions. Nouvelle session disponible dans{' '}
            <span className="font-semibold">{remainingTime}</span>.
          </p>
          <p className="text-xs text-amber-600 mt-2">
            Pour des échanges plus approfondis, contactez-moi directement à{' '}
            <a
              href="mailto:iandry.rakoto7@gmail.com"
              className="underline font-medium"
            >
              iandry.rakoto7@gmail.com
            </a>
          </p>
        </div>
      </div>
    </div>
  );
}