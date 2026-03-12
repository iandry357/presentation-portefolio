 
'use client';

import { useState } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';

interface CollapsibleSectionProps {
  title: string;
  icon?: React.ReactNode;
  defaultOpen?: boolean;
  children: React.ReactNode;
  badge?: React.ReactNode;
  isOpen?: boolean;
  onToggle?: () => void;
  keepMounted?: boolean;
}

export default function CollapsibleSection({
  title,
  icon,
  defaultOpen = false,
  children,
  badge,
  isOpen,
  onToggle,
  keepMounted = false,
}: CollapsibleSectionProps) {
  const [internalOpen, setInternalOpen] = useState(defaultOpen);
  const controlled = isOpen !== undefined && onToggle !== undefined;
  const open = controlled ? isOpen : internalOpen;
  const toggle = controlled ? onToggle : () => setInternalOpen(prev => !prev);

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
      {/* Header cliquable */}
      <button
        onClick={toggle}
        className="w-full flex items-center justify-between px-5 py-4 text-left hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
      >
        <div className="flex items-center gap-2">
          {icon && <span className="text-gray-500 dark:text-gray-400">{icon}</span>}
          <span className="font-semibold text-gray-800 dark:text-gray-100 text-sm">
            {title}
          </span>
          {badge && <span>{badge}</span>}
        </div>
        {open
          ? <ChevronUp className="w-4 h-4 text-gray-400 shrink-0" />
          : <ChevronDown className="w-4 h-4 text-gray-400 shrink-0" />
        }
      </button>

      {/* Contenu */}
      {keepMounted ? (
        <div className={`px-5 pb-5 border-t border-gray-100 dark:border-gray-700 ${open ? '' : 'hidden'}`}>
          {children}
        </div>
      ) : (
        open && (
          <div className="px-5 pb-5 border-t border-gray-100 dark:border-gray-700">
            {children}
          </div>
        )
      )}
    </div>
  );
}