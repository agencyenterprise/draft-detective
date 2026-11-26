'use client';

import { Markdown } from '@/components/markdown';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';
import { ChevronRight, Circle, Loader2, MessageSquareText } from 'lucide-react';
import { defaultUrlTransform } from 'react-markdown';
import { useState } from 'react';
import {
  fileAnchor,
  fileLinkOf,
  type AuthorQuestion,
  type FileLink,
  type Outputs,
  type ResearchItem,
  type Step,
  type VerdictKind,
  verdictKind,
} from './live-report-state';

const TONES: Record<VerdictKind, string> = {
  holds: 'bg-emerald-50 text-emerald-800 border-emerald-200',
  update: 'bg-sky-50 text-sky-800 border-sky-200',
  caution: 'bg-amber-50 text-amber-900 border-amber-200',
  broken: 'bg-rose-50 text-rose-800 border-rose-200',
  nothing: 'bg-muted text-muted-foreground',
};

const toneOf = (label: string) => TONES[verdictKind(label)];

export function VerdictBadge({ label }: { label: string }) {
  return (
    <Badge variant="outline" className={cn('shrink-0 font-medium', toneOf(label))}>
      {label}
    </Badge>
  );
}

/** Keeps the agent's links to its own files (`sandbox:/live-report/…`), which the default drops as unsafe. */
function keepFileLinks(url: string): string {
  return fileLinkOf(url) ? url.replace(/^sandbox:/, '') : defaultUrlTransform(url);
}

/**
 * A markdown document. With `onFileLink`, a link to one of the run's files opens
 * it on the page instead of following the link.
 */
export function Doc({ markdown, onFileLink }: { markdown: string; onFileLink?: (link: FileLink) => void }) {
  return (
    <div
      className="max-w-none text-sm leading-relaxed"
      onClick={(event) => {
        const link = fileLinkOf((event.target as HTMLElement).closest('a')?.getAttribute('href'));
        if (link && onFileLink) {
          event.preventDefault();
          onFileLink(link);
        }
      }}
    >
      {/* No images: a web page a researcher read could plant one whose URL carries
          data out, and the browser would fetch it as soon as the note shows. */}
      <Markdown urlTransform={onFileLink ? keepFileLinks : undefined} disallowedElements={['img']}>
        {markdown}
      </Markdown>
    </div>
  );
}

export function Working({ label }: { label: string }) {
  return (
    <span className="text-muted-foreground inline-flex items-center gap-2 text-sm">
      <Loader2 className="size-4 animate-spin" /> {label}
    </span>
  );
}

/** Suggestions per step; each one is a message the button sends. */
const PRESETS: Partial<Record<Step, string[]>> = {
  intake: ['The publication date is wrong', 'Put the summary and recommendations in scope'],
  plan: ['Drop the items that matter least', 'Add an angle on new legislation', 'Prefer official sources'],
  brief: ['Make it shorter', 'Look for more recent sources'],
  outputs: ['Make the addendum shorter', 'Make the change plan shorter', 'Use a more formal tone'],
};

/** "Ask for changes": pick a suggestion or describe one. Also how to answer the agent. */
export function RefineBox({
  step,
  disabled,
  onSend,
}: {
  step: Step;
  disabled: boolean;
  onSend: (text: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState('');
  const send = (message: string) => {
    onSend(message);
    setText('');
    setOpen(false);
  };
  if (!open) {
    return (
      <Button variant="outline" disabled={disabled} onClick={() => setOpen(true)}>
        <MessageSquareText className="size-4" /> Ask for changes
      </Button>
    );
  }
  return (
    <div className="bg-muted/40 flex w-full flex-col gap-2 rounded-lg border p-3">
      <div className="flex flex-wrap gap-2">
        {(PRESETS[step] ?? []).map((preset) => (
          <Button key={preset} variant="secondary" size="sm" disabled={disabled} onClick={() => send(preset)}>
            {preset}
          </Button>
        ))}
      </div>
      <Textarea
        autoFocus
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Or describe the change, or answer the agent, in your own words"
        className="bg-background min-h-16"
      />
      <div className="flex justify-end gap-2">
        <Button variant="ghost" size="sm" onClick={() => setOpen(false)}>
          Cancel
        </Button>
        <Button size="sm" disabled={disabled || !text.trim()} onClick={() => send(text.trim())}>
          Send
        </Button>
      </div>
    </div>
  );
}

export function ResearchProgress({ items, running }: { items: ResearchItem[]; running: boolean }) {
  if (!items.length) return running ? <Working label="Starting the research…" /> : null;
  return (
    <ul className="flex flex-col divide-y rounded-lg border">
      {items.map((item) => (
        <ResearchRow key={item.id} item={item} running={running} />
      ))}
    </ul>
  );
}

/** One research item. Once its note is written, it opens to show the note in full. */
function ResearchRow({ item, running }: { item: ResearchItem; running: boolean }) {
  const [open, setOpen] = useState(false);
  return (
    <li id={fileAnchor(`research/${item.id}.md`)} className="scroll-mt-6 text-sm">
      <button
        type="button"
        disabled={!item.note}
        aria-expanded={open}
        onClick={() => setOpen(!open)}
        className={cn(
          'hover:bg-muted/50 flex w-full gap-3 px-3 py-2 text-left disabled:cursor-default disabled:hover:bg-transparent',
          // Open, the item's text wraps in full, so the icons sit on its first line.
          open ? 'items-start' : 'items-center',
        )}
      >
        {item.note ? (
          <ChevronRight
            className={cn('text-muted-foreground size-4 shrink-0 transition-transform', open && 'rotate-90')}
          />
        ) : running ? (
          <Loader2 className="text-muted-foreground size-4 shrink-0 animate-spin" />
        ) : (
          <Circle className="text-muted-foreground/50 size-4 shrink-0" />
        )}
        <span className="w-7 shrink-0 font-mono text-xs">{item.id}</span>
        <span className={cn('min-w-0 flex-1', !open && 'truncate')} title={open ? undefined : item.text}>
          {item.text}
        </span>
        {item.verdict ? (
          <VerdictBadge label={item.verdict} />
        ) : (
          !running && <span className="text-muted-foreground text-xs">Not researched yet</span>
        )}
      </button>
      {open && item.note && (
        <div className="bg-muted/20 border-t px-6 py-4">
          <Doc markdown={item.note} />
        </div>
      )}
    </li>
  );
}

export function OutputChoice({ value, onChange }: { value: Outputs; onChange: (next: Outputs) => void }) {
  const options: { key: keyof Outputs; title: string; hint: string }[] = [
    { key: 'addendum', title: 'Addendum', hint: 'A section to publish with the report, for its readers' },
    { key: 'changePlan', title: 'Change plan', hint: 'What the authors should revise, section by section' },
  ];
  return (
    <div className="grid gap-2 sm:grid-cols-2">
      {options.map((option) => (
        <label
          key={option.key}
          className={cn(
            'flex cursor-pointer items-start gap-3 rounded-lg border p-3',
            value[option.key] && 'border-primary bg-primary/5',
          )}
        >
          <Checkbox
            checked={value[option.key]}
            onCheckedChange={(checked) => onChange({ ...value, [option.key]: checked === true })}
          />
          <span className="flex flex-col">
            <span className="text-sm font-medium">{option.title}</span>
            <span className="text-muted-foreground text-xs">{option.hint}</span>
          </span>
        </label>
      ))}
    </div>
  );
}

/** The brief's checkpoint: answer what you can and pick the outputs. The approve button is in the footer. */
export function BriefForm({
  questions,
  answers,
  onAnswers,
  outputs,
  onOutputs,
}: {
  questions: AuthorQuestion[];
  answers: string[];
  onAnswers: (answers: string[]) => void;
  outputs: Outputs;
  onOutputs: (outputs: Outputs) => void;
}) {
  return (
    <div className="flex flex-col gap-5 border-t pt-5">
      {questions.length > 0 && (
        <div className="flex flex-col gap-3">
          <h3 className="text-sm font-semibold">Questions for the authors</h3>
          {questions.map((q, i) => (
            <div key={`${q.about}-${i}`} className="flex flex-col gap-1">
              <Label htmlFor={`question-${i}`} className="text-sm leading-snug font-normal">
                {q.about && <span className="font-mono text-xs">{q.about}</span>} {q.text}
              </Label>
              <Textarea
                id={`question-${i}`}
                placeholder="Optional. Leave empty to keep it open for the authors."
                value={answers[i] ?? ''}
                onChange={(e) => onAnswers(Object.assign([...answers], { [i]: e.target.value }))}
                className="min-h-12"
              />
            </div>
          ))}
        </div>
      )}
      <div className="flex flex-col gap-2">
        <h3 className="text-sm font-semibold">What to write</h3>
        <OutputChoice value={outputs} onChange={onOutputs} />
      </div>
    </div>
  );
}
