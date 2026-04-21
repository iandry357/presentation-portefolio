import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Explorer le marché | Portfolio",
  description: "Exploration des offres d'emploi du marché data & IA",
};

export default function ExploreLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}