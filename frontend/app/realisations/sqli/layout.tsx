import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'SQLI | Réalisations',
  description:
    'POC veille Google News + RAG + Topic Modeling LDA sur les actualités SQLI.',
  robots: { index: false, follow: false },
};

export default function SqliLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
