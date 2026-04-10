'use client';

import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';

interface RevisionSwitcherProps {
  currentRevision: number;
  totalRevisions: number;
  selectedRevision: number;
  onRevisionChange: (revision: number) => void;
}

export function RevisionSwitcher({
  currentRevision,
  totalRevisions,
  selectedRevision,
  onRevisionChange,
}: RevisionSwitcherProps) {
  if (totalRevisions <= 1) return null;

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Select value={String(selectedRevision)} onValueChange={(v) => onRevisionChange(Number(v))}>
          <SelectTrigger className="h-8 w-auto gap-1 text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {Array.from({ length: totalRevisions }, (_, i) => totalRevisions - i).map((rev) => (
              <SelectItem key={rev} value={String(rev)}>
                Revision {rev}
                {rev === currentRevision ? ' (latest)' : ''}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </TooltipTrigger>
      <TooltipContent>Switch between document revisions</TooltipContent>
    </Tooltip>
  );
}
