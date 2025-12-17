import { ShareDialog } from '@/components/share/share-dialog';
import { ShareStatusBadge } from '@/components/share/share-status-badge';
import { ShareWarningDialog } from '@/components/share/share-warning-dialog';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { useShareStatus } from '@/hooks/use-share-status';
import { WorkflowRunDetail, WorkflowRunType } from '@/lib/generated-api';
import { getWorkflowRunByType } from '@/lib/workflow-state';
import { Download, EllipsisVerticalIcon, FileTextIcon, Link, RefreshCcwIcon } from 'lucide-react';
import { useState } from 'react';
import { useDownloadDocx, downloadDocxFile } from './use-download-docx';
import { toast } from 'sonner';

export interface AnalysisOptionsMenuProps {
  onSaveAsEvalTest: () => void;
  onReevaluate: () => void;
  projectId: string;
  results: WorkflowRunDetail[];
  readOnly: boolean;
}

export function AnalysisOptionsMenu({
  onSaveAsEvalTest,
  onReevaluate,
  projectId,
  results,
  readOnly,
}: AnalysisOptionsMenuProps) {
  const share = useShareStatus(projectId);
  const [isWarningDialogOpen, setIsWarningDialogOpen] = useState(false);
  const [isEnablingForDownload, setIsEnablingForDownload] = useState(false);

  const shareToken = share.shareStatus?.share_link?.token ?? null;
  const { download, isDownloading } = useDownloadDocx({ projectId, shareToken });

  const claimSubstantiationResults = getWorkflowRunByType(results, WorkflowRunType.ClaimSubstantiation);
  const hasDocx = claimSubstantiationResults?.state?.file?.original_file_path?.endsWith('.docx');

  const handleDownloadClick = () => {
    if (share.isEnabled) {
      download(true);
    } else {
      setIsWarningDialogOpen(true);
    }
  };

  const handleMakePublicAndDownload = async () => {
    setIsEnablingForDownload(true);
    setIsWarningDialogOpen(false);

    const toastId = toast.loading('Preparing DOCX with share links...', {
      description: 'This may take a few moments',
    });

    try {
      const shareResponse = await share.enable();
      const freshToken = shareResponse?.share_link?.token;

      if (!freshToken) {
        throw new Error('Failed to create share token');
      }

      await downloadDocxFile(projectId, freshToken);
      toast.success('DOCX file downloaded successfully', { id: toastId });
    } catch (error) {
      console.error('Failed to enable sharing and download:', error);
      toast.error('Failed to download DOCX file', { id: toastId });
    } finally {
      setIsEnablingForDownload(false);
    }
  };

  const handleDownloadWithoutLinks = () => {
    setIsWarningDialogOpen(false);
    download(false);
  };

  return (
    <>
      <div className="flex items-center gap-2">
        {!readOnly && <ShareStatusBadge isEnabled={share.isEnabled} onClick={() => share.setIsDialogOpen(true)} />}

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
            <MenuItemWithTooltip icon={FileTextIcon} onClick={onSaveAsEvalTest} tooltip="Generate eval test cases">
              Save as eval test
            </MenuItemWithTooltip>

            {!readOnly && (
              <MenuItemWithTooltip icon={RefreshCcwIcon} onClick={onReevaluate} tooltip="Re-run with different config">
                Re-run analysis
              </MenuItemWithTooltip>
            )}

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
                <DropdownMenuSeparator />

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
        open={isWarningDialogOpen}
        onOpenChange={setIsWarningDialogOpen}
        isEnablingShare={isEnablingForDownload || share.isEnabling}
        isDownloading={isDownloading}
        onMakePublicAndDownload={handleMakePublicAndDownload}
        onDownloadWithoutLinks={handleDownloadWithoutLinks}
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
        <DropdownMenuItem className="cursor-pointer" onClick={onClick} disabled={disabled}>
          <Icon />
          {children}
        </DropdownMenuItem>
      </TooltipTrigger>
      <TooltipContent side="left">{tooltip}</TooltipContent>
    </Tooltip>
  );
}
