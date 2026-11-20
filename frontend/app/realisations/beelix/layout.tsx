import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Beelix | Réalisations',
  description:
    'POC signaux de prospection : offres data/IA en Île-de-France par secteur, concurrence et RAG.',
  robots: { index: false, follow: false },
};

export default function BeelixLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
