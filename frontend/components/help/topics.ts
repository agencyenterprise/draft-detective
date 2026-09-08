import {
  BookOpen,
  CircleAlert,
  FileText,
  History,
  Link2,
  ListChecks,
  LucideIcon,
  MessagesSquare,
  ThumbsUp,
} from 'lucide-react';
import { ComponentType } from 'react';
import { AssessmentsTopic } from './topics/assessments';
import { FeedbackTopic } from './topics/feedback';
import { IssuesTopic } from './topics/issues';
import { PeerReviewTopic } from './topics/peer-review';
import { ReferencesTopic } from './topics/references';
import { RevisionsTopic } from './topics/revisions';
import { SharingTopic } from './topics/sharing';
import { SourceFilesTopic } from './topics/source-files';

export type HelpTopicId =
  | 'assessments'
  | 'issues'
  | 'references'
  | 'source-files'
  | 'revisions'
  | 'sharing'
  | 'peer-review'
  | 'feedback';

export interface HelpTopicBodyProps {
  /**
   * Sends the reader to the References tab. Passed only where that is somewhere
   * else to go — the References tab itself omits it.
   */
  onReviewReferences?: () => void;
  /**
   * Moves the dialog to another topic, for the places where one concept hands
   * over to the next rather than repeating it.
   */
  onOpenTopic?: (topic: HelpTopicId) => void;
}

export interface HelpTopic {
  id: HelpTopicId;
  /** In the navigation, where it sits beside the other topics. */
  label: string;
  /** The dialog's heading once this topic is open. */
  title: string;
  description: string;
  icon: LucideIcon;
  Body: ComponentType<HelpTopicBodyProps>;
  /**
   * Listed only for readers who have opted into experimental features, matching
   * the tab it explains. Explaining a part of the app someone cannot see would
   * be worse than saying nothing.
   */
  experimental?: boolean;
}

/**
 * The concepts the app explains in one place, ordered as the work runs:
 * assessments produce issues, references name sources, one assessment needs
 * those sources, revisions are what all of it hangs from, sharing is how the
 * draft reaches someone else, peer review is what happens once they have read
 * it, and feedback is how any of it gets better. Every "what is this" link
 * in the product opens this list at one of them, so a question asked in one
 * corner is answered next to all the others.
 */
export const HELP_TOPICS: HelpTopic[] = [
  {
    id: 'assessments',
    label: 'Assessments',
    title: 'Assessments, and what they check',
    description: 'Each one reads your draft looking for a different kind of problem, and reports what it finds.',
    icon: ListChecks,
    Body: AssessmentsTopic,
  },
  {
    id: 'issues',
    label: 'Issues',
    title: 'Issues in your document',
    description: 'One finding from one assessment, anchored to the lines it is about.',
    icon: CircleAlert,
    Body: IssuesTopic,
  },
  {
    id: 'references',
    label: 'References',
    title: 'References in your bibliography',
    description: 'Every entry, pulled out of your document automatically.',
    icon: BookOpen,
    Body: ReferencesTopic,
  },
  {
    id: 'source-files',
    label: 'Source files',
    title: 'Source files, and the assessment that needs them',
    description:
      'The document a reference points at. It does not arrive with your draft, so someone has to provide it.',
    icon: FileText,
    Body: SourceFilesTopic,
  },
  {
    id: 'revisions',
    label: 'Revisions',
    title: 'Revisions of the main document',
    description: 'Each draft you upload becomes a revision. The ones before it stay, with everything they found.',
    icon: History,
    Body: RevisionsTopic,
  },
  {
    id: 'sharing',
    label: 'Sharing',
    title: 'Sharing a project by link',
    description: 'A public, read-only link to your project. Anyone holding it can look; only you can change anything.',
    icon: Link2,
    Body: SharingTopic,
  },
  {
    id: 'peer-review',
    label: 'Peer Review',
    title: 'Peer review, from memos to sign-off',
    description: 'The round trip after other people have read your draft: plan, revise, respond, and check coverage.',
    icon: MessagesSquare,
    Body: PeerReviewTopic,
    experimental: true,
  },
  {
    id: 'feedback',
    label: 'Feedback',
    title: 'Feedback, and what sharing it means',
    description: 'Telling us whether a finding was any good, and deciding how much of it we get to see.',
    icon: ThumbsUp,
    Body: FeedbackTopic,
  },
];
