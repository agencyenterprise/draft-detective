'use client';

import { CopyReferencesDialog } from '@/components/references/copy-references-dialog';
import { useFetchAllFromWebMutation } from '@/components/results/references/mutations';
import { useReferenceReviewReferences } from '@/components/results/references/queries';
import { ReferenceReviewStatus } from '@/components/results/references/types';
import { HelpLink } from '@/components/help/help-link';
import { UnmatchedReferencesApproveDialog } from '@/components/results/references/unmatched-references-approve-dialog';
import { useReferenceApprovalFlow } from '@/components/results/references/use-reference-approval-flow';
import { useScrollToReference } from '@/components/results/references/use-scroll-to-reference';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Input } from '@/components/ui/input';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { WorkflowConfigDialog } from '@/components/workflows/workflow-config-dialog';
import { useDownloadAllProjectFiles } from '@/hooks/use-download-all-project-files';
import { FileRole, ProjectOverview, WorkflowRunType } from '@/lib/generated-api';
import { RAIL_ITEM_ACTIVE, RAIL_ITEM_IDLE } from '@/lib/rail-style';
import { cn } from '@/lib/utils';
import { findRunByType, isWorkflowProcessing } from '@/lib/workflow-state';
import { Copy, Download, FileText, GlobeIcon, Loader2, MoreHorizontal, Search, Upload } from 'lucide-react';
import { useMemo, useState } from 'react';
import { FileUploadDialog } from '@/components/results/references/file-upload-dialog';
import { Rail, RailToggle, SidePane, useRailState } from '../panes';
import { TabError, TabLoading } from '../tab-status';
import { ReferenceDetail } from './reference-detail';
import { ReferenceRow } from './reference-row';

type Lens = 'all' | ReferenceReviewStatus;

interface ReferencesTabProps {
  overview: ProjectOverview;
  readOnly: boolean;
}

/**
 * The references tab: a rail that narrows the list, a toolbar
 * that acts on all of it, and one flat row per reference. The right-hand
 * evidence pane the mock carried is gone — reference validation reports its
 * findings as issues in the document explorer, so a second place to read them
 * would only be a second place to keep in sync.
 */
export function ReferencesTab({ overview, readOnly }: ReferencesTabProps) {
  const projectId = overview.project.id;
  const workflowRuns = useMemo(() => overview.workflow_runs ?? [], [overview.workflow_runs]);

  const rail = useRailState();
  const [lens, setLens] = useState<Lens>('all');
  const [search, setSearch] = useState('');
  const [copyOpen, setCopyOpen] = useState(false);
  const [fetchAllOpen, setFetchAllOpen] = useState(false);
  const [batchUploadOpen, setBatchUploadOpen] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  useScrollToReference();

  const { references, isLoading: isLoadingReferences, error: referencesError } = useReferenceReviewReferences(overview);
  const approval = useReferenceApprovalFlow(overview);
  const fetchAll = useFetchAllFromWebMutation(projectId);
  const { downloadAll, isDownloading } = useDownloadAllProjectFiles(projectId, [FileRole.Support]);

  const referenceExtraction = findRunByType(workflowRuns, WorkflowRunType.ReferenceExtraction);
  const referenceDownloader = findRunByType(workflowRuns, WorkflowRunType.ReferenceDownloader);
  const isExtracting = isWorkflowProcessing(referenceExtraction);
  const isFetchingAll = fetchAll.isPending || isWorkflowProcessing(referenceDownloader);
  const isProcessingFiles = approval.isProcessingFiles;

  const counts = useMemo(
    () => ({
      all: references.length,
      unmatched: references.filter((r) => r.status === 'unmatched').length,
      matched: references.filter((r) => r.status === 'matched').length,
      fetching: references.filter((r) => r.status === 'fetching').length,
      withFile: references.filter((r) => r.matchedFile).length,
    }),
    [references],
  );

  // What the zip will actually hold. Counting matched references instead reports
  // a different number: a source can sit in the project without any reference
  // claiming it, and the download asks the API for the role, not for the matches.
  const sourceFileCount = useMemo(
    () => (overview.files ?? []).filter((file) => file.role === FileRole.Support).length,
    [overview.files],
  );

  const shown = useMemo(() => {
    const query = search.trim().toLowerCase();
    return references.filter((reference) => {
      if (lens !== 'all' && reference.status !== lens) return false;
      if (!query) return true;
      return (
        reference.text?.toLowerCase().includes(query) || !!reference.matchedFile?.name.toLowerCase().includes(query)
      );
    });
  }, [references, lens, search]);

  const filtered = lens !== 'all' || search.trim() !== '';
  // Looked up in the filtered list, not all of them: a pane describing a row
  // the filter has hidden is a pane pointing at nothing. The id is kept, so
  // clearing the filter brings the selection back.
  const selected = shown.find((reference) => reference.id === selectedId) ?? null;

  if (isExtracting) {
    return <ExtractingState />;
  }

  if (isLoadingReferences) {
    return <TabLoading label="Loading references..." />;
  }

  if (referencesError) {
    return <TabError what="the references" error={referencesError} />;
  }

  const handleFetchAllConfirm = () => {
    const unmatched = references
      .filter((reference) => reference.status === 'unmatched')
      .map((reference) => ({ reference_id: reference.id, text: reference.text }));
    fetchAll.mutate({ references: unmatched }, { onSuccess: () => setFetchAllOpen(false) });
  };

  return (
    <div className="flex h-full min-h-0">
      <WorkflowConfigDialog
        isOpen={fetchAllOpen}
        type={WorkflowRunType.ReferenceDownloader}
        title="Fetch source files from the web"
        description="Draft Detective searches for each reference without a source file and downloads the full text when it finds one it can read."
        helpTopic="source-files"
        submitLabel="Fetch sources"
        projectId={projectId}
        onConfirm={handleFetchAllConfirm}
        onCancel={() => setFetchAllOpen(false)}
      />
      <FileUploadDialog
        isOpen={batchUploadOpen}
        title="Upload source documents"
        description="Upload as many sources as you like. We process each one and match it to the reference it belongs to."
        multiple
        projectId={projectId}
        onCancel={() => setBatchUploadOpen(false)}
        onComplete={() => setBatchUploadOpen(false)}
      />
      <CopyReferencesDialog
        references={references.map((reference) => reference.text)}
        open={copyOpen}
        onOpenChange={setCopyOpen}
      />
      <UnmatchedReferencesApproveDialog
        open={approval.showUnmatchedWarning}
        onOpenChange={approval.setShowUnmatchedWarning}
        unmatchedCount={approval.unmatchedCount}
        onConfirmApprove={approval.handleConfirmApprove}
      />

      <Rail state={rail} label="Filters">
        <LensRail
          lens={lens}
          onLensChange={(next) => {
            setLens(next);
            rail.close();
          }}
          counts={counts}
        />
      </Rail>

      <main className="flex min-w-0 flex-1 flex-col">
        <div className="flex h-10 shrink-0 items-center gap-2 border-b px-2">
          <RailToggle state={rail} label="Filters" />

          <span className="shrink-0 truncate text-xs text-muted-foreground">
            {filtered ? `${shown.length} of ${counts.all} references` : `${counts.all} references`}
          </span>

          <div className="relative ml-2 hidden max-w-64 min-w-0 flex-1 sm:block">
            <Search className="absolute top-1/2 left-2 size-3.5 -translate-y-1/2 text-muted-foreground" />
            <Input
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search references and files"
              className="h-7 pl-7 text-xs"
            />
          </div>

          {!readOnly && (
            <div className="ml-auto flex shrink-0 items-center gap-1.5">
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    size="xs"
                    variant="outline"
                    aria-label="Fetch all missing"
                    disabled={isFetchingAll || isProcessingFiles || counts.unmatched === 0}
                    onClick={() => setFetchAllOpen(true)}
                  >
                    {isFetchingAll ? <Loader2 className="size-3 animate-spin" /> : <GlobeIcon className="size-3" />}
                    {/* Labels give way below sm: this row needs 430px of them,
                        which is wider than the phone it sits on. */}
                    <span className="hidden sm:inline">Fetch all missing</span>
                  </Button>
                </TooltipTrigger>
                <TooltipContent>
                  {counts.unmatched === 0
                    ? 'Every reference already has a source file'
                    : 'Search the web for the source files not provided yet'}
                </TooltipContent>
              </Tooltip>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    size="xs"
                    variant="outline"
                    aria-label="Upload sources"
                    disabled={isProcessingFiles}
                    onClick={() => setBatchUploadOpen(true)}
                  >
                    <Upload className="size-3" />
                    <span className="hidden sm:inline">Upload sources</span>
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Upload source files, and we match each one to its reference</TooltipContent>
              </Tooltip>
              <DropdownMenu>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <DropdownMenuTrigger asChild>
                      <Button size="icon" variant="ghost" className="size-7" aria-label="More reference actions">
                        <MoreHorizontal className="size-4" />
                      </Button>
                    </DropdownMenuTrigger>
                  </TooltipTrigger>
                  <TooltipContent>More options</TooltipContent>
                </Tooltip>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem onSelect={() => setCopyOpen(true)}>
                    <Copy className="size-4" />
                    Copy all references
                  </DropdownMenuItem>
                  <DropdownMenuItem onSelect={() => downloadAll()} disabled={sourceFileCount === 0 || isDownloading}>
                    {isDownloading ? <Loader2 className="size-4 animate-spin" /> : <Download className="size-4" />}
                    {isDownloading
                      ? 'Preparing zip…'
                      : `Download ${sourceFileCount} source file${sourceFileCount === 1 ? '' : 's'} (.zip)`}
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          )}
        </div>

        {approval.hasPendingApproval && !readOnly && (
          <div className="flex shrink-0 items-center gap-3 border-b px-4 py-2.5">
            <span className="min-w-0 flex-1 text-sm">
              {counts.unmatched > 0 ? (
                <>
                  <strong className="font-medium">
                    {counts.unmatched} reference{counts.unmatched === 1 ? ' has' : 's have'} no source file provided.
                  </strong>{' '}
                  <span className="text-muted-foreground">
                    Claim Reference Validation will mark {counts.unmatched === 1 ? 'its claims' : 'their claims'}{' '}
                    unverifiable.
                  </span>
                </>
              ) : (
                <span className="text-muted-foreground">Every reference has its source file. Ready when you are.</span>
              )}
            </span>
            <Button
              size="sm"
              className="h-7 shrink-0"
              onClick={approval.handleApprove}
              disabled={approval.isApproveDisabled}
            >
              {approval.showApproveButtonSpinner && <Loader2 className="size-3 animate-spin" />}
              {approval.approveButtonText}
            </Button>
          </div>
        )}

        {isProcessingFiles && (
          <div className="flex shrink-0 items-center gap-2 border-b bg-blue-50 px-4 py-2 text-xs dark:bg-blue-950/30">
            <Loader2 className="size-3.5 shrink-0 animate-spin text-blue-700 dark:text-blue-400" />
            <span>
              <strong className="font-medium">Processing your source files.</strong>{' '}
              <span className="text-muted-foreground">
                We are indexing them and matching them to references — usually a minute or two.
              </span>
            </span>
          </div>
        )}

        <div className="min-h-0 flex-1 overflow-y-auto">
          {references.length === 0 ? (
            <EmptyState />
          ) : shown.length === 0 ? (
            <div className="space-y-1 py-12 text-center text-sm text-muted-foreground">
              <p>No references match this view.</p>
              <Button
                variant="link"
                size="sm"
                className="text-xs"
                onClick={() => {
                  setLens('all');
                  setSearch('');
                }}
              >
                Clear filters
              </Button>
            </div>
          ) : (
            <div className="divide-y">
              {shown.map((reference) => (
                <ReferenceRow
                  key={reference.id}
                  reference={reference}
                  active={reference.id === selectedId}
                  onSelect={() => setSelectedId(reference.id)}
                />
              ))}
            </div>
          )}
        </div>
      </main>

      {references.length > 0 && (
        <SidePane
          open={selected !== null}
          onClose={() => setSelectedId(null)}
          label="Reference details"
          empty={
            <div className="flex h-full items-center justify-center p-8">
              <p className="max-w-56 text-center text-xs leading-relaxed text-muted-foreground">
                Select a reference to see more details, provide or replace a source file.
              </p>
            </div>
          }
        >
          {selected && (
            <ReferenceDetail
              key={selected.id}
              reference={selected}
              projectId={projectId}
              readOnly={readOnly}
              disabled={approval.isProcessingFiles}
            />
          )}
        </SidePane>
      )}
    </div>
  );
}

const LENSES: { id: Lens; label: string; countKey: 'all' | 'unmatched' | 'matched' | 'fetching' }[] = [
  { id: 'all', label: 'All references', countKey: 'all' },
  { id: 'unmatched', label: 'Source file not provided', countKey: 'unmatched' },
  { id: 'matched', label: 'Source file provided', countKey: 'matched' },
  { id: 'fetching', label: 'Fetching', countKey: 'fetching' },
];

function LensRail({
  lens,
  onLensChange,
  counts,
}: {
  lens: Lens;
  onLensChange: (lens: Lens) => void;
  counts: Record<'all' | 'unmatched' | 'matched' | 'fetching' | 'withFile', number>;
}) {
  return (
    <div className="flex h-full flex-col">
      <div className="min-h-0 flex-1 overflow-y-auto p-3">
        <div className="flex items-center justify-between px-2">
          <h2 className="font-mono text-[10px] tracking-wide text-muted-foreground uppercase">Filter references</h2>
          {lens !== 'all' && (
            <Button variant="link" size="sm" className="h-auto p-0 text-xs" onClick={() => onLensChange('all')}>
              Clear
            </Button>
          )}
        </div>
        <div className="mt-2 space-y-px">
          {LENSES.map((entry) => {
            const count = counts[entry.countKey];
            if (entry.id === 'fetching' && count === 0) return null;
            return (
              <button
                key={entry.id}
                onClick={() => onLensChange(entry.id)}
                aria-pressed={lens === entry.id}
                className={cn(
                  'flex w-full cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm transition-colors',
                  lens === entry.id ? RAIL_ITEM_ACTIVE : RAIL_ITEM_IDLE,
                )}
              >
                <span className="flex-1 truncate">{entry.label}</span>
                <span className="font-mono text-[11px] tabular-nums text-muted-foreground">{count}</span>
              </button>
            );
          })}
        </div>
      </div>

      <p className="shrink-0 border-t px-5 py-4 text-xs leading-relaxed text-muted-foreground">
        Some assessments — Claim Reference Validation among them — read the original source documents behind your
        bibliographic references. <HelpLink topic="source-files">More details</HelpLink>
      </p>
    </div>
  );
}

function ExtractingState() {
  return (
    <div className="flex h-full items-center justify-center p-8">
      <div className="max-w-sm space-y-2 text-center">
        <Loader2 className="text-primary mx-auto size-7 animate-spin" />
        <p className="text-sm font-medium">Finding references in your document</p>
        <p className="text-xs leading-relaxed text-muted-foreground">
          Usually two to ten minutes, depending on how long the document is. You can leave this page — we keep working.
        </p>
      </div>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="flex h-full items-center justify-center p-8">
      <div className="max-w-sm space-y-2 text-center">
        <FileText className="mx-auto size-7 text-muted-foreground" />
        <p className="text-sm font-medium">No references found</p>
        <p className="text-xs leading-relaxed text-muted-foreground">
          We did not find a bibliography in this document. Assessments that read sources have nothing to check against.
        </p>
      </div>
    </div>
  );
}
