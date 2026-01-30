import { AiGeneratedLabel } from '@/components/ai-generated-label';
import { Badge } from '@/components/ui/badge';
import type { ProjectDetailed } from '@/lib/generated-api';
import { X } from 'lucide-react';
import { useMemo } from 'react';
import { SingleChunkContent } from './single-chunk-content';

export interface ChunkSidebarContentProps {
  chunkIndices: number[];
  projectDetail: ProjectDetailed;
  readOnly?: boolean;
  onClearChunkSelection: () => void;
  onNavigateToReferences?: (referenceIndex: number) => void;
}

export function ChunkSidebarContent({
  chunkIndices,
  projectDetail,
  readOnly = false,
  onClearChunkSelection,
  onNavigateToReferences,
}: ChunkSidebarContentProps) {
  const workflowRuns = projectDetail.workflow_runs ?? [];

  const headerLabel = useMemo(() => {
    if (chunkIndices.length === 1) {
      return `Chunk #${chunkIndices[0]}`;
    }
    return `${chunkIndices.length} Chunks Selected`;
  }, [chunkIndices]);

  const showChunkLabels = chunkIndices.length > 1;

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <Badge variant="secondary" className="gap-1 pl-2.5 pr-1">
          {headerLabel}
          <button
            onClick={onClearChunkSelection}
            className="ml-0.5 rounded-sm hover:bg-muted-foreground/20 p-0.5"
            aria-label="Clear chunk selection"
          >
            <X className="h-3 w-3" />
          </button>
        </Badge>

        <AiGeneratedLabel className="ml-auto" />
      </div>

      {chunkIndices.map((chunkIndex) => (
        <SingleChunkContent
          key={chunkIndex}
          chunkIndex={chunkIndex}
          projectDetail={projectDetail}
          workflowRuns={workflowRuns}
          readOnly={readOnly}
          onNavigateToReferences={onNavigateToReferences}
          showChunkLabel={showChunkLabels}
        />
      ))}
    </div>
  );
}
