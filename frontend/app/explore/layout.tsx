import type { Metadata } from "next";
import { AccessGate } from "@/components/PrivateSection";

export const metadata: Metadata = {
  title: "Explorer le marché | Portfolio",
  description: "Exploration des offres d'emploi du marché data & IA",
};

export default function ExploreLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <AccessGate title="Explorer le marché">{children}</AccessGate>;
}