import { Badge } from '@/components/ui/badge';
import packageJson from '@/package.json';

export function VersionBadge() {
  const repoUrl = packageJson.repository?.url;

  return (
    <div className="fixed bottom-4 right-4 z-50">
      <a
        href={`${repoUrl}/blob/main/CHANGELOG.md`}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-block"
        aria-label={`View release notes for version ${packageJson.version}`}
      >
        <Badge
          variant="outline"
          className="text-xs font-mono bg-background/80 backdrop-blur-sm opacity-50 hover:opacity-100 transition-opacity cursor-pointer"
        >
          v{packageJson.version}
        </Badge>
      </a>
    </div>
  );
}
