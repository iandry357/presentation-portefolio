import type { Metadata } from 'next';
import Link from 'next/link';
import FeedbackWidget from "@/components/feedback/FeedbackWidget";
import { FileText, MessageSquare, Github } from 'lucide-react';

export const metadata: Metadata = {
  title: 'Iandry RAKOTONIAINA — Data Scientist & AI-ML Engineer',
  description:
    "Portefolio de Iandry RAKOTONIAINA, Data Scientist / Data Engineer / AI-ML Engineer, 7 ans d\'expérience en recherche appliquée et consulting industriel.",
  openGraph: {
    title: 'Iandry RAKOTONIAINA — Data Scientist & AI-ML Engineer',
    description:
      "Portefolio de Iandry RAKOTONIAINA, Data Scientist / Data Engineer / AI-ML Engineer, 7 ans d\'expérience en recherche appliquée et consulting industriel.",
    url: 'https://portfoliocvcy2iktuv-portfolio-cv-frontend.functions.fnc.fr-par.scw.cloud',
    type: 'website',
  },
};

export default function HomePage() {
  return (
    <div className="min-h-[calc(100vh-64px)] bg-gradient-to-b from-gray-50 to-white dark:from-gray-900 dark:to-gray-800 flex items-center justify-center px-4">
      <div className="max-w-3xl mx-auto text-center space-y-8">
        {/* Nom */}
        <div>
          <h1 className="text-4xl font-bold text-gray-900 dark:text-white mb-2">
            Iandry RAKOTONIAINA
          </h1>
          <div className="w-48 h-px bg-gray-300 dark:bg-gray-700 mx-auto" />
        </div>

        {/* Pitch principal */}
        <div className="space-y-4">
          <h2 className="text-2xl font-semibold text-gray-900 dark:text-white leading-tight">
            Data Scientist / AI-ML Engineer
          </h2>
          <p className="text-lg text-gray-600 dark:text-gray-400">
            7 ans d'expérience<br />
            Recherche appliquée → Consulting industriel
          </p>
        </div>

        {/* CTA Buttons */}
        <div className="flex flex-col sm:flex-row gap-4 justify-center items-center pt-4">
          <Link
            href="/cv"
            className="inline-flex items-center gap-2 px-6 py-3 border-2 border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg font-medium hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors min-w-[200px] justify-center"
          >
            <FileText className="w-5 h-5" />
            Voir mon CV
          </Link>
          <Link
            href="/chat"
            className="inline-flex items-center gap-2 px-6 py-3 bg-gray-900 dark:bg-white text-white dark:text-gray-900 rounded-lg font-medium hover:bg-gray-800 dark:hover:bg-gray-100 transition-colors min-w-[200px] justify-center"
          >
            <MessageSquare className="w-5 h-5" />
            CV Interactif
          </Link>
        </div>

        {/* LinkedIn */}
        {/* <div className="pt-12 border-t border-gray-200 dark:border-gray-700"> */}
        <div className="pt-12 border-t border-gray-200 dark:border-gray-700 flex flex-col items-center gap-4">
          <a
            href="https://linkedin.com/in/iandry-rakotoniaina"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 transition-colors"
          >
            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
              <path d="M19 0h-14c-2.761 0-5 2.239-5 5v14c0 2.761 2.239 5 5 5h14c2.762 0 5-2.239 5-5v-14c0-2.761-2.238-5-5-5zm-11 19h-3v-11h3v11zm-1.5-12.268c-.966 0-1.75-.79-1.75-1.764s.784-1.764 1.75-1.764 1.75.79 1.75 1.764-.783 1.764-1.75 1.764zm13.5 12.268h-3v-5.604c0-3.368-4-3.113-4 0v5.604h-3v-11h3v1.765c1.396-2.586 7-2.777 7 2.476v6.759z"/>
            </svg>
            linkedin.com/in/iandry-rakotoniaina
          </a>
          <a
            href="https://github.com/iandry357/presentation-portefolio/tree/infra-scaleway-v1.1"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 transition-colors"
          >
            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
              <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
            </svg>
            github.com/iandry357/presentation-portfolio
          </a>
        </div>
      </div>
      <FeedbackWidget 
        pageType="home" 
        pageRoute="/" 
      />
    </div>
  );
}