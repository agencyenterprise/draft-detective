'use client';

import { HelpLink } from '@/components/help/help-link';
import { formatFileSize } from '@/components/analysis-form/utils';
import { ReplaceMainDocumentDialog } from '@/components/results/components/replace-main-document-dialog';
import { FileUploadDialog } from '@/components/results/references/file-upload-dialog';
import { FileTypeIcon } from '@/components/shared/file-type-icon';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { useDownloadAllProjectFiles } from '@/hooks/use-download-all-project-files';
import { buildReferenceByFileIdMap, composeReferences } from '@/lib/composed-references';
import { FileListItem, FileRole, ProjectDetailed, WorkflowRunType } from '@/lib/generated-api';
import { RAIL_ITEM_ACTIVE, RAIL_ITEM_IDLE } from '@/lib/rail-style';
import { cn } from '@/lib/utils';
import { getWorkflowRunByType } from '@/lib/workflow-state';
import { Download, FileText, Loader2, Search, Upload } from 'lucide-react';
import { useMemo, useState } from 'react';
import { Rail, RailToggle, SidePane, useRailState } from '../panes';
import { FileDetail } from './file-detail';
import { FileGroup, GROUP, fileGroup, revisionLabel, sortFiles } from './role';

type Lens = 'all' | FileGroup;

interface FilesTabProps {
  projectDetail: ProjectDetailed;
  readOnly: boolean;
  onRevisionCreated?: () => void;
}

/**
 * Every file the project holds: a rail that narrows by kind,
 * a toolbar that acts on all of them, a table, and a detail pane for the one
 * you have selected.
 */
export function FilesTab({ projectDetail, readOnly, onRevisionCreated }: FilesTabProps) {
  const projectId = projectDetail.project.id;
  const currentRevision = projectDetail.project.current_revision ?? 1;
  const allFiles = useMemo(() => projectDetail.files ?? [], [projectDetail.files]);
  // Supporting candidates are a staging role the reference downloader uses
  // while it works, not files the project holds. The API already leaves them
  // out of projectDetail.files — get_project_files_list_items filters the role
  // in SQL — so this is belt and braces, and the tab's counts match the badge
  // in the header because both read this same list.
  const files = useMemo(() => allFiles.filter((file) => file.role !== FileRole.SupportingCandidate), [allFiles]);
  const workflowRuns = useMemo(() => projectDetail.workflow_runs ?? [], [projectDetail.workflow_runs]);

  const rail = useRailState();
  const [lens, setLens] = useState<Lens>('all');
  const [search, setSearch] = useState('');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [replaceOpen, setReplaceOpen] = useState(false);

  // Every role this table lists, not the hook's default of main and support:
  // memos are rows here too, and "Download all" would otherwise hand back a zip
  // quietly missing them.
  const { downloadAll, isDownloading } = useDownloadAllProjectFiles(projectId, [
    FileRole.Main,
    FileRole.Support,
    FileRole.ReviewerMemo,
    FileRole.ResponseMemo,
  ]);

  const referenceExtraction = getWorkflowRunByType(workflowRuns, WorkflowRunType.ReferenceExtraction);
  const referenceFileMatching = getWorkflowRunByType(workflowRuns, WorkflowRunType.ReferenceFileMatching);

  const referenceByFileId = useMemo(
    () =>
      buildReferenceByFileIdMap(
        composeReferences(
          referenceExtraction?.state?.extracted_references,
          referenceFileMatching?.state?.matches,
          allFiles,
        ),
      ),
    [referenceExtraction?.state?.extracted_references, referenceFileMatching?.state?.matches, allFiles],
  );

  const sorted = useMemo(() => sortFiles(files), [files]);

  const counts = useMemo(
    () => ({
      all: files.length,
      main: files.filter((file) => fileGroup(file.role) === 'main').length,
      source: files.filter((file) => fileGroup(file.role) === 'source').length,
      memo: files.filter((file) => fileGroup(file.role) === 'memo').length,
      response: files.filter((file) => fileGroup(file.role) === 'response').length,
    }),
    [files],
  );

  const shown = useMemo(() => {
    const query = search.trim().toLowerCase();
    return sorted.filter((file) => {
      if (lens !== 'all' && fileGroup(file.role) !== lens) return false;
      if (!query) return true;
      return (
        file.file_name?.toLowerCase().includes(query) ||
        file.description?.toLowerCase().includes(query) ||
        !!referenceByFileId.get(file.id)?.text?.toLowerCase().includes(query)
      );
    });
  }, [sorted, lens, search, referenceByFileId]);

  const filtered = lens !== 'all' || search.trim() !== '';
  // Looked up in the filtered list, so the pane never describes a hidden row.
  const selected = shown.find((file) => file.id === selectedId) ?? null;

  return (
    <div className="flex h-full min-h-0">
      <ReplaceMainDocumentDialog
        isOpen={replaceOpen}
        projectId={projectId}
        onClose={() => setReplaceOpen(false)}
        onRevisionCreated={onRevisionCreated}
      />
      <FileUploadDialog
        isOpen={uploadOpen}
        projectId={projectId}
        title="Add files"
        // Memos are added from the Peer Review tab, which explains the draft
        // each kind is tied to; this dialog adds source documents only.
        description="Add source documents to this project."
        multiple
        onCancel={() => setUploadOpen(false)}
        onComplete={() => setUploadOpen(false)}
      />

      <Rail state={rail} label="Filters">
        <KindRail
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
            {filtered ? `${shown.length} of ${counts.all} files` : `${counts.all} files`}
          </span>

          <div className="relative ml-2 hidden max-w-64 min-w-0 flex-1 sm:block">
            <Search className="absolute top-1/2 left-2 size-3.5 -translate-y-1/2 text-muted-foreground" />
            <Input
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search files and matched references"
              className="h-7 pl-7 text-xs"
            />
          </div>

          <div className="ml-auto flex shrink-0 items-center gap-1.5">
            {!readOnly && (
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button size="xs" variant="outline" onClick={() => setUploadOpen(true)}>
                    <Upload className="size-3" />
                    Add files
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Add source documents to this project</TooltipContent>
              </Tooltip>
            )}
            {counts.all > 0 && (
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button size="xs" variant="outline" disabled={isDownloading} onClick={() => downloadAll()}>
                    {isDownloading ? <Loader2 className="size-3 animate-spin" /> : <Download className="size-3" />}
                    {isDownloading ? 'Preparing zip…' : 'Download all'}
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Download every file in this project as a zip</TooltipContent>
              </Tooltip>
            )}
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto">
          {counts.all === 0 ? (
            <EmptyState />
          ) : shown.length === 0 ? (
            <div className="space-y-1 py-12 text-center text-sm text-muted-foreground">
              <p>No files match this view.</p>
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
            <table className="w-full table-fixed border-collapse text-sm">
              {/* Fixed layout: left to itself the file-name column takes the
                  whole width and pushes role, size and date off the pane. */}
              <thead>
                <tr className="border-b text-left font-mono text-[10px] tracking-wide text-muted-foreground uppercase">
                  <th className="bg-background sticky top-0 py-2 pl-4 font-normal">File</th>
                  <th className="bg-background sticky top-0 w-44 py-2 font-normal">Role</th>
                  <th className="bg-background sticky top-0 w-24 py-2 pr-4 text-right font-normal">Size</th>
                </tr>
              </thead>
              <tbody>
                {shown.map((file) => (
                  <FileRow
                    key={file.id}
                    file={file}
                    currentRevision={currentRevision}
                    matchedReferenceText={referenceByFileId.get(file.id)?.text}
                    active={file.id === selectedId}
                    onSelect={() => setSelectedId(file.id)}
                  />
                ))}
              </tbody>
            </table>
          )}
        </div>
      </main>

      {counts.all > 0 && (
        <SidePane
          open={selected !== null}
          onClose={() => setSelectedId(null)}
          label="File details"
          empty={
            <div className="flex h-full items-center justify-center p-8">
              <p className="max-w-56 text-center text-xs leading-relaxed text-muted-foreground">
                Select a file to see more details, download it or remove it.
              </p>
            </div>
          }
        >
          {selected && (
            <FileDetail
              key={selected.id}
              file={selected}
              projectId={projectId}
              currentRevision={currentRevision}
              matchedReference={referenceByFileId.get(selected.id)}
              readOnly={readOnly}
              onReplaceMain={() => setReplaceOpen(true)}
            />
          )}
        </SidePane>
      )}
    </div>
  );
}

function FileRow({
  file,
  currentRevision,
  matchedReferenceText,
  active,
  onSelect,
}: {
  file: FileListItem;
  currentRevision: number;
  matchedReferenceText?: string;
  active: boolean;
  onSelect: () => void;
}) {
  const group = fileGroup(file.role);
  const revision = revisionLabel(file, currentRevision);
  const superseded = group === 'main' && file.revision !== currentRevision;

  return (
    // The row keeps its own role: overriding it with `button` leaves the cells
    // without a row parent in the accessibility tree. Clicking anywhere is a
    // convenience; the file name is the real control, and the one keyboards and
    // screen readers reach.
    <tr
      onClick={onSelect}
      className={cn(
        'cursor-pointer border-b transition-colors',
        active
          ? 'bg-accent [&>td:first-child]:before:bg-primary [&>td:first-child]:relative [&>td:first-child]:before:absolute [&>td:first-child]:before:inset-y-0 [&>td:first-child]:before:left-0 [&>td:first-child]:before:w-0.5'
          : 'hover:bg-accent/40',
      )}
    >
      <td className="py-2.5 pl-4">
        <button
          type="button"
          aria-pressed={active}
          onClick={(event) => {
            // The row handles it; without this the click would select twice.
            event.stopPropagation();
            onSelect();
          }}
          className="flex w-full min-w-0 cursor-pointer items-center gap-2 text-left"
        >
          <FileTypeIcon fileType={file.file_type} className="size-3.5 shrink-0 text-muted-foreground" />
          <span className={cn('truncate text-[13px]', superseded && 'text-muted-foreground')}>{file.file_name}</span>
        </button>
        {matchedReferenceText && (
          <span className="mt-0.5 ml-[1.375rem] block truncate text-[11.5px] text-muted-foreground">
            {matchedReferenceText}
          </span>
        )}
      </td>
      <td className="py-2.5">
        <span className={cn('inline-flex flex-col rounded-md px-2 py-0.5 leading-tight', GROUP[group].className)}>
          <span className="text-[11px] font-semibold">{GROUP[group].label}</span>
          {revision && <span className="text-[10px] font-medium opacity-70">{revision}</span>}
        </span>
      </td>
      <td className="py-2.5 pr-4 text-right font-mono text-[11.5px] tabular-nums text-muted-foreground">
        {formatFileSize(file.file_size)}
      </td>
    </tr>
  );
}

const LENSES: { id: Lens; label: string }[] = [
  { id: 'all', label: 'All files' },
  { id: 'main', label: GROUP.main.plural },
  { id: 'source', label: GROUP.source.plural },
  { id: 'memo', label: GROUP.memo.plural },
  { id: 'response', label: GROUP.response.plural },
];

function KindRail({
  lens,
  onLensChange,
  counts,
}: {
  lens: Lens;
  onLensChange: (lens: Lens) => void;
  counts: Record<Lens, number>;
}) {
  return (
    <div className="flex h-full flex-col">
      <div className="min-h-0 flex-1 overflow-y-auto p-3">
        <div className="flex items-center justify-between px-2">
          <h2 className="font-mono text-[10px] tracking-wide text-muted-foreground uppercase">Filter files</h2>
          {lens !== 'all' && (
            <Button variant="link" size="sm" className="h-auto p-0 text-xs" onClick={() => onLensChange('all')}>
              Clear
            </Button>
          )}
        </div>
        <div className="mt-2 space-y-px">
          {LENSES.map((entry) => {
            const count = counts[entry.id];
            if (entry.id !== 'all' && count === 0) return null;
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
        Every file this project holds: the draft under review and the source documents behind its references.
        Assessments read these files. <HelpLink topic="source-files">More details</HelpLink>
      </p>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="flex h-full items-center justify-center p-8">
      <div className="max-w-sm space-y-2 text-center">
        <FileText className="mx-auto size-7 text-muted-foreground" />
        <p className="text-sm font-medium">No files yet</p>
        <p className="text-xs leading-relaxed text-muted-foreground">
          The main document and any sources you provide will be listed here.
        </p>
      </div>
    </div>
  );
}
