'use client';

import Link from 'next/link';
import { Badge } from '@/components/ui/badge';

interface PocCard {
  href: string;
  title: string;
  company: string;
  description: string;
  tags: string[];
  status: 'live' | 'wip';
}

const POCS: PocCard[] = [
  {
    href: '/realisations/sanofi',
    title: 'Sanofi Dashboard',
    company: 'Sanofi',
    description:
      "Pipeline RAG multi-source + Therapeutic Insight — clustering thérapeutique OpenTargets, profils Mature/Émergent/Actif/Exploratoire, Graph RAG Neo4j + Mistral 7B fine-tuné drug discovery (win-rate 46.7%). Essais cliniques, PubMed, Google News. VoyageAI, ChromaDB, BigQuery.",
    tags: ['RAG', 'Graph RAG', 'Neo4j', 'Fine-tuning', 'QLoRA', 'ChromaDB', 'VoyageAI', 'BigQuery', 'ETL', 'LLM'],
    status: 'live',
  },
  {
    href: '/realisations/savencia',
    title: 'Savencia Dashboard',
    company: 'Savencia / Soredab',
    description:
      "Veille stratégique agroalimentaire avec topic modeling LDA et détection de maturité fromagère par Computer Vision (ViT fine-tuné + Grad-CAM) sur le dataset CR-IDB.",
    tags: ['RAG', 'Topic Modeling', 'ViT', 'Grad-CAM', 'ChromaDB', 'BigQuery'],
    status: 'live',
  },
  {
    href: '/realisations/sg/sg-assurances',
    title: 'SG Assurances',
    company: 'Société Générale Assurances',
    description:
      "Veille assurance et analyse de documents contractuels — détection de zones YOLO, extraction d'entités NER, RAG sur actualités et modèle Qwen2.5 fine-tuné QLoRA sur corpus SG.",
    tags: ['YOLO', 'NER', 'RAG', 'QLoRA', 'ChromaDB', 'BigQuery', 'Vertex AI'],
    status: 'live',
  },
  {
    href: '/realisations/banque-de-france',
    title: 'Banque de France',
    company: 'Banque de France / ACPR',
    description:
      "POC Suptech — classification multi-label des griefs de sanction ACPR (CamemBERT fine-tuné + têtes k-NN), RAG sur la veille réglementaire, topic modeling LDA et scoring composite de risque bancaire à partir des données EBA Transparency Exercise.",
    tags: ['Classification', 'RAG', 'Topic Modeling', 'k-NN', 'ChromaDB', 'BigQuery', 'Vertex AI'],
    status: 'live',
  },
  {
    href: '/realisations/gestion-patrimoine',
    title: 'Gestion Patrimoine',
    company: 'Copilote patrimonial',
    description:
      "Copilote d'ingénierie patrimoniale — génération de profils clients synthétiques RGPD-safe (Mistral, fallback Gemini) et assistant RAG juridique groundé sur le Code Général des Impôts (function calling ReAct, Qwen2.5-Instruct local OVH), citation d'article obligatoire.",
    tags: ['RAG', 'Function Calling', 'ChromaDB', 'LiteLLM', 'Pydantic', 'llama.cpp', 'PostgreSQL'],
    status: 'wip',
  },
];



export default function RealisationsPage() {
  return (
    <div className="container mx-auto px-4 py-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900 mb-2">Réalisations</h1>
        <p className="text-gray-600">
          POCs et projets techniques démontrant des compétences Data & AI Engineering en conditions réelles.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {POCS.map((poc) => (
          <Link key={poc.href} href={poc.href}>
            <div className="border rounded-lg p-6 bg-white hover:shadow-md transition-shadow cursor-pointer h-full flex flex-col">
              {/* Header */}
              <div className="flex items-start justify-between mb-3">
                <div>
                  <p className="text-xs text-gray-500 font-medium uppercase tracking-wide mb-1">
                    {poc.company}
                  </p>
                  <h2 className="text-lg font-semibold text-gray-900">{poc.title}</h2>
                </div>
                <Badge
                  variant={poc.status === 'live' ? 'default' : 'secondary'}
                  className="ml-2 shrink-0"
                >
                  {poc.status === 'live' ? 'Live' : 'En cours'}
                </Badge>
              </div>

              {/* Description */}
              <p className="text-sm text-gray-600 mb-4 flex-1">{poc.description}</p>

              {/* Tags */}
              <div className="flex flex-wrap gap-1">
                {poc.tags.map((tag) => (
                  <Badge key={tag} variant="outline" className="text-xs">
                    {tag}
                  </Badge>
                ))}
              </div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}