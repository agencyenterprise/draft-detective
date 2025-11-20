import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { EllipsisVerticalIcon, FileTextIcon } from 'lucide-react';

export interface AnalysisOptionsMenuProps {
  onSaveAsEvalTest: () => void;
}

export function AnalysisOptionsMenu({ onSaveAsEvalTest }: AnalysisOptionsMenuProps) {
  return (
    <DropdownMenu>
      <Tooltip>
        <TooltipTrigger asChild>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon">
              <EllipsisVerticalIcon />
            </Button>
          </DropdownMenuTrigger>
        </TooltipTrigger>
        <TooltipContent>
          <p>See more options for this analysis</p>
        </TooltipContent>
      </Tooltip>
      <DropdownMenuContent className="w-56">
        <Tooltip>
          <TooltipTrigger asChild>
            <DropdownMenuItem className="cursor-pointer" onClick={onSaveAsEvalTest}>
              <FileTextIcon />
              Save as eval test
            </DropdownMenuItem>
          </TooltipTrigger>
          <TooltipContent>
            <p>Generate evaluation test cases from these results for testing agents</p>
          </TooltipContent>
        </Tooltip>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
