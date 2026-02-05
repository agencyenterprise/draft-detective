'use client';

import { UploadFileState } from '@/lib/hooks/use-upload';
import { formatBytes, UploadStatus, isActiveStatus } from '@/lib/services/chunked-upload';
import { Progress } from './progress';
import { Button } from './button';
import { cn } from '@/lib/utils';
import { Clock, Upload, CheckCircle2, XCircle, X, FileText, Loader2, LucideIcon } from 'lucide-react';

interface StatusConfig {
  icon: LucideIcon;
  color: string;
  label: string;
}

const STATUS_CONFIG: Record<UploadStatus, StatusConfig> = {
  pending: { icon: Clock, color: 'text-muted-foreground', label: 'Queued' },
  uploading: { icon: Upload, color: 'text-primary', label: 'Uploading' },
  completing: { icon: Loader2, color: 'text-primary', label: 'Completing' },
  completed: { icon: CheckCircle2, color: 'text-green-500', label: 'Complete' },
  error: { icon: XCircle, color: 'text-destructive', label: 'Failed' },
  paused: { icon: Clock, color: 'text-amber-500', label: 'Paused' },
};

const PROGRESS_STATUSES = new Set<UploadStatus>(['uploading', 'completing']);

interface UploadProgressItemProps {
  file: UploadFileState;
  onCancel?: () => void;
  showControls?: boolean;
}

function StatusDetail({ file }: { file: UploadFileState }) {
  if (PROGRESS_STATUSES.has(file.status)) {
    return (
      <div className="space-y-1">
        <Progress value={file.progress.progress_percent} className="h-1.5" />
        <div className="flex justify-between text-xs text-muted-foreground">
          <span>
            {formatBytes(file.progress.uploaded_size)} / {formatBytes(file.progress.total_size)}
          </span>
          <span>{file.progress.progress_percent}%</span>
        </div>
      </div>
    );
  }

  if (file.status === 'error') {
    return <span className="text-xs text-destructive">{file.error}</span>;
  }

  return <span className="text-xs text-muted-foreground">{formatBytes(file.file.size)}</span>;
}

function UploadProgressItem({ file, onCancel, showControls = true }: UploadProgressItemProps) {
  const config = STATUS_CONFIG[file.status];
  const Icon = config.icon;
  const isSpinning = PROGRESS_STATUSES.has(file.status);
  const canCancel = showControls && isActiveStatus(file.status) && onCancel;

  return (
    <div className="flex items-center gap-3 p-3 rounded-lg border bg-card min-w-0">
      <div className={cn('flex-shrink-0', config.color)}>
        <FileText className="h-5 w-5" />
      </div>

      <div className="flex-1 min-w-0 space-y-1.5 overflow-hidden">
        <div className="flex items-center justify-between gap-2 min-w-0">
          <span className="text-sm font-medium truncate flex-1 min-w-0" title={file.file.name}>
            {file.file.name}
          </span>
          <div className="flex items-center gap-1.5 flex-shrink-0">
            <Icon className={cn('h-4 w-4', config.color, isSpinning && 'animate-spin')} />
            <span className={cn('text-xs font-medium whitespace-nowrap', config.color)}>{config.label}</span>
          </div>
        </div>
        <StatusDetail file={file} />
      </div>

      {canCancel && (
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7 flex-shrink-0 text-muted-foreground hover:text-destructive"
          onClick={onCancel}
          title="Cancel upload"
        >
          <X className="h-3.5 w-3.5" />
        </Button>
      )}
    </div>
  );
}

export interface UploadProgressListProps {
  files: UploadFileState[];
  overallProgress: number;
  completedCount: number;
  totalCount: number;
  onCancelFile?: (fileId: string) => void;
  onCancelAll?: () => void;
  showGlobalControls?: boolean;
  className?: string;
}

export function UploadProgressList({
  files,
  overallProgress,
  completedCount,
  totalCount,
  onCancelFile,
  onCancelAll,
  showGlobalControls = true,
  className,
}: UploadProgressListProps) {
  if (files.length === 0) return null;

  const hasActiveUploads = files.some((f) => isActiveStatus(f.status));

  return (
    <div className={cn('flex flex-col', className)}>
      {/* Overall progress summary */}
      <div className="space-y-2 flex-shrink-0">
        <div className="flex items-center justify-between text-sm">
          <span className="font-medium">
            {completedCount}/{totalCount} files uploaded
          </span>
          <span className="text-muted-foreground">{overallProgress}%</span>
        </div>
        <Progress value={overallProgress} className="h-2" />
      </div>

      {/* Global controls */}
      {showGlobalControls && hasActiveUploads && onCancelAll && (
        <div className="flex items-center justify-end gap-2 pt-4 flex-shrink-0">
          <Button variant="outline" size="sm" className="text-destructive hover:text-destructive" onClick={onCancelAll}>
            <X className="h-4 w-4 mr-1.5" />
            Cancel All
          </Button>
        </div>
      )}

      {/* File list */}
      <div className="space-y-2 mt-4 flex-1 min-h-0 overflow-y-auto">
        {files.map((file) => (
          <UploadProgressItem
            key={file.id}
            file={file}
            onCancel={onCancelFile ? () => onCancelFile(file.id) : undefined}
            showControls={hasActiveUploads}
          />
        ))}
      </div>
    </div>
  );
}
