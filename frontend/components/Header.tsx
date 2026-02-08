
'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';

export default function Header() {
  const pathname = usePathname();

  return (
    <header className="border-b bg-white sticky top-0 z-50">
      <div className="container mx-auto px-4">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center gap-8">
            <Link href="/">
              <h1 className="text-xl font-bold text-gray-900 hover:text-gray-700 transition-colors cursor-pointer">
                Iandry (prononcé Ian'ch) RAKOTONIAINA
              </h1>
            </Link>
            <nav className="flex gap-1">
              <Link
                href="/cv"
                className={cn(
                  'px-4 py-2 rounded-md text-sm font-medium transition-colors',
                  pathname === '/cv'
                    ? 'bg-blue-100 text-blue-700'
                    : 'text-gray-600 hover:bg-gray-100'
                )}
              >
                CV
              </Link>
              <Link
                href="/chat"
                className={cn(
                  'px-4 py-2 rounded-md text-sm font-medium transition-colors',
                  pathname === '/chat'
                    ? 'bg-blue-100 text-blue-700'
                    : 'text-gray-600 hover:bg-gray-100'
                )}
              >
                Chat
              </Link>
            </nav>
          </div>
        </div>
      </div>
    </header>
  );
}
