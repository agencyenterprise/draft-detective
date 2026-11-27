'use client';

import { Markdown } from '@/components/shared/markdown';
import { formatFileSize } from '@/components/analysis-form/utils';
import { useRemoveFileMutation } from '@/components/results/references/mutations';
import { FileTypeIcon } from '@/components/shared/file-type-icon';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Button } from '@/components/ui/button';
import { FileDownloadLink } from '@/components/ui/file-download-link';
import { ComposedReference } from '@/lib/composed-references';
import { FileListItem, FileRole } from '@/lib/generated-api';
import { cn } from '@/lib/utils';
import { format } from 'date-fns';
import { Download, Loader2, RefreshCw, Trash2 } from 'lucide-react';
import { ReactNode, useState } from 'react';
import { GROUP, fileGroup, revisionLabel } from './role';

interface FileDetailProps {
  file: FileListItem;
  projectId: string;
  currentRevision: number;
  matchedReference?: ComposedReference;
  readOnly: boolean;
  onReplaceMain: () => void;
}

/**
 * One file's particulars and the things you can do to it. The list stays a
 * list — name, role, size, date — and everything that needs a second look or a
 * confirmation happens here.
 */
export function FileDetail({
  file,
  projectId,
  currentRevision,
  matchedReference,
  readOnly,
  onReplaceMain,
}: FileDetailProps) {
  const [removeOpen, setRemoveOpen] = useState(false);
  const removeFile = useRemoveFileMutation(projectId, file.id);

  const group = fileGroup(file.role);
  const isMain = file.role === FileRole.Main;
  const isCurrentMain = isMain && file.revision === currentRevision;
  const revision = revisionLabel(file, currentRevision);

  return (
    <div className="flex h-full flex-col">
      <AlertDialog open={removeOpen} onOpenChange={setRemoveOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remove this file?</AlertDialogTitle>
            <AlertDialogDescription className="break-all">
              {file.file_name} will be removed from the project for good. If a reference was matched to it, that
              reference goes back to having no source file.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={() => removeFile.mutate()}>Remove</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <div className="bg-background/90 sticky top-0 z-10 flex h-10 shrink-0 items-center gap-2 border-b px-4 backdrop-blur">
        <FileTypeIcon fileType={file.file_type} className="size-3.5 shrink-0 text-muted-foreground" />
        <span className="truncate text-xs font-medium" title={file.file_name}>
          {file.file_name}
        </span>
      </div>

      <div className="min-h-0 flex-1 space-y-5 overflow-y-auto px-4 py-4">
        <dl className="divide-y rounded-md border text-[12.5px]">
          {/* The header truncates; these names run to eighty characters, and
              the whole point of the pane is to be able to read one. */}
          <div className="px-3 py-2">
            <dt className="text-muted-foreground">File name</dt>
            <dd className="mt-0.5 break-all">{file.file_name}</dd>
          </div>

          <div className="px-3 py-2">
            <div className="flex items-center justify-between gap-3">
              <dt className="shrink-0 text-muted-foreground">Role</dt>
              <dd>
                <span className={cn('rounded px-1.5 py-0.5 text-[11px] font-medium', GROUP[group].className)}>
                  {GROUP[group].label}
                </span>
              </dd>
            </div>
            <p className="mt-1.5 text-[11.5px] leading-relaxed text-muted-foreground">{GROUP[group].description}</p>
          </div>
          {revision && <Fact label="Revision">{revision}</Fact>}
          <Fact label="Size">{formatFileSize(file.file_size)}</Fact>
          {/* `uploaded_by` holds a user id, not a name, and there is nothing
              here to resolve it against — a raw UUID tells the reader less
              than no row at all. */}
          <Fact label="Added">{format(file.created_at, 'MMM d, yyyy')}</Fact>
        </dl>

        <div className="flex flex-wrap gap-1.5">
          <Button asChild size="xs" variant="outline">
            <FileDownloadLink fileId={file.id}>
              <Download className="size-3" />
              Download
            </FileDownloadLink>
          </Button>

          {!readOnly && isCurrentMain && (
            <Button size="xs" variant="outline" onClick={onReplaceMain}>
              <RefreshCw className="size-3" />
              Replace, opening revision {currentRevision + 1}
            </Button>
          )}

          {!readOnly && !isMain && (
            <Button size="xs" variant="outline" disabled={removeFile.isPending} onClick={() => setRemoveOpen(true)}>
              {removeFile.isPending ? <Loader2 className="size-3 animate-spin" /> : <Trash2 className="size-3" />}
              Remove
            </Button>
          )}
        </div>

        {matchedReference && (
          <Section title="Matched reference">
            <div className="rounded-md border px-3 py-2 text-[12.5px] leading-relaxed [&_p]:mb-0">
              <Markdown>{matchedReference.text}</Markdown>
            </div>
          </Section>
        )}

        {isMain && !isCurrentMain && (
          <p className="text-[11.5px] leading-relaxed text-muted-foreground">
            Superseded main documents are kept so earlier revisions stay readable. They cannot be removed.
          </p>
        )}
      </div>
    </div>
  );
}

function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 px-3 py-2">
      <dt className="shrink-0 text-muted-foreground">{label}</dt>
      <dd className="min-w-0 truncate text-right">{children}</dd>
    </div>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section>
      <h3 className="mb-2 font-mono text-[10px] tracking-wide text-muted-foreground uppercase">{title}</h3>
      {children}
    </section>
  );
}
