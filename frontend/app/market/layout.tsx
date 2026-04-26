import type { Metadata } from "next"

export const metadata: Metadata = {
  title: "Observatoire Marché — Portfolio IA",
  description: "Analyses du marché de l'emploi data & IA en France",
}

export default function MarketLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}