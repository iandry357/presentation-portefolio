'use client';

import { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';

const NAV_LINKS = [
  { href: '/cv',        label: 'CV',        match: (p: string) => p === '/cv' },
  { href: '/chat',      label: 'Chat',      match: (p: string) => p === '/chat' },
  { href: '/jobs',      label: 'Jobs',      match: (p: string) => p === '/jobs' || p.startsWith('/jobs/') },
  { href: '/companies', label: 'Companies', match: (p: string) => p === '/companies' || p.startsWith('/companies/') },
  { href: '/explore',   label: 'Explorer',  match: (p: string) => p === '/explore' },
];

export default function Header() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  return (
    <header className="border-b bg-white sticky top-0 z-50">
      <div className="container mx-auto px-4">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <Link href="/" onClick={() => setOpen(false)}>
            <h1 className="text-xl font-bold text-gray-900 hover:text-gray-700 transition-colors cursor-pointer">
              <span className="hidden sm:inline">Iandry (prononcé Yan'ch) RAKOTONIAINA</span>
              <span className="sm:hidden">Yan'ch</span>
            </h1>
          </Link>

          {/* Nav desktop */}
          <nav className="hidden md:flex gap-1">
            {NAV_LINKS.map(({ href, label, match }) => (
              <Link
                key={href}
                href={href}
                className={cn(
                  'px-4 py-2 rounded-md text-sm font-medium transition-colors',
                  match(pathname)
                    ? 'bg-blue-100 text-blue-700'
                    : 'text-gray-600 hover:bg-gray-100'
                )}
              >
                {label}
              </Link>
            ))}
          </nav>

          {/* Bouton hamburger mobile */}
          <button
            onClick={() => setOpen(o => !o)}
            className="md:hidden p-2 rounded-md text-gray-600 hover:bg-gray-100 transition-colors"
            aria-label="Menu"
          >
            {open ? (
              // X
              <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            ) : (
              // Hamburger
              <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            )}
          </button>
        </div>
      </div>

      {/* Menu mobile déroulant */}
      {open && (
        <div className="md:hidden border-t bg-white px-4 py-2">
          {NAV_LINKS.map(({ href, label, match }) => (
            <Link
              key={href}
              href={href}
              onClick={() => setOpen(false)}
              className={cn(
                'block px-4 py-3 rounded-md text-sm font-medium transition-colors',
                match(pathname)
                  ? 'bg-blue-100 text-blue-700'
                  : 'text-gray-600 hover:bg-gray-100'
              )}
            >
              {label}
            </Link>
          ))}
        </div>
      )}
    </header>
  );
}