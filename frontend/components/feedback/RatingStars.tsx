"use client";

import { useState } from "react";
import { Star } from "lucide-react";

interface RatingStarsProps {
  value: number | null;
  onChange: (rating: number) => void;
  size?: number;
}

export default function RatingStars({
  value,
  onChange,
  size = 32,
}: RatingStarsProps) {
  const [hoverRating, setHoverRating] = useState<number | null>(null);

  const displayRating = hoverRating ?? value ?? 0;

  return (
    <div className="flex gap-1">
      {[1, 2, 3, 4, 5].map((star) => (
        <button
          key={star}
          type="button"
          onClick={() => onChange(star)}
          onMouseEnter={() => setHoverRating(star)}
          onMouseLeave={() => setHoverRating(null)}
          className="transition-transform hover:scale-110 focus:outline-none focus:ring-2 focus:ring-blue-500 rounded"
          aria-label={`${star} étoile${star > 1 ? "s" : ""}`}
        >
          <Star
            size={size}
            className={`transition-colors ${
              star <= displayRating
                ? "fill-yellow-400 text-yellow-400"
                : "fill-none text-gray-300"
            }`}
          />
        </button>
      ))}
    </div>
  );
}