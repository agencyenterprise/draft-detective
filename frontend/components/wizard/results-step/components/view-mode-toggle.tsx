import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { DocRenderMode } from '@/lib/constants';
import { FileTextIcon, LayoutIcon } from 'lucide-react';

export interface ViewModeToggleProps {
  onViewModeChange: (mode: DocRenderMode) => void;
  viewMode: DocRenderMode;
  isDoclingAvailable: boolean;
}

export function ViewModeToggle({ onViewModeChange, viewMode, isDoclingAvailable }: ViewModeToggleProps) {
  return (
    <ToggleGroup type="single" variant="default" size="sm" value={viewMode} onValueChange={onViewModeChange}>
      <Tooltip>
        <TooltipTrigger asChild>
          <div>
            <ToggleGroupItem value="markdown" className="cursor-pointer">
              <FileTextIcon />
            </ToggleGroupItem>
          </div>
        </TooltipTrigger>
        <TooltipContent className="max-w-sm">
          <p className="font-semibold mb-1">Markdown View</p>
          <p className="text-xs">
            Simple text-based view of document content, showing the original document content converted to markdown
          </p>
        </TooltipContent>
      </Tooltip>

      <Tooltip>
        <TooltipTrigger asChild>
          <div>
            <ToggleGroupItem value="docling" className="cursor-pointer" disabled={!isDoclingAvailable}>
              <LayoutIcon />
            </ToggleGroupItem>
          </div>
        </TooltipTrigger>
        <TooltipContent className="max-w-sm">
          <p className="font-semibold mb-1">Docling View</p>
          <p className="text-xs">
            Visual layout with original document formatting, showing the original document content converted with
            docling
            {!isDoclingAvailable && ' (unavailable for this document)'}
          </p>
        </TooltipContent>
      </Tooltip>
    </ToggleGroup>
  );
}
