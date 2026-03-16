"use client";

import { useEffect, useState } from "react";
import { ExperienceListItem } from "@/types";
import { 
  getExperiences, 
  deleteExperience, 
  retryExperienceEmbeddings 
} from "@/lib/api";
import ExperienceCard from "@/components/cv/ExperienceCard";
import ExperienceEditModal from "@/components/cv/ExperienceEditModal";
import { Button } from "@/components/ui/button";
import { Plus, Loader2, ArrowLeft } from "lucide-react";
import Link from "next/link";

export default function CVEditPage() {
  const [experiences, setExperiences] = useState<ExperienceListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | undefined>();

  // Charger les expériences
  const loadExperiences = async () => {
    try {
      const data = await getExperiences();
      setExperiences(data);
    } catch (error) {
      console.error("Erreur chargement expériences:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadExperiences();
  }, []);

  // Polling automatique si au moins une expérience a status pending
  useEffect(() => {
    const hasPending = experiences.some(
      (exp) => exp.embedding_status === "pending"
    );

    if (!hasPending) return;

    const interval = setInterval(() => {
      loadExperiences();
    }, 5000);

    return () => clearInterval(interval);
  }, [experiences]);

  // Handlers
  const handleCreate = () => {
    setEditingId(undefined);
    setIsModalOpen(true);
  };

  const handleEdit = (id: number) => {
    setEditingId(id);
    setIsModalOpen(true);
  };

  const handleDelete = async (id: number) => {
    const code = prompt("Code de sécurité :");
    if (!code) return;

    try {
      await deleteExperience(id, code);
      await loadExperiences();
      alert("Expérience supprimée avec succès");
    } catch (error: any) {
      alert(error.message || "Erreur lors de la suppression");
    }
  };

  const handleRetry = async (id: number) => {
    const code = prompt("Code de sécurité :");
    if (!code) return;

    try {
      await retryExperienceEmbeddings(id, code);
      await loadExperiences();
      alert("Régénération des embeddings lancée");
    } catch (error: any) {
      alert(error.message || "Erreur lors du redémarrage");
    }
  };

  const handleSuccess = () => {
    loadExperiences();
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8 max-w-6xl">
      {/* Header */}
      <div className="mb-8">
        <Link
          href="/cv"
          className="inline-flex items-center gap-2 text-blue-600 hover:text-blue-700 mb-4"
        >
          <ArrowLeft className="w-4 h-4" />
          Retour à l'affichage
        </Link>
        
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">
              Gestion du CV
            </h1>
            <p className="text-gray-600 mt-2">
              Gérez vos expériences professionnelles
            </p>
          </div>
          <Button onClick={handleCreate}>
            <Plus className="w-4 h-4 mr-2" />
            Nouvelle expérience
          </Button>
        </div>
      </div>

      {/* Liste des expériences */}
      {experiences.length === 0 ? (
        <div className="text-center py-12 bg-white rounded-lg shadow-sm border border-gray-200">
          <p className="text-gray-500 mb-4">
            Aucune expérience enregistrée
          </p>
          <Button onClick={handleCreate} variant="outline">
            Créer votre première expérience
          </Button>
        </div>
      ) : (
        <div className="grid gap-6">
          {experiences.map((exp) => (
            <ExperienceCard
              key={exp.id}
              experience={exp}
              onEdit={handleEdit}
              onDelete={handleDelete}
              onRetry={handleRetry}
            />
          ))}
        </div>
      )}

      {/* Modal */}
      <ExperienceEditModal
        experienceId={editingId}
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSuccess={handleSuccess}
      />
    </div>
  );
}