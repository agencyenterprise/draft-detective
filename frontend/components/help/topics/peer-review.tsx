'use client';

import { cn } from '@/lib/utils';
import { ReactNode } from 'react';
import { SectionTitle, TopicLink } from '../help-primitives';
import { HelpTopicBodyProps } from '../topics';

interface Step {
  title: string;
  body: string;
  /** The step the author does by hand; every other one is a run. */
  byHand?: boolean;
}

/**
 * The sequence, in the order it has to happen. Numbered because it genuinely is
 * an order — two of these steps compare the revised draft against the reviewed
 * one, so they cannot run until the draft in the middle exists.
 */
const STEPS: Step[] = [
  {
    title: 'Plan the revision',
    body: 'Reads the memos and breaks every reviewer’s points into discrete, actionable suggestions, each mapped to the part of your draft it lands on.',
  },
  {
    title: 'Upload your revised draft',
    body: 'You write the revision; this step files it as a new one, which is what gives the next two steps a before and an after to compare.',
    byHand: true,
  },
  {
    title: 'Respond to the reviewers',
    body: 'Drafts one response memo per reviewer. Each of their points is echoed back word for word, with a reply on what changed and where — or why it did not. Once they have been edited and sent, upload the final versions; if the author wrote their own, upload those instead.',
  },
  {
    title: 'QA coverage report',
    body: 'Gives every point a verdict — addressed, partly addressed, declined with a rationale, or not addressed — plus a count table and an overall read for sign-off. When author response memos are uploaded, it also checks what the author told each reviewer against the revised draft.',
  },
];

/**
 * The one part of the app that is not about reading your draft: it is about the
 * round trip after other people have read it. The steps carry the explanation,
 * because the order is the thing that surprises people.
 */
export function PeerReviewTopic({ onOpenTopic }: HelpTopicBodyProps) {
  return (
    <div className="space-y-5">
      <section>
        <SectionTitle>After the reviewers reply</SectionTitle>
        <p className="text-foreground/80 leading-relaxed">
          Every other{' '}
          <TopicLink to="assessments" onOpenTopic={onOpenTopic}>
            assessment
          </TopicLink>{' '}
          reads your draft on its own. Peer Review starts from{' '}
          <strong className="text-foreground font-medium">what your reviewers wrote about it</strong> — their memos —
          and walks the round trip from those comments to a revised draft, a reply to each reviewer, and a report on how
          much of it you actually addressed.
        </p>
        <p className="text-foreground/80 mt-2 leading-relaxed">
          A <strong className="text-foreground font-medium">reviewer memo</strong> is one reviewer&apos;s document about
          your draft. Add them from the Peer Review tab, which is also where author response memos go. They belong to
          the{' '}
          <TopicLink to="revisions" onOpenTopic={onOpenTopic}>
            revision
          </TopicLink>{' '}
          they were written about, so if you upload a newer draft first, memos left on the older one are the ones these
          steps read.
        </p>
        <p className="text-foreground/80 mt-2 leading-relaxed">
          A <strong className="text-foreground font-medium">response memo</strong> is the author&apos;s reply to one
          reviewer. It belongs to the revised draft it describes, so uploading another revision afterwards leaves it
          behind: upload the replies again for the new draft.
        </p>
      </section>

      <section>
        <SectionTitle>The four steps</SectionTitle>
        <ol className="space-y-2">
          {STEPS.map((step, index) => (
            <li key={step.title} className="flex gap-2.5 rounded-md border p-2.5">
              <span
                className={cn(
                  'mt-px flex size-4 shrink-0 items-center justify-center rounded-full font-mono text-[10px] font-medium',
                  step.byHand ? 'bg-muted text-muted-foreground' : 'bg-primary/10 text-primary',
                )}
              >
                {index + 1}
              </span>
              <div className="min-w-0">
                <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs font-medium">
                  {step.title}
                  {step.byHand && (
                    <span className="rounded-sm bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
                      Your turn
                    </span>
                  )}
                </p>
                <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">{step.body}</p>
              </div>
            </li>
          ))}
        </ol>
        <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
          A step stays locked until what it reads exists, and says what it is waiting for. Nothing here starts on its
          own either — not even when you create a revision — because these steps read one draft against another, and
          only you know when the revision is the one you meant.
        </p>
      </section>

      <section>
        <SectionTitle>Where it lives</SectionTitle>
        <ul className="space-y-1.5">
          <Fact term="The Peer Review tab">
            The steps, the memos they read, and each step&apos;s report. Results also appear on the Assessments tab
            alongside{' '}
            <TopicLink to="assessments" onOpenTopic={onOpenTopic}>
              everything else
            </TopicLink>
            , but this is where they are sequenced and started.
          </Fact>
          <Fact term="Still in alpha">
            It is behind an opt-in while the sequence settles, which is why it is not in every project.
          </Fact>
        </ul>
      </section>
    </div>
  );
}

function Fact({ term, children }: { term: string; children: ReactNode }) {
  return (
    <li className="text-xs leading-relaxed">
      <strong className="font-medium">{term}.</strong> <span className="text-muted-foreground">{children}</span>
    </li>
  );
}
