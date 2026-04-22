import { Issue } from '@/lib/generated-api';
import { DocumentIssueCard } from './document-issue-card';

interface DocumentIssuesListProps {
  issues: Issue[];
  hideJumpButton?: boolean;
  onSelect: (issue: Issue) => void;
  readOnly?: boolean;
}

export function DocumentIssuesList({ issues, hideJumpButton = false, onSelect, readOnly }: DocumentIssuesListProps) {
  return (
    <div className="space-y-2">
      {issues.map((issue) => (
        <DocumentIssueCard
          key={issue.id}
          issue={issue}
          hideJumpButton={hideJumpButton}
          onSelect={onSelect}
          readOnly={readOnly}
        />
      ))}
    </div>
  );
}
