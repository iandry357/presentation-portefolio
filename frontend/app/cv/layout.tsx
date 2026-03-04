import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'CV Data Scientist & Data Engineer & ML Engineer',
  description:
    "Parcours, compétences et expériences d'un Data Scientist spécialisé en AI/ML, RAG-LLM et déploiement cloud.",
  openGraph: {
    title: 'CV Data Scientist & Data Engineer & ML Engineer — Iandry RAKOTONIAINA',
    description:
      "Parcours, compétences et expériences d'un Data Scientist spécialisé en AI/ML, RAG-LLM et déploiement cloud.",
    url: 'https://portfoliocvcy2iktuv-portfolio-cv-frontend.functions.fnc.fr-par.scw.cloud/cv',
    type: 'website',
  },
};

export default function CVLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}