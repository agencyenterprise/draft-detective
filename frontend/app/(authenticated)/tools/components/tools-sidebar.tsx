'use client';

import { cn } from '@/lib/utils';
import { FileDownIcon } from 'lucide-react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

interface Tool {
  name: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
}

const tools: Tool[] = [
  {
    name: 'Reference Downloader',
    href: '/tools/reference-downloader',
    icon: FileDownIcon,
  },
];

export function ToolsSidebar() {
  const pathname = usePathname();

  return (
    <div className="w-64 shrink-0 border-r border-gray-200 bg-white">
      <div className="p-4">
        <h2 className="text-sm font-semibold text-gray-900">Tools</h2>
        <p className="mt-1 text-xs text-gray-500">Standalone analysis tools</p>
      </div>
      <nav className="px-2 pb-4">
        <ul className="space-y-1">
          {tools.map((tool) => {
            const Icon = tool.icon;
            const isActive = pathname === tool.href;
            return (
              <li key={tool.href}>
                <Link
                  href={tool.href}
                  className={cn(
                    'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
                    isActive ? 'bg-indigo-50 text-indigo-700' : 'text-gray-700 hover:bg-gray-50 hover:text-gray-900',
                  )}
                >
                  <Icon className={cn('h-5 w-5', isActive ? 'text-indigo-600' : 'text-gray-400')} />
                  {tool.name}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
    </div>
  );
}
