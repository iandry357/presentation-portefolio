"use client";

import { Input } from "@/components/ui/input";
import { X } from "lucide-react";
import { useState } from "react";

interface SkillsSelectorProps {
  selectedIds: number[];
  onChange: (ids: number[]) => void;
}

export default function SkillsSelector({
  selectedIds,
  onChange,
}: SkillsSelectorProps) {
  const [inputValue, setInputValue] = useState("");

  const handleAddSkill = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && inputValue.trim()) {
      e.preventDefault();
      const skillId = parseInt(inputValue.trim());
      
      if (!isNaN(skillId) && !selectedIds.includes(skillId)) {
        onChange([...selectedIds, skillId]);
      }
      
      setInputValue("");
    }
  };

  const handleRemoveSkill = (id: number) => {
    onChange(selectedIds.filter((skillId) => skillId !== id));
  };

  return (
    <div className="space-y-2">
      <label className="block text-sm font-medium text-gray-700">
        Compétences
      </label>
      
      {/* Tags affichés */}
      {selectedIds.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-2">
          {selectedIds.map((id) => (
            <div
              key={id}
              className="flex items-center gap-1 px-3 py-1 bg-blue-50 text-blue-700 rounded-full text-sm"
            >
              <span>Skill #{id}</span>
              <button
                type="button"
                onClick={() => handleRemoveSkill(id)}
                className="hover:bg-blue-100 rounded-full p-0.5"
              >
                <X className="w-3 h-3" />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Input temporaire (en attendant l'endpoint GET /cv/skills) */}
      <div>
        <Input
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleAddSkill}
          placeholder="Saisir un ID de skill et appuyer sur Entrée (temporaire)"
          className="text-sm"
        />
        <p className="text-xs text-gray-500 mt-1">
          Version temporaire : saisir les IDs de compétences manuellement.
          Le sélecteur sera remplacé par une vraie liste après implémentation de GET /cv/skills.
        </p>
      </div>
    </div>
  );
}