import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Offres d\'emploi suivies',
  description: 'Pipeline de matching et suivi d\'offres d\'emploi personnalisé.',
  robots: {
    index: false,
    follow: false,
  },
};

export default function JobsLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}