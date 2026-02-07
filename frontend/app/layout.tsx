
import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import Header from '@/components/Header';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: "Iandry RAKOTONIAINA - ML Engineer",
  description: 'Portfolio interactif avec RAG - Posez vos questions sur mon parcours',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="fr">
      <body className={inter.className}>
        <div className="min-h-screen flex flex-col bg-gray-50">
          <Header />
          <main className="flex-1">{children}</main>
        </div>
      </body>
    </html>
  );
}