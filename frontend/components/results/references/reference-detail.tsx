'use client';

import { Markdown } from '@/components/shared/markdown';
import { FileUploadDialog } from '@/components/results/references/file-upload-dialog';
import { useFetchFromWebMutation, useRemoveFileMutation } from '@/components/results/references/mutations';
import { ReferenceReviewItem, ReferenceReviewStatus } from '@/components/results/references/types';
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
import { HelpLink } from '@/components/help/help-link';
import { WorkflowConfigDialog } from '@/components/workflows/workflow-config-dialog';
import { MatchSource, WorkflowRunType } from '@/lib/generated-api';
import { cn } from '@/lib/utils';
import {
  ChevronDownIcon,
  ChevronRightIcon,
  Download,
  FileText,
  FileX,
  GlobeIcon,
  Loader2,
  LucideIcon,
  Sparkles,
  Trash2,
  Upload,
  User,
} from 'lucide-react';
import { ReactNode, useState } from 'react';
import { readFetchOutcome } from './fetch-outcome';
import { STATUS } from './status';

const SOURCE: Record<MatchSource, { icon: LucideIcon; label: string }> = {
  [MatchSource.ManualUpload]: { icon: User, label: 'Uploaded by someone on the project' },
  [MatchSource.AutoMatched]: { icon: Sparkles, label: 'Matched from your supporting documents' },
  [MatchSource.AutoFetched]: { icon: GlobeIcon, label: 'Downloaded from the web' },
};

interface ReferenceDetailProps {
  reference: ReferenceReviewItem;
  projectId: string;
  readOnly: boolean;
  /** Files are being processed project-wide, so edits here would race. */
  disabled: boolean;
  /** Opens the shared explanation of why source files are wanted. */
}

/**
 * Everything about one reference that is not the citation itself: which source
 * file stands behind it, where that file came from, how to change it, and what
 * the web fetch found. The list keeps only what you scan; this keeps what you
 * act on, so a row does not have to carry six controls.
 */
export function ReferenceDetail({ reference, projectId, readOnly, disabled }: ReferenceDetailProps) {
  const { id, index, text, status, matchedFile, source, fetchResult } = reference;
  const [uploadMode, setUploadMode] = useState<'upload' | 'replace' | null>(null);
  const [fetchDialogOpen, setFetchDialogOpen] = useState(false);
  const [removeOpen, setRemoveOpen] = useState(false);
  // The backend only reports 'fetching' once the workflow starts, a round trip
  // away; without this the button snaps back to idle in between.
  const [fetchInitiated, setFetchInitiated] = useState(false);

  const removeFile = useRemoveFileMutation(projectId, matchedFile?.id);
  const fetchFromWeb = useFetchFromWebMutation(projectId, id, text);

  const isFetching = fetchFromWeb.isPending || (fetchInitiated && status !== 'fetching');
  const busy = removeFile.isPending || isFetching || uploadMode !== null;
  const actionsDisabled = busy || status === 'fetching' || disabled;
  const displayStatus: ReferenceReviewStatus = isFetching ? 'fetching' : status;
  const fetchRead = fetchResult ? readFetchOutcome(fetchResult) : null;

  // Once the backend reports the fetch, its status takes over.
  if (fetchInitiated && (status === 'fetching' || status === 'matched')) setFetchInitiated(false);

  return (
    <div className="flex h-full flex-col">
      <FileUploadDialog
        isOpen={uploadMode !== null}
        title={uploadMode === 'replace' ? 'Replace source file' : 'Provide source file'}
        description={
          uploadMode === 'replace'
            ? 'Upload a new document to take the place of the current one. We process it and match it to this reference.'
            : 'Upload the document this reference cites. We process it and match it to this reference.'
        }
        multiple={false}
        projectId={projectId}
        referenceId={id}
        onCancel={() => setUploadMode(null)}
        onComplete={() => setUploadMode(null)}
      />

      <WorkflowConfigDialog
        isOpen={fetchDialogOpen}
        type={WorkflowRunType.ReferenceDownloader}
        title="Fetch this source from the web"
        description="Draft Detective searches for this reference and downloads the full text if it finds one it can read."
        helpTopic="source-files"
        submitLabel="Fetch source"
        projectId={projectId}
        onConfirm={() =>
          fetchFromWeb.mutate(undefined, {
            onSuccess: () => {
              setFetchDialogOpen(false);
              setFetchInitiated(true);
            },
          })
        }
        onCancel={() => setFetchDialogOpen(false)}
      />

      <AlertDialog open={removeOpen} onOpenChange={setRemoveOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remove this source file?</AlertDialogTitle>
            <AlertDialogDescription className="break-all">
              {matchedFile?.name} will no longer be matched to this reference, and assessments that read sources will
              skip it.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={() => removeFile.mutate()}>Remove</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <div className="bg-background/90 sticky top-0 z-10 flex h-10 shrink-0 items-center gap-2 border-b px-4 backdrop-blur">
        <span className={cn('text-xs font-medium', STATUS[displayStatus].text)}>
          {displayStatus === 'fetching' ? (
            <span className="inline-flex items-center gap-1.5">
              <Loader2 className="size-3.5 animate-spin" />
              {STATUS.fetching.label}
            </span>
          ) : (
            STATUS[displayStatus].label
          )}
        </span>
        <span className="ml-auto font-mono text-[11px] tabular-nums text-muted-foreground">Reference {index + 1}</span>
      </div>

      <div className="min-h-0 flex-1 space-y-5 overflow-y-auto px-4 py-4">
        <Section title="Source file">
          {matchedFile ? (
            <div className="space-y-2">
              <div className="rounded-md border p-2.5">
                <FileDownloadLink
                  fileId={matchedFile.id}
                  className="group flex min-w-0 items-start gap-2 text-[12.5px]"
                >
                  <FileText className="mt-0.5 size-3.5 shrink-0 text-muted-foreground" />
                  <span className="min-w-0 flex-1">
                    <span className="text-primary block break-all group-hover:underline">{matchedFile.name}</span>
                    <span className="text-[11px] text-muted-foreground">{matchedFile.size}</span>
                  </span>
                  <Download className="mt-0.5 size-3.5 shrink-0 text-muted-foreground" />
                </FileDownloadLink>
                {source && <SourceLine source={source} />}
              </div>

              {!readOnly && (
                <div className="flex flex-wrap gap-1.5">
                  <Button
                    size="xs"
                    variant="outline"
                    disabled={actionsDisabled}
                    onClick={() => setUploadMode('replace')}
                  >
                    <Upload className="size-3" />
                    Replace
                  </Button>
                  <Button size="xs" variant="outline" disabled={actionsDisabled} onClick={() => setRemoveOpen(true)}>
                    {removeFile.isPending ? <Loader2 className="size-3 animate-spin" /> : <Trash2 className="size-3" />}
                    Remove
                  </Button>
                </div>
              )}
            </div>
          ) : (
            <div className="space-y-2">
              <p className={cn('flex items-start gap-2 text-[12.5px]', STATUS.unmatched.text)}>
                <FileX className="mt-0.5 size-3.5 shrink-0" />
                <span>
                  {displayStatus === 'fetching'
                    ? 'We are searching the web for a copy of this source.'
                    : 'Source file has not been provided for this reference yet.'}{' '}
                  <HelpLink topic="source-files">What is this?</HelpLink>
                </span>
              </p>

              {!readOnly && (
                <div className="flex flex-wrap gap-1.5">
                  <Button
                    size="xs"
                    variant="outline"
                    disabled={actionsDisabled}
                    onClick={() => setFetchDialogOpen(true)}
                  >
                    {isFetching ? <Loader2 className="size-3 animate-spin" /> : <GlobeIcon className="size-3" />}
                    Fetch from the web
                  </Button>
                  <Button
                    size="xs"
                    variant="outline"
                    disabled={actionsDisabled}
                    onClick={() => setUploadMode('upload')}
                  >
                    <Upload className="size-3" />
                    Upload
                  </Button>
                </div>
              )}
            </div>
          )}
        </Section>

        {fetchRead && (
          <Section title="Web fetch">
            <div className="space-y-1.5 text-[12.5px] leading-relaxed">
              <p className={cn('font-medium', fetchRead.outcome.className)}>{fetchRead.outcome.label}</p>
              {fetchRead.detail && <p className="text-foreground/80">{fetchRead.detail}</p>}
              {fetchRead.sourceUrl && (
                <p className="min-w-0">
                  <span className="mr-1.5 font-mono text-[10px] text-muted-foreground uppercase">Source</span>
                  <a
                    href={fetchRead.sourceUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary break-all hover:underline"
                  >
                    {fetchRead.sourceUrl}
                  </a>
                </p>
              )}
              {fetchRead.reasoning && (
                <details className="group">
                  <summary className="inline-flex cursor-pointer list-none items-center gap-0.5 text-[11px] font-medium text-muted-foreground hover:text-foreground">
                    <ChevronRightIcon className="size-3 group-open:hidden" />
                    <ChevronDownIcon className="hidden size-3 group-open:inline" />
                    <span className="group-open:hidden">How we looked</span>
                    <span className="hidden group-open:inline">Hide how we looked</span>
                  </summary>
                  <div className="bg-muted/50 text-foreground/80 mt-1.5 rounded-md border p-2.5 text-[11.5px] leading-relaxed [&_p]:mb-1 [&_p:last-child]:mb-0">
                    <Markdown>{fetchRead.reasoning}</Markdown>
                  </div>
                </details>
              )}
            </div>
          </Section>
        )}
      </div>
    </div>
  );
}

function SourceLine({ source }: { source: MatchSource }) {
  const { icon: Icon, label } = SOURCE[source];
  return (
    <p className="mt-2 flex items-center gap-1.5 border-t pt-2 text-[11px] text-muted-foreground">
      <Icon className="size-3 shrink-0" />
      {label}
    </p>
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
