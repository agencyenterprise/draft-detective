import { ShareDialog } from '@/components/share/share-dialog';
import { ShareStatusBadge } from '@/components/share/share-status-badge';
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
import { useDownloadDocx } from './use-download-docx';

export interface AnalysisOptionsMenuProps {
  onSaveAsEvalTest: () => void;
  onReevaluate: () => void;
  projectId: string;
  results: WorkflowRunDetail[];
}

export function AnalysisOptionsMenu({ onSaveAsEvalTest, onReevaluate, projectId, results }: AnalysisOptionsMenuProps) {
  const share = useShareStatus(projectId);
  const { download, isDownloading } = useDownloadDocx(projectId);

  const claimSubstantiationResults = getWorkflowRunByType(results, WorkflowRunType.ClaimSubstantiation);
  const hasDocx = claimSubstantiationResults?.state?.file?.original_file_path?.endsWith('.docx');

  return (
    <>
      <div className="flex items-center gap-2">
        <ShareStatusBadge isEnabled={share.isEnabled} onClick={() => share.setIsDialogOpen(true)} />

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

            <MenuItemWithTooltip icon={RefreshCcwIcon} onClick={onReevaluate} tooltip="Re-run with different config">
              Re-run analysis
            </MenuItemWithTooltip>

            {hasDocx && (
              <MenuItemWithTooltip
                icon={Download}
                onClick={download}
                disabled={isDownloading}
                tooltip="Download reviewed DOCX"
              >
                {isDownloading ? 'Downloading...' : 'Download DOCX'}
              </MenuItemWithTooltip>
            )}

            <DropdownMenuSeparator />

            <MenuItemWithTooltip
              icon={Link}
              onClick={() => share.setIsDialogOpen(true)}
              tooltip={share.isEnabled ? 'View or copy the share link' : 'Create a public link'}
            >
              {share.isEnabled ? 'Manage share link' : 'Share this analysis'}
            </MenuItemWithTooltip>
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
