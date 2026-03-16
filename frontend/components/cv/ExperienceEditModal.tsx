"use client";

import { useState, useEffect } from "react";
import { Experience, ExperienceFormData, ProjectFormData } from "@/types";
import { getExperience, createExperience, updateExperience } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { X, Plus, Loader2 } from "lucide-react";
import ProjectForm from "./ProjectForm";
import SkillsSelector from "./SkillsSelector";
import dynamic from "next/dynamic";

const TipTapEditor = dynamic(
  () => import("@/components/cv/TipTapEditor"),
  { ssr: false }
);

interface ExperienceEditModalProps {
  experienceId?: number;
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

const emptyProject: ProjectFormData = {
  name: "",
  project_type: "",
  description: "",
  objective: "",
  problem: "",
  solution: "",
  results: "",
  impact: "",
  stack: "",
  collaborators: "",
};

const emptyExperience: ExperienceFormData = {
  company: "",
  role: "",
  mission_type: "",
  location: "",
  start_date: "",
  end_date: "",
  context: "",
  is_stage: false,
  projects: [],
  skill_ids: [],
};

export default function ExperienceEditModal({
  experienceId,
  isOpen,
  onClose,
  onSuccess,
}: ExperienceEditModalProps) {
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [formData, setFormData] = useState<ExperienceFormData>(emptyExperience);
  const [securityCode, setSecurityCode] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [isEndDatePresent, setIsEndDatePresent] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (isOpen && experienceId) {
      loadExperience();
    } else if (isOpen && !experienceId) {
      setFormData(emptyExperience);
      setSecurityCode("");
      setErrors({});
      setIsEndDatePresent(false);
    }
  }, [isOpen, experienceId]);

  const loadExperience = async () => {
    if (!experienceId) return;

    setLoading(true);
    try {
      const exp = await getExperience(experienceId);
      
      setFormData({
        company: exp.company,
        role: exp.role,
        mission_type: exp.mission_type,
        location: exp.location,
        start_date: exp.start_date,
        end_date: exp.end_date || "",
        context: exp.context,
        is_stage: exp.is_stage,
        projects: exp.projects.map((p) => ({
          id: p.id,
          name: p.name,
          project_type: p.project_type,
          description: p.description,
          objective: p.objective,
          problem: p.problem,
          solution: p.solution,
          results: p.results,
          impact: p.impact,
          stack: p.stack,
          collaborators: p.collaborators || "",
          start_date: p.start_date || "",
          end_date: p.end_date || "",
        })),
        skill_ids: exp.skills.map((s) => s.id),
      });

      setIsEndDatePresent(!!exp.end_date);
    } catch (error: any) {
      console.error("Erreur chargement expérience:", error);
      alert("Erreur lors du chargement de l'expérience");
    } finally {
      setLoading(false);
    }
  };

  const validate = (): boolean => {
    const newErrors: Record<string, string> = {};

    // Expérience
    if (!formData.company.trim()) newErrors.company = "Entreprise requise";
    if (!formData.role.trim()) newErrors.role = "Rôle requis";
    if (!formData.mission_type.trim()) newErrors.mission_type = "Type de mission requis";
    if (!formData.location.trim()) newErrors.location = "Localisation requise";
    if (!formData.start_date) newErrors.start_date = "Date de début requise";
    if (!formData.context.trim()) newErrors.context = "Contexte requis";

    // Projets
    formData.projects.forEach((project, idx) => {
      if (!project.name.trim()) newErrors[`projects.${idx}.name`] = "Nom requis";
      if (!project.project_type.trim()) newErrors[`projects.${idx}.project_type`] = "Type requis";
      if (!project.description.trim()) newErrors[`projects.${idx}.description`] = "Description requise";
      if (!project.objective.trim()) newErrors[`projects.${idx}.objective`] = "Objectif requis";
      if (!project.problem.trim()) newErrors[`projects.${idx}.problem`] = "Problème requis";
      if (!project.solution.trim()) newErrors[`projects.${idx}.solution`] = "Solution requise";
      if (!project.results.trim()) newErrors[`projects.${idx}.results`] = "Résultats requis";
      if (!project.impact.trim()) newErrors[`projects.${idx}.impact`] = "Impact requis";
      if (!project.stack.trim()) newErrors[`projects.${idx}.stack`] = "Stack requise";
    });

    // Code de sécurité
    if (!securityCode.trim()) newErrors.securityCode = "Code de sécurité requis";

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!validate()) {
      alert("Veuillez corriger les erreurs dans le formulaire");
      return;
    }

    setSaving(true);
    try {
      // Préparer les données (enlever end_date si "En cours")
      // Nettoyer les données avant envoi
        const cleanedData = { ...formData };

        // Supprimer end_date si vide
        if (!isEndDatePresent || !cleanedData.end_date) {
        delete cleanedData.end_date;
        }

        // Nettoyer les projets : supprimer les champs date vides
        if (cleanedData.projects) {
        cleanedData.projects = cleanedData.projects.map(p => {
            const cleaned = { ...p };
            if (!cleaned.start_date) delete cleaned.start_date;
            if (!cleaned.end_date) delete cleaned.end_date;
            if (!cleaned.duration_months) delete cleaned.duration_months;
            if (!cleaned.collaborators || cleaned.collaborators.trim() === '') {
            delete cleaned.collaborators;
            }
            return cleaned;
        });
        }

        const dataToSubmit = cleanedData;
    //   const dataToSubmit = {
    //     ...formData,
    //     end_date: isEndDatePresent ? formData.end_date : undefined,
    //   };

      if (experienceId) {
        await updateExperience(experienceId, dataToSubmit, securityCode);
      } else {
        await createExperience(dataToSubmit, securityCode);
      }

      onSuccess();
      onClose();
    } catch (error: any) {
      console.error("Erreur sauvegarde:", error);
      alert(error.message || "Erreur lors de la sauvegarde");
    } finally {
      setSaving(false);
    }
  };

  const handleProjectChange = (
    index: number,
    field: keyof ProjectFormData,
    value: string
  ) => {
    const newProjects = [...formData.projects];
    newProjects[index] = { ...newProjects[index], [field]: value };
    setFormData({ ...formData, projects: newProjects });
  };

  const handleAddProject = () => {
    setFormData({
      ...formData,
      projects: [...formData.projects, { ...emptyProject }],
    });
  };

  const handleRemoveProject = (index: number) => {
    setFormData({
      ...formData,
      projects: formData.projects.filter((_, i) => i !== index),
    });
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b">
          <h2 className="text-2xl font-bold text-gray-900">
            {experienceId ? "Modifier l'expérience" : "Nouvelle expérience"}
          </h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        {/* Body scrollable */}
        <div className="flex-1 overflow-y-auto p-6">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-6">
              {/* Section 1 - Informations principales */}
              <div className="space-y-4">
                <h3 className="text-lg font-semibold text-gray-900">
                  Informations principales
                </h3>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Entreprise <span className="text-red-500">*</span>
                    </label>
                    <Input
                      value={formData.company}
                      onChange={(e) =>
                        setFormData({ ...formData, company: e.target.value })
                      }
                      className={errors.company ? "border-red-500" : ""}
                    />
                    {errors.company && (
                      <p className="text-red-500 text-xs mt-1">{errors.company}</p>
                    )}
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Rôle <span className="text-red-500">*</span>
                    </label>
                    <Input
                      value={formData.role}
                      onChange={(e) =>
                        setFormData({ ...formData, role: e.target.value })
                      }
                      className={errors.role ? "border-red-500" : ""}
                    />
                    {errors.role && (
                      <p className="text-red-500 text-xs mt-1">{errors.role}</p>
                    )}
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Type de mission <span className="text-red-500">*</span>
                    </label>
                    <Input
                      value={formData.mission_type}
                      onChange={(e) =>
                        setFormData({ ...formData, mission_type: e.target.value })
                      }
                      placeholder="Ex: CDI, Freelance, Consulting"
                      className={errors.mission_type ? "border-red-500" : ""}
                    />
                    {errors.mission_type && (
                      <p className="text-red-500 text-xs mt-1">{errors.mission_type}</p>
                    )}
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Localisation <span className="text-red-500">*</span>
                    </label>
                    <Input
                      value={formData.location}
                      onChange={(e) =>
                        setFormData({ ...formData, location: e.target.value })
                      }
                      placeholder="Ex: Paris, Remote"
                      className={errors.location ? "border-red-500" : ""}
                    />
                    {errors.location && (
                      <p className="text-red-500 text-xs mt-1">{errors.location}</p>
                    )}
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Date de début <span className="text-red-500">*</span>
                    </label>
                    <Input
                      type="date"
                      value={formData.start_date}
                      onChange={(e) =>
                        setFormData({ ...formData, start_date: e.target.value })
                      }
                      className={errors.start_date ? "border-red-500" : ""}
                    />
                    {errors.start_date && (
                      <p className="text-red-500 text-xs mt-1">{errors.start_date}</p>
                    )}
                  </div>

                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <label className="block text-sm font-medium text-gray-700">
                        Date de fin
                      </label>
                      <label className="flex items-center gap-1 text-sm text-gray-600">
                        <input
                          type="checkbox"
                          checked={!isEndDatePresent}
                          onChange={(e) => setIsEndDatePresent(!e.target.checked)}
                          className="rounded"
                        />
                        En cours
                      </label>
                    </div>
                    <Input
                      type="date"
                      value={formData.end_date || ""}
                      onChange={(e) =>
                        setFormData({ ...formData, end_date: e.target.value })
                      }
                      disabled={!isEndDatePresent}
                      className={isEndDatePresent ? "" : "bg-gray-100"}
                    />
                  </div>
                </div>

                <div>
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={formData.is_stage}
                      onChange={(e) =>
                        setFormData({ ...formData, is_stage: e.target.checked })
                      }
                      className="rounded"
                    />
                    <span className="text-sm font-medium text-gray-700">
                      Il s'agit d'un stage
                    </span>
                  </label>
                </div>
              </div>

              {/* Section 2 - Contexte */}
              <div className="space-y-4">
                <h3 className="text-lg font-semibold text-gray-900">Contexte</h3>
                {mounted && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Description du contexte <span className="text-red-500">*</span>
                    </label>
                    <TipTapEditor
                      content={formData.context}
                      onChange={(value) =>
                        setFormData({ ...formData, context: value })
                      }
                      placeholder="Décrivez le contexte de cette expérience..."
                    />
                    {errors.context && (
                      <p className="text-red-500 text-xs mt-1">{errors.context}</p>
                    )}
                  </div>
                )}
              </div>

              {/* Section 3 - Compétences */}
              <div className="space-y-4">
                <h3 className="text-lg font-semibold text-gray-900">Compétences</h3>
                <SkillsSelector
                  selectedIds={formData.skill_ids}
                  onChange={(ids) => setFormData({ ...formData, skill_ids: ids })}
                />
              </div>

              {/* Section 4 - Projets */}
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-lg font-semibold text-gray-900">Projets</h3>
                  <Button
                    type="button"
                    onClick={handleAddProject}
                    variant="outline"
                    size="sm"
                  >
                    <Plus className="w-4 h-4 mr-1" />
                    Ajouter un projet
                  </Button>
                </div>

                {formData.projects.length === 0 ? (
                  <p className="text-gray-500 text-sm text-center py-4">
                    Aucun projet ajouté
                  </p>
                ) : (
                  <div className="space-y-4">
                    {formData.projects.map((project, index) => (
                      <ProjectForm
                        key={index}
                        project={project}
                        index={index}
                        onChange={handleProjectChange}
                        onRemove={handleRemoveProject}
                        errors={errors}
                      />
                    ))}
                  </div>
                )}
              </div>

              {/* Section 5 - Code de sécurité */}
              <div className="space-y-4 pt-4 border-t">
                <h3 className="text-lg font-semibold text-gray-900">
                  Code de sécurité
                </h3>
                <div className="max-w-md">
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Code <span className="text-red-500">*</span>
                  </label>
                  <Input
                    type="password"
                    value={securityCode}
                    onChange={(e) => setSecurityCode(e.target.value)}
                    placeholder="Saisissez le code de sécurité"
                    className={errors.securityCode ? "border-red-500" : ""}
                  />
                  {errors.securityCode && (
                    <p className="text-red-500 text-xs mt-1">{errors.securityCode}</p>
                  )}
                </div>
              </div>
            </form>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 p-6 border-t bg-gray-50">
          <Button
            type="button"
            variant="outline"
            onClick={onClose}
            disabled={saving}
          >
            Annuler
          </Button>
          <Button onClick={handleSubmit} disabled={saving || loading}>
            {saving ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Enregistrement...
              </>
            ) : (
              "Enregistrer"
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}