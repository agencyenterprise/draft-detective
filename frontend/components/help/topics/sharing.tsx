'use client';

import { Check, EllipsisVertical, Eye, Link2, Link2Off, LucideIcon, X } from 'lucide-react';
import { ReactNode } from 'react';
import { SectionTitle, TopicLink } from '../help-primitives';
import { HelpTopicBodyProps } from '../topics';

interface Ability {
  can: boolean;
  text: string;
}

/** What creating a link sets in motion, in the order it happens. */
const STEPS: { icon: LucideIcon; title: string; body: string }[] = [
  {
    icon: EllipsisVertical,
    title: 'Open the project menu and choose “Share this project”',
    body: 'The three-dot button at the right of the project header. Nothing is shared yet; the dialog only asks whether you want a link.',
  },
  {
    icon: Link2,
    title: '“Enable Sharing” creates the link',
    body: 'A unique address for this project, ready to copy. From then on the header shows a green “Sharing enabled” badge, and clicking it brings the dialog back.',
  },
  {
    icon: Eye,
    title: '“Preview” opens what readers get',
    body: 'The same page they will see, with a banner along the top reminding you that this is the shared version and a button back to the editable one.',
  },
];

/**
 * The link says who a reader is, so this is the one place where being logged in
 * grants nothing: the list is written from the reader's side, and it is the same
 * whoever holds the link.
 */
const READER_ABILITIES: Ability[] = [
  { can: true, text: 'Read the document, with every issue anchored where it was found' },
  { can: true, text: 'Browse the assessments, their results, and the references' },
  { can: true, text: 'Download the uploaded files, and the Export with the issues as Word comments' },
  { can: false, text: 'Run an assessment, upload a revision, or edit the project details' },
  { can: false, text: 'Resolve or rate an issue, or see any rating you have given' },
  { can: false, text: 'Reach an earlier revision: the link always shows the current one' },
];

/**
 * What a share link is, what it gives away, and how to take it back. The
 * worry underneath is always the same: who can see my draft now? So the answer
 * leads. Anyone holding the link, nobody else, and only for as long as you leave
 * it on.
 */
export function SharingTopic({ onOpenTopic }: HelpTopicBodyProps) {
  return (
    <div className="space-y-5">
      <section>
        <SectionTitle>One link, read-only</SectionTitle>
        <p className="text-foreground/80 leading-relaxed">
          A project is private until you share it. Sharing creates a{' '}
          <strong className="text-foreground font-medium">public link that anyone can open</strong>, with or without a
          Draft Detective account. It shows the project as you see it, minus everything that would change it: a reader
          can look at the draft and every finding, and can touch none of it.
        </p>

        <div className="mt-2 overflow-hidden rounded-md border">
          <div className="flex items-center gap-2 border-b px-3 py-2">
            <span className="min-w-0 flex-1 truncate rounded border bg-background/60 px-2 py-1 font-mono text-[11px] text-muted-foreground">
              https://…/share/kQ3vX9mB2pLw7RtYcN4eZg
            </span>
            <span className="bg-primary text-primary-foreground shrink-0 rounded p-1" aria-hidden>
              <Check className="size-3" />
            </span>
            <span className="text-xs text-green-600 dark:text-green-400">Copied</span>
          </div>
          <div className="flex items-center gap-2 px-3 py-2">
            <span className="rounded border border-green-200 bg-green-50 px-1.5 py-0.5 text-[10px] font-medium text-green-700 dark:border-green-800 dark:bg-green-950 dark:text-green-300">
              <Link2 className="mr-1 inline size-3 align-[-0.15em]" aria-hidden />
              Sharing enabled
            </span>
            <span className="text-xs text-muted-foreground">What the header shows while a link exists.</span>
          </div>
        </div>

        <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
          The address ends in a long random code that cannot be guessed, so the link itself is the key. Whoever you send
          it to can send it on, and nobody is told when it is opened.
        </p>
      </section>

      <section>
        <SectionTitle>Creating one</SectionTitle>
        <div className="space-y-2">
          {STEPS.map((step) => (
            <Step key={step.title} icon={step.icon} title={step.title}>
              {step.body}
            </Step>
          ))}
        </div>
        <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
          Only the person whose project it is can share it. Each project has its own link, and sharing one says nothing
          about the others.
        </p>
      </section>

      <section>
        <SectionTitle>What a reader can and can&apos;t do</SectionTitle>
        <ul className="space-y-1.5">
          {READER_ABILITIES.map((ability) => (
            <li key={ability.text} className="flex gap-1.5 text-xs leading-relaxed">
              {ability.can ? (
                <Check className="mt-0.5 size-3 shrink-0 text-green-600 dark:text-green-400" aria-hidden />
              ) : (
                <X className="mt-0.5 size-3 shrink-0 text-muted-foreground" aria-hidden />
              )}
              <span className={ability.can ? 'text-foreground/80' : 'text-muted-foreground'}>{ability.text}</span>
            </li>
          ))}
        </ul>
        <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
          The page is live, not a snapshot. Resolve an{' '}
          <TopicLink to="issues" onOpenTopic={onOpenTopic}>
            issue
          </TopicLink>
          , run another assessment, or upload a{' '}
          <TopicLink to="revisions" onOpenTopic={onOpenTopic}>
            revision
          </TopicLink>
          , and the link shows the new state the next time it is opened. Your own ratings are the exception: the thumbs
          never appear on a shared page, whoever is looking, so previewing your link shows you exactly what a reader
          gets.
        </p>
      </section>

      <section>
        <SectionTitle>Turning it off</SectionTitle>
        <p className="text-foreground/80 leading-relaxed">
          Open the share dialog again, from the badge or the menu, and choose{' '}
          <strong className="text-foreground font-medium">Disable</strong>.{' '}
          <strong className="text-foreground font-medium">Every copy of the link stops working at once</strong>; anyone
          opening it sees only that the link was not found. Your project is untouched.
        </p>
        <div className="mt-2 flex items-start gap-2 rounded-md border p-2.5">
          <Link2Off className="mt-0.5 size-3.5 shrink-0 text-muted-foreground" aria-hidden />
          <div className="min-w-0">
            <p className="text-xs font-medium">Re-enabling creates a new address</p>
            <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">
              The old one stays dead. Turning sharing off and on again is how you cut off everyone who had the link
              while keeping the project shareable.
            </p>
          </div>
        </div>
      </section>

      <section>
        <SectionTitle>Where else sharing comes up</SectionTitle>
        <ul className="space-y-1.5">
          <Fact term="Export to Word">
            The download offers to add a link to each comment, pointing at that issue on the shared page. Ticking it
            turns sharing on, exactly as the dialog would, because the links are useless otherwise.
          </Fact>
          <Fact
            term={
              <TopicLink to="feedback" onOpenTopic={onOpenTopic}>
                Feedback visibility
              </TopicLink>
            }
          >
            A different setting. It decides what Draft Detective&apos;s administrators may see of your project when you
            rate a finding, and has nothing to do with the link. Sharing a project does not share your feedback, and
            sharing your feedback creates no link.
          </Fact>
        </ul>
      </section>
    </div>
  );
}

function Step({ icon: Icon, title, children }: { icon: LucideIcon; title: string; children: ReactNode }) {
  return (
    <div className="flex gap-2.5 rounded-md border p-2.5">
      <Icon className="mt-0.5 size-3.5 shrink-0 text-muted-foreground" aria-hidden />
      <div className="min-w-0">
        <p className="text-xs font-medium">{title}</p>
        <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">{children}</p>
      </div>
    </div>
  );
}

function Fact({ term, children }: { term: ReactNode; children: ReactNode }) {
  return (
    <li className="text-xs leading-relaxed">
      <strong className="font-medium">{term}.</strong> <span className="text-muted-foreground">{children}</span>
    </li>
  );
}
