import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Fiches entreprises',
  description: 'Fiches de préparation entreprise générées par IA.',
  robots: {
    index: false,
    follow: false,
  },
};

export default function CompaniesLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}