'use client';

import { FileText, X, AlertTriangle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { formatFileSize } from './utils';
import { MAX_FILE_SIZE_BYTES, MAX_FILE_SIZE_MB } from '@/lib/constants';

export interface FileListItemProps {
  file: File;
  type: 'main' | 'supporting';
  onRemove: () => void;
}

export const FileListItem = ({ file, type, onRemove }: FileListItemProps) => {
  const isMain = type === 'main';
  const isOversized = file.size > MAX_FILE_SIZE_BYTES;

  const bgClass = isOversized
    ? 'bg-destructive/5 border-destructive/30'
    : isMain
      ? 'bg-primary/5 border-primary/20'
      : 'bg-muted/10 border-muted/20';

  const iconClass = isOversized ? 'text-destructive' : isMain ? 'text-primary' : 'text-muted-foreground';

  const tagClass = isMain ? 'bg-primary/20 text-primary' : 'bg-muted/60 text-muted-foreground';

  return (
    <div className={`flex items-center justify-between px-3 py-2 border rounded-lg ${bgClass}`}>
      <div className="flex items-center gap-2 min-w-0 flex-1">
        <FileText className={`w-4 h-4 flex-shrink-0 ${iconClass}`} />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <p className="text-sm font-medium truncate">{file.name}</p>
            {isOversized && <AlertTriangle className="w-3.5 h-3.5 text-destructive flex-shrink-0" />}
          </div>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <span className={`px-1.5 py-0.5 rounded ${tagClass}`}>{isMain ? 'Main' : 'Supporting'}</span>
            <span className={isOversized ? 'text-destructive font-medium' : ''}>{formatFileSize(file.size)}</span>
            {isOversized && <span className="text-destructive text-[10px]">(Max: {MAX_FILE_SIZE_MB} MB)</span>}
          </div>
        </div>
      </div>
      <Button
        type="button"
        variant="ghost"
        size="icon"
        onClick={onRemove}
        className="h-6 w-6 text-muted-foreground hover:text-destructive"
      >
        <X className="w-3 h-3" />
      </Button>
    </div>
  );
};
