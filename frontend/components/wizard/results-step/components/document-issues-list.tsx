import { DocumentIssue, WorkflowRunDetail } from '@/lib/generated-api';
import { DocumentIssueCard } from './document-issue-card';

interface DocumentIssuesListProps {
  issues: DocumentIssue[];
  hideJumpToChunk?: boolean;
  onSelect: (issue: DocumentIssue) => void;
  workflowRuns?: WorkflowRunDetail[];
  readOnly?: boolean;
}

export function DocumentIssuesList({
  issues,
  hideJumpToChunk = false,
  onSelect,
  workflowRuns,
  readOnly,
}: DocumentIssuesListProps) {
  return (
    <div className="space-y-2">
      {issues.map((issue) => (
        <DocumentIssueCard
          key={issue.id}
          issue={issue}
          hideJumpToChunk={hideJumpToChunk}
          onSelect={onSelect}
          workflowRuns={workflowRuns}
          readOnly={readOnly}
        />
      ))}
    </div>
  );
}
