import { EditProjectDialog, EditProjectFormValues } from '@/components/projects/edit-project-dialog';
import { FilterWarningDialog } from '@/components/share/filter-warning-dialog';
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
} from '@/lib/generated-api';
import { useDocumentExplorerStore } from '@/lib/stores/document-explorer-store';
import { getWorkflowRunByType } from '@/lib/workflow-state';
import { getErrorMessage } from '@/lib/api-error';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Download, EllipsisVerticalIcon, Link, Pencil } from 'lucide-react';
import { useState } from 'react';
import { toast } from 'sonner';
import { downloadDocxFile, DocxType, useDownloadDocx } from './use-download-docx';

type ProjectWithDetails = Project & {
  publication_date?: Date | null;
  domain?: string | null;
  target_audience?: string | null;
};

export interface AnalysisOptionsMenuProps {
  project: ProjectWithDetails;
  results: WorkflowRunDetail[];
  readOnly: boolean;
}

export function AnalysisOptionsMenu({ project, results, readOnly }: AnalysisOptionsMenuProps) {
  const { filter } = useDocumentExplorerStore();
  const projectId = project.id;
  const share = useShareStatus(projectId, !readOnly);
  const shareContext = useShare();
  const queryClient = useQueryClient();

  const [showShareWarning, setShowShareWarning] = useState(false);
  const [showFilterWarning, setShowFilterWarning] = useState(false);
  const [pendingDocxType, setPendingDocxType] = useState<DocxType>('original');
  const [isEnablingForDownload, setIsEnablingForDownload] = useState(false);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);

  const shareToken = share.shareStatus?.share_link?.token ?? shareContext.shareToken;
  const { download, isDownloading } = useDownloadDocx({
    projectId,
    shareToken,
    severities: filter.severity,
    workflowTypes: filter.workflowType,
    includePassing: filter.showPassing,
    docxType: pendingDocxType,
  });

  const hasActiveSeverityFilter = filter.severity.length > 0 && filter.severity.length < 3;
  const hasActiveWorkflowTypeFilter = filter.workflowType.length > 0;
  const hasActiveFilter = hasActiveSeverityFilter || hasActiveWorkflowTypeFilter || filter.showPassing;

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
          domain: values.domain || null,
          target_audience: values.target_audience || null,
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

  const downloadWithShare = async (docxType: DocxType) => {
    setIsEnablingForDownload(true);
    const toastId = toast.loading('Preparing DOCX with share links...', { description: 'This may take a few moments' });

    try {
      const shareResponse = await share.enable();
      const token = shareResponse?.share_link?.token;
      if (!token) throw new Error('Failed to create share token');

      await downloadDocxFile(projectId, token, filter.severity, filter.workflowType, docxType, filter.showPassing);
      toast.success('DOCX file downloaded successfully', { id: toastId });
    } catch (error) {
      console.error('Failed to enable sharing and download:', error);
      toast.error('Failed to download DOCX file', { id: toastId });
    } finally {
      setIsEnablingForDownload(false);
    }
  };

  // Execute the actual download based on pending action
  const executeDownload = (docxType: DocxType) => {
    const notShared = !share.isEnabled && !shareContext.shareToken;
    const needsShare = docxType === 'add-in' || docxType === 'comments-with-links';
    if (needsShare && notShared) {
      downloadWithShare(docxType);
    } else {
      download(docxType);
    }
  };

  // Show filter warning or execute download
  const proceedWithDownload = (docxType: DocxType) => {
    if (hasActiveFilter) {
      setPendingDocxType(docxType);
      setShowFilterWarning(true);
    } else {
      executeDownload(docxType);
    }
  };

  const handleDownloadClick = () => {
    setShowShareWarning(true);
  };

  return (
    <>
      <div className="flex items-center gap-2">
        {!readOnly && <ShareStatusBadge isEnabled={share.isEnabled} onClick={() => share.setIsDialogOpen(true)} />}

        <DropdownMenu>
          {(hasDocx || !readOnly) && (
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
          )}

          <DropdownMenuContent className="w-56">
            {hasDocx && (
              <MenuItemWithTooltip
                icon={Download}
                onClick={handleDownloadClick}
                disabled={isDownloading}
                tooltip="Download reviewed DOCX"
              >
                {isDownloading ? 'Downloading...' : 'Download DOCX'}
              </MenuItemWithTooltip>
            )}

            {!readOnly && (
              <>
                <MenuItemWithTooltip
                  icon={Pencil}
                  onClick={() => setIsEditDialogOpen(true)}
                  tooltip="Edit project title, publication date, domain, and target audience"
                >
                  Edit project details
                </MenuItemWithTooltip>

                <MenuItemWithTooltip
                  icon={Link}
                  onClick={() => share.setIsDialogOpen(true)}
                  tooltip={share.isEnabled ? 'View or copy the share link' : 'Create a public link'}
                >
                  {share.isEnabled ? 'Manage share link' : 'Share this analysis'}
                </MenuItemWithTooltip>
              </>
            )}
          </DropdownMenuContent>
        </DropdownMenu>
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
        onDownload={(type) => {
          setShowShareWarning(false);
          proceedWithDownload(type);
        }}
      />

      <FilterWarningDialog
        open={showFilterWarning}
        onOpenChange={setShowFilterWarning}
        severityFilter={filter.severity}
        workflowTypeFilter={filter.workflowType}
        showPassing={filter.showPassing}
        onConfirm={() => {
          setShowFilterWarning(false);
          executeDownload(pendingDocxType);
        }}
      />

      <EditProjectDialog
        isOpen={isEditDialogOpen}
        project={project}
        onConfirm={(values) => updateProjectMutation.mutate(values)}
        onCancel={() => setIsEditDialogOpen(false)}
        isSubmitting={updateProjectMutation.isPending}
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
