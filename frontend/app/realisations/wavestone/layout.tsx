import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Wavestone | Réalisations',
  description:
    'POC veille entreprise : publications, cas clients et presse sur Wavestone (FR/EN), Ask AI, thèmes LDA et postes ouverts.',
  robots: { index: false, follow: false },
};

export default function WavestoneLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
