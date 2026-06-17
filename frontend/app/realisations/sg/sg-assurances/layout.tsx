import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'SG Assurances | Réalisations',
  description:
    'POC YOLO + NER + RAG + Qwen QLoRA sur les documents et la veille SG Assurances.',
};

export default function SgAssurancesLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}