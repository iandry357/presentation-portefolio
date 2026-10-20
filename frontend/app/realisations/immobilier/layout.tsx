import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Immobilier | Réalisations',
  description:
    "Veille immobilière sur Paris : parc des DPE (ADEME), DPE refaits et prix de vente au m² (DVF). Données ouvertes, pipeline Python, BigQuery et FastAPI.",
};

export default function ImmobilierLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
