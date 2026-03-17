/**
 * Configuration des questions de feedback par type de page
 */

export interface FeedbackQuestion {
  key: string;
  text: string;
}

export type PageType =
  | "home"
  | "cv"
  | "cv_edit"
  | "jobs_list"
  | "job_detail"
  | "company_detail"
  | "chat";

export const FEEDBACK_QUESTIONS: Record<PageType, FeedbackQuestion[]> = {
  home: [
    {
      key: "presentation_appeal",
      text: "Cette page vous donne-t-elle envie d'en savoir plus ?",
    },
  ],

  cv: [
    {
      key: "cv_clarity",
      text: "La présentation du CV est-elle claire et complète ?",
    },
  ],

  cv_edit: [
    {
      key: "edit_usability",
      text: "L'interface d'édition est-elle intuitive ?",
    },
  ],

  jobs_list: [
    {
      key: "jobs_match",
      text: "Les offres suggérées correspondent-elles au profil ?",
    },
    {
      key: "jobs_presentation",
      text: "La présentation des offres est-elle pertinente ?",
    },
  ],

  job_detail: [
    {
      key: "job_relevance",
      text: "Cette offre vous semble-t-elle pertinente pour le profil ?",
    },
    {
      key: "job_enrichment_quality",
      text: "L'enrichissement de l'offre (analyse, points forts/faibles) est-il utile ?",
    },
    {
      key: "company_info_quality",
      text: "La fiche entreprise apporte-t-elle des informations utiles pour préparer un entretien ?",
    },
  ],

  company_detail: [
    {
      key: "company_usefulness",
      text: "La fiche entreprise aide-t-elle à préparer un entretien ?",
    },
  ],

  chat: [
    {
      key: "chatbot_relevance",
      text: "Le chatbot a-t-il répondu de manière pertinente ?",
    },
  ],
};

/**
 * Récupère les questions pour un type de page donné
 */
export function getQuestionsForPage(pageType: PageType): FeedbackQuestion[] {
  return FEEDBACK_QUESTIONS[pageType] || [];
}

/**
 * Récupère le titre de la modale selon le type de page
 */
export function getModalTitle(pageType: PageType): string {
  const titles: Record<PageType, string> = {
    home: "Votre avis sur cette page d'accueil",
    cv: "Votre avis sur le CV",
    cv_edit: "Votre avis sur l'interface d'édition",
    jobs_list: "Votre avis sur les offres recommandées",
    job_detail: "Votre avis sur cette offre",
    company_detail: "Votre avis sur la fiche entreprise",
    chat: "Votre avis sur le chatbot",
  };

  return titles[pageType] || "Votre avis";
}