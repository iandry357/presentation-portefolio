"use client";

import { ProjectFormData } from "@/types";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Trash2 } from "lucide-react";
import dynamic from "next/dynamic";
import { useEffect, useState } from "react";

// Import TipTap dynamiquement (évite SSR)
const TipTapEditor = dynamic(
  () => import("@/components/cv/TipTapEditor"),
  { ssr: false }
);

interface ProjectFormProps {
  project: ProjectFormData;
  index: number;
  onChange: (index: number, field: keyof ProjectFormData, value: string) => void;
  onRemove: (index: number) => void;
  errors?: Record<string, string>;
}

export default function ProjectForm({
  project,
  index,
  onChange,
  onRemove,
  errors = {},
}: ProjectFormProps) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const fieldError = (field: string) => errors[`projects.${index}.${field}`];

  return (
    <div className="border rounded-lg p-4 bg-gray-50 space-y-4">
      {/* Header avec bouton supprimer */}
      <div className="flex items-center justify-between">
        <h4 className="font-medium text-gray-900">
          Projet {index + 1} {project.name && `- ${project.name}`}
        </h4>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={() => onRemove(index)}
          className="text-red-600 hover:text-red-700 hover:bg-red-50"
        >
          <Trash2 className="w-4 h-4" />
        </Button>
      </div>

      {/* Champs de base */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Nom du projet <span className="text-red-500">*</span>
          </label>
          <Input
            value={project.name}
            onChange={(e) => onChange(index, "name", e.target.value)}
            placeholder="Ex: Refonte du pipeline de données"
            className={fieldError("name") ? "border-red-500" : ""}
          />
          {fieldError("name") && (
            <p className="text-red-500 text-xs mt-1">{fieldError("name")}</p>
          )}
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Type de projet <span className="text-red-500">*</span>
          </label>
          <Input
            value={project.project_type}
            onChange={(e) => onChange(index, "project_type", e.target.value)}
            placeholder="Ex: Data Engineering, MLOps, etc."
            className={fieldError("project_type") ? "border-red-500" : ""}
          />
          {fieldError("project_type") && (
            <p className="text-red-500 text-xs mt-1">{fieldError("project_type")}</p>
          )}
        </div>
      </div>

      {/* Éditeurs riches */}
      {mounted && (
        <>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Description <span className="text-red-500">*</span>
            </label>
            <TipTapEditor
              content={project.description}
              onChange={(value) => onChange(index, "description", value)}
              placeholder="Décrivez le projet..."
            />
            {fieldError("description") && (
              <p className="text-red-500 text-xs mt-1">{fieldError("description")}</p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Objectif <span className="text-red-500">*</span>
            </label>
            <TipTapEditor
              content={project.objective}
              onChange={(value) => onChange(index, "objective", value)}
              placeholder="Quel était l'objectif principal ?"
            />
            {fieldError("objective") && (
              <p className="text-red-500 text-xs mt-1">{fieldError("objective")}</p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Problème <span className="text-red-500">*</span>
            </label>
            <TipTapEditor
              content={project.problem}
              onChange={(value) => onChange(index, "problem", value)}
              placeholder="Quel problème devait-il résoudre ?"
            />
            {fieldError("problem") && (
              <p className="text-red-500 text-xs mt-1">{fieldError("problem")}</p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Solution <span className="text-red-500">*</span>
            </label>
            <TipTapEditor
              content={project.solution}
              onChange={(value) => onChange(index, "solution", value)}
              placeholder="Comment l'avez-vous résolu ?"
            />
            {fieldError("solution") && (
              <p className="text-red-500 text-xs mt-1">{fieldError("solution")}</p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Résultats <span className="text-red-500">*</span>
            </label>
            <TipTapEditor
              content={project.results}
              onChange={(value) => onChange(index, "results", value)}
              placeholder="Quels résultats concrets ?"
            />
            {fieldError("results") && (
              <p className="text-red-500 text-xs mt-1">{fieldError("results")}</p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Impact <span className="text-red-500">*</span>
            </label>
            <TipTapEditor
              content={project.impact}
              onChange={(value) => onChange(index, "impact", value)}
              placeholder="Quel impact sur l'organisation ?"
            />
            {fieldError("impact") && (
              <p className="text-red-500 text-xs mt-1">{fieldError("impact")}</p>
            )}
          </div>
        </>
      )}

      {/* Stack et collaborateurs */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Stack technique <span className="text-red-500">*</span>
          </label>
          <Input
            value={project.stack}
            onChange={(e) => onChange(index, "stack", e.target.value)}
            placeholder="Ex: Python, Airflow, PostgreSQL, Docker"
            className={fieldError("stack") ? "border-red-500" : ""}
          />
          {fieldError("stack") && (
            <p className="text-red-500 text-xs mt-1">{fieldError("stack")}</p>
          )}
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Collaborateurs
          </label>
          <Input
            value={project.collaborators || ""}
            onChange={(e) => onChange(index, "collaborators", e.target.value)}
            placeholder="Ex: Équipe de 3 data scientists"
          />
        </div>
      </div>

      {/* Dates */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Date de début
          </label>
          <Input
            type="date"
            value={project.start_date || ""}
            onChange={(e) => onChange(index, "start_date", e.target.value)}
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Date de fin
          </label>
          <Input
            type="date"
            value={project.end_date || ""}
            onChange={(e) => onChange(index, "end_date", e.target.value)}
          />
        </div>
      </div>
    </div>
  );
}