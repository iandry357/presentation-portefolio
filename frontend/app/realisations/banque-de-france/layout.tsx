import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Banque de France | Réalisations',
  description:
    'POC Suptech ACPR — classification multi-label des griefs, RAG, topic modeling et scoring de risque bancaire EBA.',
};

export default function BanqueDeFranceLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}