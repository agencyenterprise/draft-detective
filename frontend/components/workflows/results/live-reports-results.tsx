import { LabeledValue } from '@/components/labeled-value';
import { Markdown } from '@/components/markdown';
import { Callout } from '@/components/ui/callout';
import { Card, CardContent } from '@/components/ui/card';
import { LiveReportsState, ProjectDetailed, WorkflowRunDetail } from '@/lib/generated-api';
import { format } from 'date-fns';
import { FileText } from 'lucide-react';
import { PublicationDateLabel } from '@/components/results/components/publication-date-label';

interface LiveReportsResultsProps {
  project: ProjectDetailed;
  workflowDetail: WorkflowRunDetail;
}

export function LiveReportsResults({ project, workflowDetail }: LiveReportsResultsProps) {
  const state = workflowDetail.state as LiveReportsState;

  if (!state) {
    return <div className="p-4 text-center text-muted-foreground">No state available</div>;
  }

  const addendum = state.addendum_report;

  if (!addendum) {
    return <div className="p-4 text-center text-muted-foreground">No addendum report available</div>;
  }

  const metadata = addendum.report_metadata;

  return (
    <div className="space-y-4 text-sm">
      <div className="space-y-1">
        <LabeledValue label="Title">{metadata.title}</LabeledValue>
        <LabeledValue label="Document publication date">
          <PublicationDateLabel project={project} />
        </LabeledValue>
        <LabeledValue label="Live report generation date">
          {format(new Date(metadata.date_generated), 'MMM dd, yyyy')}
        </LabeledValue>
        <LabeledValue label="Update Type">{metadata.update_type}</LabeledValue>
      </div>

      <Callout title="Sentence Summary" variant="info" icon={FileText}>
        <Markdown>{metadata.sentence_summary}</Markdown>
      </Callout>

      <Card>
        <CardContent>
          <Markdown>{addendum.report_markdown.replace(/\n/g, '\n\n')}</Markdown>
        </CardContent>
      </Card>
    </div>
  );
}
