import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { ProjectDetailed, WorkflowRunType } from '@/lib/generated-api';
import { getWorkflowRunByType } from '@/lib/workflow-state';
import { format } from 'date-fns';

export interface PublicationDateLabelProps {
  project: ProjectDetailed;
  prefix?: string;
  suffix?: string;
}

export function PublicationDateLabel({ project, prefix, suffix }: PublicationDateLabelProps) {
  // Extract user-informed publication date from workflow config
  const userInformedPublicationDate = project.project.publication_date;

  // Extract publication date from main document summary as fallback
  const documentProcessing = getWorkflowRunByType(project.workflow_runs ?? [], WorkflowRunType.DocumentProcessing);
  const documentSummarization = getWorkflowRunByType(
    project.workflow_runs ?? [],
    WorkflowRunType.DocumentSummarization,
  );
  const mainFileId = documentProcessing?.state?.file?.file_id;
  const mainSummary = documentSummarization?.state?.summaries?.find((s) => s.file_id === mainFileId);
  const extractedPublicationDate = mainSummary?.publication_date;

  const value = userInformedPublicationDate
    ? { date: format(userInformedPublicationDate, 'MMM d, yyyy'), source: 'user-informed' as const }
    : extractedPublicationDate && extractedPublicationDate !== 'Unknown'
      ? { date: extractedPublicationDate, source: 'extracted' as const }
      : undefined;

  if (!value) {
    return null;
  }

  const { date, source } = value;

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span>
          {prefix} {date} {suffix}
        </span>
      </TooltipTrigger>
      <TooltipContent>
        <p>
          {source === 'user-informed'
            ? 'User-informed publication date'
            : 'Publication date extracted from the document using AI'}
        </p>
      </TooltipContent>
    </Tooltip>
  );
}
