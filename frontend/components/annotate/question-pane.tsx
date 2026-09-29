'use client';

import { Kbd } from '@/components/annotate/kbd';
import { SectionLabel } from '@/components/annotate/section-label';
import { Markdown } from '@/components/markdown';
import { useAnnotationShortcuts } from '@/components/annotate/use-annotation-shortcuts';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { getErrorMessage } from '@/lib/api-error';
import type { AnnotationPassage, AnnotationQuestion } from '@/lib/generated-api';
import { useSubmitAnnotation } from '@/lib/hooks/use-annotations';
import { RAIL_ITEM_ACTIVE, RAIL_ITEM_IDLE } from '@/lib/rail-style';
import { cn } from '@/lib/utils';
import { Check, Loader2 } from 'lucide-react';
import { KeyboardEvent, useState } from 'react';
import { toast } from 'sonner';

interface QuestionPaneProps {
  itemId: string;
  passage: AnnotationPassage;
  questions: AnnotationQuestion[];
  /** Markdown describing what the check flags, shown below the question. */
  guidance: string;
  /** When the item was shown, to report how long the first answer took. */
  shownAt: number;
  onNext: () => void;
  onSkip: () => void;
}

/**
 * The right-hand pane: the question first, once answered a place for a
 * comment, then the highlighted passage and the check's guidance for reference. It never says how the test case answered, so one example
 * cannot teach the annotator what the next one "should" be. Keyed by item
 * upstream, so its state starts fresh for every item.
 */
export function QuestionPane({ itemId, passage, questions, guidance, shownAt, onNext, onSkip }: QuestionPaneProps) {
  const [answers, setAnswers] = useState<Record<string, string>>({});
  // What the server last stored, so a failed change can fall back to it: the
  // selection on screen must never claim an answer that was not saved.
  const [savedAnswers, setSavedAnswers] = useState<Record<string, string> | null>(null);
  const saved = savedAnswers !== null;
  const [comment, setComment] = useState('');
  const submit = useSubmitAnnotation();

  const choose = (key: string, value: string) => {
    const next = { ...answers, [key]: value };
    setAnswers(next);
    if (!questions.every((q) => next[q.key])) return;
    submit.mutate(
      { itemId, submission: { answers: next, time_spent_ms: saved ? undefined : Date.now() - shownAt } },
      {
        onSuccess: () => setSavedAnswers(next),
        onError: (error) => {
          setAnswers(savedAnswers ?? {});
          toast.error(getErrorMessage(error, 'Could not save your answer'));
        },
      },
    );
  };

  const next = async () => {
    if (!saved) return;
    if (comment.trim()) {
      try {
        await submit.mutateAsync({ itemId, submission: { answers, comment } });
      } catch (error) {
        toast.error(getErrorMessage(error, 'Could not save your comment'));
        return;
      }
    }
    onNext();
  };

  // Shortcuts pick from the first question; every set asks one. A fresh handler
  // each render, so it always sees the current answers and comment.
  useAnnotationShortcuts((key) => {
    const option = questions[0]?.options.find((o) => o.shortcut === key);
    if (option && !submit.isPending) {
      choose(questions[0].key, option.value);
      return true;
    }
    if (key === 'Enter' && saved) {
      void next();
      return true;
    }
    if (key.toLowerCase() === 's' && !saved) {
      onSkip();
      return true;
    }
    return false;
  });

  const onCommentKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) {
      event.preventDefault();
      void next();
    }
  };

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="min-h-0 flex-1 overflow-y-auto">
        {questions.map((question) => (
          <section key={question.key} className="border-b px-4 py-4">
            <p id={`q-${question.key}`} className="text-[13.5px] leading-snug font-medium">
              {question.prompt}
            </p>
            <div role="radiogroup" aria-labelledby={`q-${question.key}`} className="mt-3 space-y-px">
              {question.options.map((option) => {
                const on = answers[question.key] === option.value;
                return (
                  <button
                    key={option.value}
                    role="radio"
                    aria-checked={on}
                    disabled={submit.isPending}
                    onClick={() => choose(question.key, option.value)}
                    className={cn(
                      '-mx-2 flex w-[calc(100%+1rem)] cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-colors disabled:cursor-wait',
                      on ? RAIL_ITEM_ACTIVE : RAIL_ITEM_IDLE,
                    )}
                  >
                    <span
                      className={cn(
                        'flex size-3.5 shrink-0 items-center justify-center rounded-full border',
                        on ? 'border-foreground' : 'border-muted-foreground/50',
                      )}
                    >
                      {on && <span className="size-1.5 rounded-full bg-foreground" />}
                    </span>
                    <span className="flex-1 text-left">{option.label}</span>
                    {option.shortcut && (
                      <span className="font-mono text-[11px] tabular-nums text-muted-foreground">
                        {option.shortcut}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          </section>
        ))}

        {saved && (
          <section className="px-4 pt-4">
            <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <Check className="size-3.5" /> Answer saved. You can change it until you move on.
            </p>
            <Textarea
              value={comment}
              onChange={(event) => setComment(event.target.value)}
              onKeyDown={onCommentKeyDown}
              placeholder="Anything we should know about this one? (optional)"
              rows={3}
              maxLength={4000}
              className="mt-3 text-sm"
            />
          </section>
        )}

        {/* In the flow rather than pinned to the pane's foot, where the
            version badge floats over the corner. */}
        <div className="flex items-center gap-2 px-4 py-4">
          {!saved && (
            <Button variant="ghost" size="xs" className="-ml-2 text-muted-foreground" onClick={onSkip}>
              Skip <Kbd>S</Kbd>
            </Button>
          )}
          {submit.isPending && <Loader2 className="size-3.5 animate-spin text-muted-foreground" />}
          <Button size="xs" className="ml-auto" disabled={!saved || submit.isPending} onClick={() => void next()}>
            {comment.trim() ? 'Save and next' : 'Next example'}
            <Kbd>{comment.trim() ? '⌘↵' : '↵'}</Kbd>
          </Button>
        </div>

        <section className="border-t px-4 py-4">
          <SectionLabel>Highlighted passage</SectionLabel>
          <blockquote className="mt-2 border-l-2 border-amber-500 pl-3 text-[13.5px] leading-snug">
            {passage.anchor}
          </blockquote>
        </section>

        <section className="border-t px-4 py-4">
          <SectionLabel>What this check looks for</SectionLabel>
          <div className="mt-2 text-[13px] leading-relaxed text-muted-foreground [&_li]:mb-1.5 [&_li]:ml-3 [&_strong]:text-foreground [&_ul]:mb-3">
            <Markdown>{guidance}</Markdown>
          </div>
        </section>
      </div>
    </div>
  );
}
