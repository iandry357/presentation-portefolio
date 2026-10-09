'use client';

import type { ReactNode } from 'react';
import AccessCodeForm from '@/components/AccessCodeForm';
import { useAccess } from '@/components/AccessProvider';

interface AccessGateProps {
  children: ReactNode;
  title?: string;
  description?: string;
}

export default function AccessGate({ children, title, description }: AccessGateProps) {
  const { state } = useAccess();

  // Rien n'est monté tant que l'état n'est pas connu : évite des appels API voués au 403
  if (state === 'loading') {
    return <div className="min-h-[50vh]" aria-busy="true" />;
  }

  if (state === 'locked') {
    return (
      <div className="px-4 py-16">
        <AccessCodeForm title={title} description={description} />
      </div>
    );
  }

  return <>{children}</>;
}
