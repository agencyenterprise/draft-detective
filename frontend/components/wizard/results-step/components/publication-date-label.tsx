import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { LiveReportsState, LiteratureReviewState, WorkflowRunDetail } from '@/lib/generated-api';
import { format } from 'date-fns';

export interface PublicationDateLabelProps {
  results: WorkflowRunDetail[];
  prefix?: string;
  suffix?: string;
}

export function PublicationDateLabel({ results, prefix, suffix }: PublicationDateLabelProps) {
  // Extract user-informed publication date from workflow config
  const userInformedPublicationDate = results
    ?.map((result) => {
      const state = result.state;
      // Check if state has config with document_publication_date
      if ('config' in state && state.config && 'document_publication_date' in state.config) {
        const config = state.config as LiveReportsState['config'] | LiteratureReviewState['config'];
        return config.document_publication_date;
      }
      return undefined;
    })
    .find((date) => date !== undefined);

  // Extract publication date from main_document_summary as fallback
  const extractedPublicationDate = results
    ?.map((result) => {
      const state = result.state;
      if ('main_document_summary' in state && state.main_document_summary?.publication_date) {
        return state.main_document_summary.publication_date;
      }
      return undefined;
    })
    .find((date) => date !== undefined && date !== 'Unknown');

  const value = userInformedPublicationDate
    ? { date: format(new Date(userInformedPublicationDate), 'MMM d, yyyy'), source: 'user-informed' as const }
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
