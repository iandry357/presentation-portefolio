"use client";

import { useEffect } from "react";
import { getOrCreateSession } from "@/lib/session";

export default function SessionInitializer() {
  useEffect(() => {
    getOrCreateSession();
  }, []);

  return null; // Pas de rendu visuel
}