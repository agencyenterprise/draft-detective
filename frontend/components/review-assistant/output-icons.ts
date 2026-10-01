import { ClipboardCheck, ListChecks, LucideIcon, MessagesSquare } from 'lucide-react';
import { ReviewOutputType } from './outputs';

/** The same icons the Peer Review tab uses for these three outputs. */
export const OUTPUT_ICONS: Record<ReviewOutputType, LucideIcon> = {
  revision_planning_summary: ListChecks,
  reviewer_response_memos: MessagesSquare,
  reviewer_coverage_report: ClipboardCheck,
};
