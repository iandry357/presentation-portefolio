import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Sanofi Investigation | Réalisations',
  description:
    'POC RAG multi-source sur les données publiques Sanofi — essais cliniques, publications R&D, actualités.',
};

export default function SanofiLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}