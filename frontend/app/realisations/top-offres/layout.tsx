import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Top Offres | Réalisations',
  description:
    "Classement quotidien des offres d'emploi selon leur pertinence pour un profil — cibles de postes dérivées du CV, pré-score par embeddings, scoring par LLM local, dbt et BigQuery.",
};

export default function TopOffresLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
