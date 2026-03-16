"use client";

import { useState } from "react";
import { X } from "lucide-react";
import { Button } from "@/components/ui/button";
import RatingStars from "./RatingStars";
import QuestionItem from "./QuestionItem";
import { submitFeedback } from "@/lib/api";
import { getSessionId } from "@/lib/session";
import {
  getQuestionsForPage,
  getModalTitle,
  type PageType,
} from "@/lib/feedbackConfig";
import type { FeedbackAnswer } from "@/types";

interface FeedbackModalProps {
  isOpen: boolean;
  onClose: () => void;
  pageType: PageType;
  pageRoute: string;
  contextIds?: {
    jobOfferId?: number;
    companyProfileId?: number;
  };
}

export default function FeedbackModal({
  isOpen,
  onClose,
  pageType,
  pageRoute,
  contextIds,
}: FeedbackModalProps) {
  const [rating, setRating] = useState<number | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const questions = getQuestionsForPage(pageType);
  const title = getModalTitle(pageType);

  const handleSubmit = async () => {
    // Validation : rating obligatoire
    if (rating === null) {
      alert(
        "Votre évaluation globale nous aide à améliorer l'expérience.\nMerci de sélectionner un nombre d'étoiles."
      );
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      const sessionId = getSessionId();

      // Construire les réponses (une par question, même si comment vide)
      const feedbackAnswers: FeedbackAnswer[] = questions.map((q) => ({
        question_key: q.key,
        comment: answers[q.key] || undefined,
      }));

      await submitFeedback({
        session_id: sessionId,
        page_route: pageRoute,
        page_type: pageType,
        rating,
        job_offer_id: contextIds?.jobOfferId,
        company_profile_id: contextIds?.companyProfileId,
        answers: feedbackAnswers,
      });

      // Message de confirmation bienveillant
      alert(
        "Merci pour votre retour précieux !\nIl nous aide à améliorer continuellement cette plateforme."
      );

      // Reset et fermeture
      setRating(null);
      setAnswers({});
      onClose();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Erreur lors de l'envoi du feedback"
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleAnswerChange = (questionKey: string, value: string) => {
    setAnswers((prev) => ({
      ...prev,
      [questionKey]: value,
    }));
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[1000] flex items-center justify-center">
      {/* Overlay */}
      <div
        className="absolute inset-0 bg-black/50"
        onClick={onClose}
      />

      {/* Modale */}
      <div className="relative z-10 bg-white rounded-lg shadow-xl max-w-2xl w-full mx-4 max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b">
          <h2 className="text-xl font-semibold text-gray-900">{title}</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors"
            aria-label="Fermer"
          >
            <X size={24} />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 overflow-y-auto flex-1">
          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 rounded-md text-sm">
              {error}
            </div>
          )}

          {/* Rating */}
          <div className="mb-6">
            <label className="block text-sm font-medium text-gray-700 mb-3">
              Évaluation globale <span className="text-red-500">*</span>
            </label>
            <RatingStars value={rating} onChange={setRating} />
          </div>

          {/* Questions */}
          <div className="space-y-6">
            {questions.map((question) => (
              <QuestionItem
                key={question.key}
                questionText={question.text}
                value={answers[question.key] || ""}
                onChange={(value) => handleAnswerChange(question.key, value)}
              />
            ))}
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 p-6 border-t bg-gray-50">
          <Button
            variant="outline"
            onClick={onClose}
            disabled={isSubmitting}
          >
            Annuler
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={isSubmitting}
          >
            {isSubmitting ? "Envoi..." : "Soumettre"}
          </Button>
        </div>
      </div>
    </div>
  );
}