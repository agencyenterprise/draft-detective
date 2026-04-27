import { Github } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import packageJson from '@/package.json';

export function VersionBadge() {
  const repoUrl = packageJson.repository?.url;

  return (
    <div className="fixed bottom-4 right-4 z-50">
      <Badge
        variant="outline"
        className="text-xs font-mono bg-background/80 backdrop-blur-sm opacity-50 hover:opacity-100 transition-opacity gap-2"
      >
        <a
          href={`${repoUrl}/blob/main/CHANGELOG.md`}
          target="_blank"
          rel="noopener noreferrer"
          aria-label={`View release notes for version ${packageJson.version}`}
          className="hover:underline"
        >
          v{packageJson.version}
        </a>
        <a
          href={repoUrl}
          target="_blank"
          rel="noopener noreferrer"
          aria-label="View source on GitHub"
          className="inline-flex items-center"
        >
          <Github className="w-3 h-3" />
        </a>
      </Badge>
    </div>
  );
}
