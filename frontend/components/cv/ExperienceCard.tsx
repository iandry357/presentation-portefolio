"use client";

import { ExperienceListItem } from "@/types";
import { format } from "date-fns";
import { fr } from "date-fns/locale";
import { Briefcase, MapPin, Calendar, Loader2, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";

interface ExperienceCardProps {
  experience: ExperienceListItem;
  onEdit: (id: number) => void;
  onDelete: (id: number) => void;
  onRetry?: (id: number) => void;
}

export default function ExperienceCard({
  experience,
  onEdit,
  onDelete,
  onRetry,
}: ExperienceCardProps) {
  const formatDate = (dateString: string) => {
    return format(new Date(dateString), "MMM yyyy", { locale: fr });
  };

  const getDuration = () => {
    const start = new Date(experience.start_date);
    const end = experience.end_date ? new Date(experience.end_date) : new Date();
    const months = Math.round(
      (end.getTime() - start.getTime()) / (1000 * 60 * 60 * 24 * 30)
    );
    const years = Math.floor(months / 12);
    const remainingMonths = months % 12;

    if (years > 0 && remainingMonths > 0) {
      return `${years} an${years > 1 ? "s" : ""} ${remainingMonths} mois`;
    } else if (years > 0) {
      return `${years} an${years > 1 ? "s" : ""}`;
    } else {
      return `${remainingMonths} mois`;
    }
  };

  const renderStatusBadge = () => {
    if (experience.embedding_status === "pending") {
      return (
        <div className="flex items-center gap-2 px-3 py-1 bg-blue-50 text-blue-700 rounded-full text-sm">
          <Loader2 className="w-3 h-3 animate-spin" />
          <span>Embeddings en cours...</span>
        </div>
      );
    }

    if (experience.embedding_status === "failed") {
      return (
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-2 px-3 py-1 bg-red-50 text-red-700 rounded-full text-sm">
            <AlertCircle className="w-3 h-3" />
            <span>Erreur embeddings</span>
          </div>
          {onRetry && (
            <Button
              variant="outline"
              size="sm"
              onClick={(e) => {
                e.stopPropagation();
                onRetry(experience.id);
              }}
              className="text-xs"
            >
              Réessayer
            </Button>
          )}
        </div>
      );
    }

    return null;
  };

  return (
    <div className="border rounded-lg p-6 hover:shadow-md transition-shadow bg-white">
      {/* Header avec statut */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-2">
            <h3 className="text-xl font-semibold text-gray-900">
              {experience.role}
            </h3>
            {experience.is_stage && (
              <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded text-xs font-medium">
                Stage
              </span>
            )}
          </div>
          <div className="flex items-center gap-2 text-gray-600 mb-2">
            <Briefcase className="w-4 h-4" />
            <span className="font-medium">{experience.company}</span>
          </div>
        </div>
        
        {/* Statut embeddings */}
        {renderStatusBadge()}
      </div>

      {/* Informations */}
      <div className="space-y-2 mb-4">
        <div className="flex items-center gap-2 text-gray-600 text-sm">
          <MapPin className="w-4 h-4" />
          <span>{experience.location}</span>
        </div>
        
        <div className="flex items-center gap-2 text-gray-600 text-sm">
          <Calendar className="w-4 h-4" />
          <span>
            {formatDate(experience.start_date)} -{" "}
            {experience.end_date ? formatDate(experience.end_date) : "Présent"}
          </span>
          <span className="text-gray-400">•</span>
          <span>{getDuration()}</span>
        </div>

        {experience.project_count > 0 && (
          <div className="text-sm text-gray-600">
            {experience.project_count} projet{experience.project_count > 1 ? "s" : ""}
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="flex gap-2 pt-4 border-t">
        <Button
          variant="outline"
          size="sm"
          onClick={() => onEdit(experience.id)}
        >
          Modifier
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => onDelete(experience.id)}
          className="text-red-600 hover:text-red-700 hover:bg-red-50"
        >
          Supprimer
        </Button>
      </div>
    </div>
  );
}