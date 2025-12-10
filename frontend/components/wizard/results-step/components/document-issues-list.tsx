import { DocumentIssue } from '@/lib/generated-api';
import { DocumentIssueCard } from './document-issue-card';

interface DocumentIssuesListProps {
  issues: DocumentIssue[];
  onSelect: (issue: DocumentIssue) => void;
}

export function DocumentIssuesList({ issues, onSelect }: DocumentIssuesListProps) {
  return (
    <div className="space-y-2">
      {issues.length === 0 && (
        <div className="text-sm text-muted-foreground space-y-2">
          <p>No issues found for this document.</p>
          <p>You can still view detailled analysis for each chunk by selecting a chunk from the document.</p>
        </div>
      )}
      {issues.map((issue, index) => (
        <DocumentIssueCard key={index} issue={issue} onSelect={onSelect} />
      ))}
    </div>
  );
}
