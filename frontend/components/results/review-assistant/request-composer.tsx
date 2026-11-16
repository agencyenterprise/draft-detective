'use client';

import { FileListItem as StagedFile } from '@/components/analysis-form/file-list-item';
import { Button } from '@/components/ui/button';
import { FileUpload } from '@/components/ui/file-upload';
import { UploadProgressList } from '@/components/ui/upload-progress-list';
import {
  FileRole,
  listProjectFilesEndpointApiProjectProjectIdFilesGet,
  ProjectOverview,
  ReviewAssistantOutput,
} from '@/lib/generated-api';
import { useUpload } from '@/lib/hooks/upload';
import { cn } from '@/lib/utils';
import { Check, Loader2, Sparkles } from 'lucide-react';
import { useRef, useState } from 'react';
import { toast } from 'sonner';
import { DOCUMENT_KINDS, OUTPUTS } from './outputs';
import { ProjectFilePicker } from './project-file-picker';
import { inSentOrder, matchUploads, UploadRow } from './uploaded-files';
import { useStartReviewAssistantRequest } from './use-review-assistant';

interface RequestComposerProps {
  overview: ProjectOverview;
  onStarted: (runId: string) => void;
}

type Phase = 'idle' | 'uploading' | 'starting';

const listFiles = (projectId: string) =>
  listProjectFilesEndpointApiProjectProjectIdFilesGet({ path: { project_id: projectId } });

/** Pick the outputs, hand over the documents, generate. Nothing to label. */
export function RequestComposer({ overview, onStarted }: RequestComposerProps) {
  const projectId = overview.project.id;
  const [outputs, setOutputs] = useState<Set<ReviewAssistantOutput>>(new Set());
  const [staged, setStaged] = useState<File[]>([]);
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [phase, setPhase] = useState<Phase>('idle');
  const filesBeforeUpload = useRef<Set<string>>(new Set());
  const failedUploads = useRef(0);
  const cancelledUploads = useRef(0);
  const sentCount = useRef(0);
  // The staged files whose upload finished, in the order they finished.
  const finished = useRef<File[]>([]);

  const start = useStartReviewAssistantRequest(projectId);

  /**
   * Files that are now in the project leave the staged list and are ticked
   * under "Already in this project" instead, so trying again never uploads
   * them twice.
   */
  const keepUploaded = (matched: Map<File, UploadRow>) => {
    setPicked((prev) => new Set([...prev, ...[...matched.values()].map((row) => row.id)]));
    setStaged((prev) => prev.filter((file) => !matched.has(file)));
  };

  /** What the upload created for each finished file, read back from the project. */
  const readUploads = async () => matchUploads(finished.current, filesBeforeUpload.current, await listFiles(projectId));

  const submit = (matched: Map<File, UploadRow>) => {
    const uploaded = inSentOrder(staged, matched);
    setPhase('starting');
    const newFileIds = uploaded.map((file) => file.id);
    // Order: the documents as the author added them, then the ones they picked.
    const fileIds = [...newFileIds, ...[...picked].filter((id) => !newFileIds.includes(id))];
    start.mutate(
      { outputs: OUTPUTS.map((o) => o.id).filter((id) => outputs.has(id)), fileIds },
      {
        onSuccess: (response) => onStarted(response.workflow_run_id),
        onError: () => keepUploaded(matched),
        onSettled: () => setPhase('idle'),
      },
    );
  };

  /**
   * Some files did not upload, because they failed or were cancelled. Starting
   * anyway would read fewer documents than the author gave, and the reports
   * would not say so. So nothing starts: the files that made it are kept, and
   * the rest stay staged to retry or remove.
   */
  const holdAfterPartialUpload = (matched: Map<File, UploadRow>) => {
    keepUploaded(matched);
    setPhase('idle');
    const missing = sentCount.current - matched.size;
    toast.error(
      `${missing} of ${sentCount.current} files did not upload, so nothing was started. Retry them or remove them, then generate again.`,
    );
  };

  /** Every file sent has failed or been cancelled, and none is left to finish. */
  const settleIfNothingLeft = () => {
    if (failedUploads.current + cancelledUploads.current >= sentCount.current) setPhase('idle');
  };

  const upload = useUpload({
    projectId,
    fileRole: FileRole.ReviewInput,
    onFileComplete: (file) => {
      finished.current.push(file);
    },
    onError: () => {
      failedUploads.current += 1;
      // The upload reports no completion when nothing succeeded.
      settleIfNothingLeft();
    },
    onAllComplete: async () => {
      try {
        const matched = await readUploads();
        if (matched.size < sentCount.current) return holdAfterPartialUpload(matched);
        submit(matched);
      } catch {
        toast.error(
          'The files uploaded, but the request could not be started. Pick them from the project and try again.',
        );
        setPhase('idle');
      }
    },
  });

  /** Stops the rest; any file that already finished is kept, as on a partial failure. */
  const cancelAll = async () => {
    upload.cancelAll();
    setPhase('idle');
    try {
      keepUploaded(await readUploads());
    } catch {
      // Nothing lost: a finished file is still in the project to pick by hand.
    }
  };

  const cancelFile = (fileId: string) => {
    upload.removeFile(fileId);
    cancelledUploads.current += 1;
    settleIfNothingLeft();
  };

  const documentCount = staged.length + picked.size;
  const busy = phase !== 'idle';
  const canGenerate = outputs.size > 0 && documentCount > 0 && !busy;

  const generate = async () => {
    if (staged.length === 0) return submit(new Map());
    setPhase('uploading');
    try {
      // Read now rather than from the overview, which may be minutes old.
      filesBeforeUpload.current = new Set((await listFiles(projectId)).map((file) => file.id));
    } catch {
      toast.error('Could not read the project files. Try again.');
      return setPhase('idle');
    }
    failedUploads.current = 0;
    finished.current = [];
    cancelledUploads.current = 0;
    sentCount.current = staged.length;
    upload.reset();
    upload.startUpload(staged);
  };

  const toggle = <T,>(set: Set<T>, value: T) => {
    const next = new Set(set);
    if (next.has(value)) next.delete(value);
    else next.add(value);
    return next;
  };

  return (
    <div className="space-y-8">
      <section>
        <SectionHeading
          step={1}
          title="What do you need?"
          hint="Pick any. They are written together, from one reading of your documents."
        />
        <div className="mt-3 grid gap-2 sm:grid-cols-3">
          {OUTPUTS.map((output) => {
            const on = outputs.has(output.id);
            const Icon = output.icon;
            return (
              <button
                key={output.id}
                type="button"
                aria-pressed={on}
                disabled={busy}
                onClick={() => setOutputs((prev) => toggle(prev, output.id))}
                className={cn(
                  'relative flex cursor-pointer flex-col gap-1.5 rounded-lg border p-3.5 text-left transition-colors disabled:cursor-not-allowed',
                  on ? 'border-primary bg-primary/5 ring-1 ring-primary' : 'hover:bg-accent/40',
                )}
              >
                <span className="flex items-center gap-2">
                  <Icon className="size-4 text-muted-foreground" />
                  <span className="text-[13px] font-medium">{output.title}</span>
                  {on && <Check className="ml-auto size-3.5 text-primary" />}
                </span>
                <span className="text-xs leading-relaxed text-muted-foreground">{output.description}</span>
                <span className="mt-auto pt-1 text-[11px] leading-snug text-muted-foreground/80">
                  Reads: {output.needs.toLowerCase()}
                </span>
              </button>
            );
          })}
        </div>
      </section>

      <section>
        <SectionHeading
          step={2}
          title="Add your drafts, memos and marked-up copies"
          hint="Any of the documents below, in any order. No need to say which is which: the Review Assistant works it out."
        />
        <dl className="mt-3 grid gap-x-6 gap-y-2.5 rounded-md bg-muted/50 px-4 py-3 sm:grid-cols-2">
          {DOCUMENT_KINDS.map((kind) => (
            <div key={kind.name}>
              <dt className="text-xs font-medium">{kind.name}</dt>
              <dd className="mt-0.5 text-xs leading-relaxed text-muted-foreground">{kind.description}</dd>
            </div>
          ))}
        </dl>
        <div className="mt-3 grid gap-6 lg:grid-cols-2">
          <div className="space-y-2">
            <p className="text-xs font-medium">Already in this project</p>
            <div className="max-h-80 overflow-y-auto rounded-md border p-3">
              <ProjectFilePicker
                files={overview.files ?? []}
                currentRevision={overview.project.current_revision ?? 1}
                selected={picked}
                onToggle={(id) => setPicked((prev) => toggle(prev, id))}
                disabled={busy}
              />
            </div>
          </div>

          <div className="space-y-2">
            <p className="text-xs font-medium">New files</p>
            {phase === 'uploading' ? (
              <UploadProgressList
                files={upload.files}
                overallProgress={upload.overallProgress}
                completedCount={upload.completedCount}
                totalCount={upload.totalCount}
                onCancelFile={cancelFile}
                onPauseFile={upload.pauseFile}
                onResumeFile={upload.resumeFile}
                onCancelAll={cancelAll}
                onPauseAll={upload.pauseAll}
                onResumeAll={upload.resumeAll}
              />
            ) : (
              <>
                <FileUpload
                  files={staged}
                  onFilesChange={setStaged}
                  accept=".pdf,.doc,.docx,.txt,.md"
                  multiple
                  maxSize={500}
                  className="h-32"
                  disabled={busy}
                  compact
                />
                {staged.length > 0 && (
                  <div className="space-y-1">
                    {staged.map((file, index) => (
                      <StagedFile
                        key={`${file.name}-${file.size}-${file.lastModified}`}
                        file={file}
                        type={FileRole.ReviewInput}
                        onRemove={() => setStaged((prev) => prev.filter((_, i) => i !== index))}
                      />
                    ))}
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </section>

      <div className="flex flex-wrap items-center gap-3 border-t pt-5">
        <Button onClick={generate} disabled={!canGenerate}>
          {busy ? <Loader2 className="size-4 animate-spin" /> : <Sparkles className="size-4" />}
          {phase === 'uploading' ? 'Uploading…' : phase === 'starting' ? 'Starting…' : 'Generate'}
        </Button>
        <span className="text-xs text-muted-foreground">{summaryLine(outputs.size, documentCount)}</span>
      </div>
    </div>
  );
}

function summaryLine(outputCount: number, documentCount: number): string {
  if (outputCount === 0) return 'Pick at least one output.';
  if (documentCount === 0) return 'Add or pick at least one document.';
  const outputs = `${outputCount} output${outputCount === 1 ? '' : 's'}`;
  const documents = `${documentCount} document${documentCount === 1 ? '' : 's'}`;
  return `${outputs} from ${documents}.`;
}

/**
 * Numbered, so the two sections read as two halves of one request. Where there
 * is room the number hangs in the margin, keeping the title, hint and the
 * cards below on one left edge; on a phone it sits inline.
 */
function SectionHeading({ step, title, hint }: { step: number; title: string; hint: string }) {
  return (
    <header>
      <h2 className="relative flex items-center gap-2 text-sm font-semibold">
        <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-primary text-[11px] font-semibold text-primary-foreground tabular-nums md:absolute md:top-1/2 md:-left-8 md:-translate-y-1/2">
          {step}
        </span>
        {title}
      </h2>
      <p className="mt-1 pl-7 text-[13px] leading-relaxed text-muted-foreground md:pl-0">{hint}</p>
    </header>
  );
}
