import { EditProjectDialog, EditProjectFormValues } from '@/components/projects/edit-project-dialog';
import { ShareDialog } from '@/components/share/share-dialog';
import { ShareStatusBadge } from '@/components/share/share-status-badge';
import { ShareWarningDialog } from '@/components/share/share-warning-dialog';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { useShare } from '@/context/share-context';
import { useShareStatus } from '@/hooks/use-share-status';
import {
  Project,
  updateProjectEndpointApiProjectProjectIdPatch,
  WorkflowRunDetail,
  WorkflowRunType,
  Issue,
} from '@/lib/generated-api';
import { useDocumentExplorerStore } from '@/lib/stores/document-explorer-store';
import { cn } from '@/lib/utils';
import { getWorkflowRunByType } from '@/lib/workflow-state';
import { getErrorMessage } from '@/lib/api-error';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Download, EllipsisVerticalIcon, Link, Pencil, Plus } from 'lucide-react';
import { useState } from 'react';
import { toast } from 'sonner';
import { downloadDocxFile, DocxType, useDownloadDocx } from './use-download-docx';
import { exportCounts, shareLinksAvailable } from '@/lib/export-scope';
import { ReplaceMainDocumentDialog } from './replace-main-document-dialog';
import { RevisionSwitcher } from './revision-switcher';

type ProjectWithDetails = Project & {
  publication_date?: Date | null;
};

export interface AnalysisOptionsMenuProps {
  project: ProjectWithDetails;
  results: WorkflowRunDetail[];
  /** The project's issues, for the export dialog's counts. */
  issues: Issue[];
  readOnly: boolean;
  selectedRevision?: number;
  onRevisionChange?: (revision: number) => void;
  onRevisionCreated?: () => void;
  /** Label for the download button. */
  downloadLabel?: string;
  /** Drops the download button to secondary where another action leads the row. */
  downloadVariant?: 'default' | 'outline';
  /**
   * Labels give way to icons on narrow screens. For headers that carry other
   * controls beside this one and would otherwise run off a phone screen.
   */
  compact?: boolean;
}

export function AnalysisOptionsMenu({
  project,
  results,
  issues,
  readOnly,
  selectedRevision,
  onRevisionChange,
  onRevisionCreated,
  downloadLabel = 'Download DOCX',
  downloadVariant = 'default',
  compact = false,
}: AnalysisOptionsMenuProps) {
  const { filter } = useDocumentExplorerStore();
  const projectId = project.id;
  const share = useShareStatus(projectId, !readOnly);
  const shareContext = useShare();
  const queryClient = useQueryClient();

  const [showShareWarning, setShowShareWarning] = useState(false);
  const [isEnablingForDownload, setIsEnablingForDownload] = useState(false);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
  const [isReplaceDialogOpen, setIsReplaceDialogOpen] = useState(false);

  const shareToken = share.shareStatus?.share_link?.token ?? shareContext.shareToken;
  // The dialog's counts come from the revision on screen, so the export has to
  // come from the same one rather than from whatever the latest revision is.
  const { download, isDownloading } = useDownloadDocx({
    projectId,
    shareToken,
    severities: filter.severity,
    workflowTypes: filter.workflowType,
    includePassing: filter.showPassing,
    revision: selectedRevision,
  });

  const documentProcessing = getWorkflowRunByType(results, WorkflowRunType.DocumentProcessing);
  const mainFilePath = documentProcessing?.state?.file?.file_path.toLowerCase() ?? '';
  const hasDocx = mainFilePath.endsWith('.docx') || mainFilePath.endsWith('.doc');

  const updateProjectMutation = useMutation({
    mutationFn: async (values: EditProjectFormValues) => {
      return await updateProjectEndpointApiProjectProjectIdPatch({
        path: { project_id: projectId },
        body: {
          title: values.title,
          publication_date: values.publication_date ? new Date(values.publication_date) : null,
          feedback_visibility: values.feedback_visibility ?? undefined,
        },
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['project', projectId] });
      setIsEditDialogOpen(false);
      toast.success('Project details updated successfully');
    },
    onError: (error) => {
      toast.error(`Failed to update project: ${getErrorMessage(error, 'Unknown error')}`);
    },
  });

  const downloadWithShare = async (docxType: DocxType, includeEdits: boolean) => {
    setIsEnablingForDownload(true);
    const toastId = toast.loading('Preparing DOCX with share links...', { description: 'This may take a few moments' });

    try {
      const shareResponse = await share.enable();
      const token = shareResponse?.share_link?.token;
      if (!token) throw new Error('Failed to create share token');

      await downloadDocxFile({
        projectId,
        shareToken: token,
        severities: filter.severity,
        workflowTypes: filter.workflowType,
        docxType,
        includePassing: filter.showPassing,
        includeEdits,
        revision: selectedRevision,
      });
      toast.success('DOCX file downloaded successfully', { id: toastId });
    } catch (error) {
      console.error('Failed to enable sharing and download:', error);
      toast.error('Failed to download DOCX file', { id: toastId });
    } finally {
      setIsEnablingForDownload(false);
    }
  };

  // Execute the actual download based on pending action
  const executeDownload = (docxType: DocxType, includeEdits: boolean) => {
    const notShared = !share.isEnabled && !shareContext.shareToken;
    const needsShare = docxType === 'add-in' || docxType === 'comments-with-links';
    if (needsShare && notShared) {
      downloadWithShare(docxType, includeEdits);
    } else {
      download(docxType, includeEdits);
    }
  };

  const handleDownloadClick = () => {
    setShowShareWarning(true);
  };

  return (
    <>
      <div className="flex items-center gap-1">
        <div className="flex items-center gap-2">
          {!readOnly && (
            <ShareStatusBadge
              isEnabled={share.isEnabled}
              onClick={() => share.setIsDialogOpen(true)}
              compact={compact}
            />
          )}

          <Tooltip>
            <TooltipTrigger asChild>
              {/* Wrapper span so the tooltip still fires while the button is disabled */}
              <span tabIndex={0}>
                <Button
                  variant={downloadVariant}
                  size="xs"
                  onClick={handleDownloadClick}
                  disabled={!hasDocx || isDownloading}
                  aria-label={downloadLabel}
                >
                  <Download />
                  <span className={cn(compact && 'hidden sm:inline')}>
                    {isDownloading ? 'Downloading...' : downloadLabel}
                  </span>
                </Button>
              </span>
            </TooltipTrigger>
            <TooltipContent>
              {hasDocx
                ? 'Download the original Word document with the analysis results (issues and suggested edits) added as comments'
                : 'DOCX export is only available when the source document is a Word file (.docx or .doc)'}
            </TooltipContent>
          </Tooltip>

          {selectedRevision && onRevisionChange && (
            <RevisionSwitcher
              currentRevision={project.current_revision ?? 1}
              totalRevisions={project.current_revision ?? 1}
              selectedRevision={selectedRevision}
              onRevisionChange={onRevisionChange}
              onCreateRevision={readOnly ? undefined : () => setIsReplaceDialogOpen(true)}
              compact={compact}
            />
          )}
        </div>

        {!readOnly && (
          <DropdownMenu>
            <Tooltip>
              <TooltipTrigger asChild>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" size="icon">
                    <EllipsisVerticalIcon />
                  </Button>
                </DropdownMenuTrigger>
              </TooltipTrigger>
              <TooltipContent>See more options</TooltipContent>
            </Tooltip>

            <DropdownMenuContent className="w-56">
              <MenuItemWithTooltip
                icon={Pencil}
                onClick={() => setIsEditDialogOpen(true)}
                tooltip="Edit project details"
              >
                Edit project details
              </MenuItemWithTooltip>

              <MenuItemWithTooltip
                icon={Plus}
                onClick={() => setIsReplaceDialogOpen(true)}
                tooltip="Upload a new version of the main document as a new revision. Previous revisions, their reviewer memos, and results are kept."
              >
                Create new revision
              </MenuItemWithTooltip>

              <MenuItemWithTooltip
                icon={Link}
                onClick={() => share.setIsDialogOpen(true)}
                tooltip={share.isEnabled ? 'View or copy the share link' : 'Create a public link'}
              >
                {share.isEnabled ? 'Manage share link' : 'Share this project'}
              </MenuItemWithTooltip>
            </DropdownMenuContent>
          </DropdownMenu>
        )}
      </div>

      <ShareDialog
        open={share.isDialogOpen}
        onOpenChange={share.setIsDialogOpen}
        shareStatus={share.shareStatus}
        isEnabling={share.isEnabling}
        isDisabling={share.isDisabling}
        onEnable={share.enable}
        onDisable={share.disable}
      />

      <ShareWarningDialog
        open={showShareWarning}
        onOpenChange={setShowShareWarning}
        isProjectPublic={share.isEnabled || !!shareContext.shareToken}
        isEnablingShare={isEnablingForDownload || share.isEnabling}
        isDownloading={isDownloading}
        filters={{ severity: filter.severity, workflowType: filter.workflowType, showPassing: filter.showPassing }}
        counts={exportCounts(issues, filter)}
        linksAvailable={shareLinksAvailable(selectedRevision, project.current_revision ?? 1)}
        onDownload={(type, options) => {
          setShowShareWarning(false);
          executeDownload(type, options.includeEdits);
        }}
      />

      <EditProjectDialog
        isOpen={isEditDialogOpen}
        project={project}
        onConfirm={(values) => updateProjectMutation.mutate(values)}
        onCancel={() => setIsEditDialogOpen(false)}
        isSubmitting={updateProjectMutation.isPending}
      />

      <ReplaceMainDocumentDialog
        isOpen={isReplaceDialogOpen}
        projectId={projectId}
        onClose={() => setIsReplaceDialogOpen(false)}
        onRevisionCreated={onRevisionCreated}
      />
    </>
  );
}

interface MenuItemWithTooltipProps {
  icon: React.ComponentType<{ className?: string }>;
  onClick: () => void;
  tooltip: string;
  disabled?: boolean;
  children: React.ReactNode;
}

function MenuItemWithTooltip({ icon: Icon, onClick, tooltip, disabled, children }: MenuItemWithTooltipProps) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <DropdownMenuItem onClick={onClick} disabled={disabled}>
          <Icon />
          {children}
        </DropdownMenuItem>
      </TooltipTrigger>
      <TooltipContent side="left">{tooltip}</TooltipContent>
    </Tooltip>
  );
}
