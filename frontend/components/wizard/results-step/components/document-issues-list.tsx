import { DocumentIssue } from '@/lib/generated-api';
import { DocumentIssueCard } from './document-issue-card';

interface DocumentIssuesListProps {
  issues: DocumentIssue[];
  onSelect: (issue: DocumentIssue) => void;
}

export function DocumentIssuesList({ issues, onSelect }: DocumentIssuesListProps) {
  return (
    <div className="space-y-2">
      {issues.map((issue, index) => (
        <DocumentIssueCard key={index} issue={issue} onSelect={onSelect} />
      ))}
    </div>
  );
}
