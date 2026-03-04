import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'CV Interactif',
  description:
    "Explorez le profil de ce Data Scientist & AI Engineer via un chatbot RAG — posez vos questions directement.",
  openGraph: {
    title: 'CV Interactif — Iandry RAKOTONIAINA',
    description:
      "Explorez le profil de ce Data Scientist & Data Engineer & AI Engineer via un chatbot RAG — posez vos questions directement.",
    url: 'https://portfoliocvcy2iktuv-portfolio-cv-frontend.functions.fnc.fr-par.scw.cloud/chat',
    type: 'website',
  },
};

export default function ChatLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}