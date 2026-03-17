"use client";

import { useState } from "react";
import { MessageCircle } from "lucide-react";
import FeedbackModal from "./FeedbackModal";
import type { PageType } from "@/lib/feedbackConfig";

interface FeedbackWidgetProps {
  pageType: PageType;
  pageRoute: string;
  contextIds?: {
    jobOfferId?: number;
    companyProfileId?: number;
  };
}

export default function FeedbackWidget({
  pageType,
  pageRoute,
  contextIds,
}: FeedbackWidgetProps) {
  const [isModalOpen, setIsModalOpen] = useState(false);

  return (
    <>
      {/* Widget fixe côté gauche */}
      <button
        onClick={() => setIsModalOpen(true)}
        className="fixed left-0 top-1/2 -translate-y-1/2 z-[999] bg-blue-600 hover:bg-blue-700 text-white px-3 py-4 rounded-r-lg shadow-lg transition-all duration-200 hover:px-4 group"
        aria-label="Donner votre avis"
      >
        <div className="flex flex-col items-center gap-2">
          <MessageCircle size={24} className="group-hover:scale-110 transition-transform" />
          <span className="text-xs font-medium" style={{ writingMode: 'vertical-rl' }}>
            Feedback
          </span>
        </div>
      </button>

      {/* Modale */}
      <FeedbackModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        pageType={pageType}
        pageRoute={pageRoute}
        contextIds={contextIds}
      />
    </>
  );
}