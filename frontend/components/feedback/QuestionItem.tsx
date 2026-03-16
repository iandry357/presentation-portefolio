"use client";

import { Textarea } from "@/components/ui/textarea";

interface QuestionItemProps {
  questionText: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}

export default function QuestionItem({
  questionText,
  value,
  onChange,
  placeholder = "Votre commentaire (optionnel)...",
}: QuestionItemProps) {
  return (
    <div className="space-y-2">
      <label className="block text-sm font-medium text-gray-700">
        {questionText}
      </label>
      <Textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        rows={3}
        className="resize-none"
      />
    </div>
  );
}