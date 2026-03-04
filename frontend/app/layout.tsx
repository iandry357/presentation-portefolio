import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import Script from 'next/script';
import './globals.css';
import Header from '@/components/Header';

const inter = Inter({ subsets: ['latin'] });

const GA_ID = process.env.NEXT_PUBLIC_GA_ID;
const isProd = process.env.NEXT_PUBLIC_ENV === 'production';

export const metadata: Metadata = {
  title: {
    default: 'Iandry RAKOTONIAINA — Data Scientist & AI-ML Engineer',
    template: '%s — Iandry RAKOTONIAINA',
  },
  description:
    'Portefolio de Iandry RAKOTONIAINA, Data Scientist / Data Engineer / AI-ML Engineer, 7 ans d\'expérience en recherche appliquée et consulting industriel.',
  robots: {
    index: true,
    follow: true,
  },
  verification: {
    google: '0lwLlboK8A5Jj7JPxSFetCnfu5BpkWPnOTA49klcmtU',
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="fr">
      <body className={inter.className}>
        {isProd && GA_ID && (
          <>
            <Script
              src={`https://www.googletagmanager.com/gtag/js?id=${GA_ID}`}
              strategy="afterInteractive"
            />
            <Script id="google-analytics" strategy="afterInteractive">
              {`
                window.dataLayer = window.dataLayer || [];
                function gtag(){dataLayer.push(arguments);}
                gtag('js', new Date());
                gtag('config', '${GA_ID}');
              `}
            </Script>
          </>
        )}
        <div className="min-h-screen flex flex-col bg-gray-50">
          <Header />
          <main className="flex-1">{children}</main>
        </div>
      </body>
    </html>
  );
}