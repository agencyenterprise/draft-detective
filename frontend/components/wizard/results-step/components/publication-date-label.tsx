import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { ClaimSubstantiatorStateSummary } from '@/lib/generated-api';
import { format } from 'date-fns';

export interface PublicationDateLabelProps {
  results: ClaimSubstantiatorStateSummary | undefined | null;
  prefix?: string;
  suffix?: string;
}

export function PublicationDateLabel({ results, prefix, suffix }: PublicationDateLabelProps) {
  const userInformedPublicationDate = results?.config?.documentPublicationDate;
  const extractedPublicationDate = results?.mainDocumentSummary?.publicationDate;

  const value = userInformedPublicationDate
    ? { date: format(userInformedPublicationDate, 'MMM d, yyyy'), source: 'user-informed' }
    : extractedPublicationDate && extractedPublicationDate !== 'Unknown'
      ? { date: extractedPublicationDate, source: 'extracted' }
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
