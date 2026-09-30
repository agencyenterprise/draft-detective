'use client';

import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';
import { ChevronDownIcon, ChevronUpIcon } from 'lucide-react';
import { useEffect } from 'react';

/**
 * The keys the stepper answers to.
 *
 * `n` and `p` are the ones it advertises: they say what they do to anyone who
 * has not read a shortcut list, which `j` and `k` only do for people who have.
 * The arrows are aliases for readers who reach for them first, and they are the
 * horizontal pair on purpose — the vertical two are how a keyboard scrolls a
 * document, and taking those would cost more than it gave.
 *
 * No modifier on any of them: a reader working through ninety findings presses
 * these a great many times.
 */
const KEYS = {
  // Spelled as `KeyboardEvent.key` spells them, since that is also how
  // `aria-keyshortcuts` names them to a screen reader. Compared case-insensitively.
  next: { shortcut: 'n', aliases: ['ArrowRight'] },
  previous: { shortcut: 'p', aliases: ['ArrowLeft'] },
} as const;

interface IssueNavProps {
  /** Where the reader stands in the walk, counting from one, or null before it. */
  position: number | null;
  total: number;
  onStep: (delta: 1 | -1) => void;
}

/**
 * Step to the next finding, or back to the one before it.
 *
 * Findings are not spread evenly through a document: it can carry nothing for
 * twenty pages and then eleven in a row. Without this the reader has to scroll
 * the whole quiet stretch to find that out, and in margin mode there is nothing
 * beside the text to tell them how much further to go.
 *
 * The count is here for the same reason — it answers how far through the review
 * they are, which neither the document nor the margin can say.
 *
 * Whether the width can carry this at all is the caller's to decide: stepping is
 * only worth offering while something on screen can show what it steps to.
 */
export function IssueNav({ position, total, onStep }: IssueNavProps) {
  if (total === 0) return null;

  return (
    <div className="flex items-center gap-0.5 rounded-md border p-0.5">
      <Step
        label="Previous issue"
        shortcut={KEYS.previous}
        icon={ChevronUpIcon}
        // Nothing open means the reader has not started, so there is nothing
        // behind them; the first press has to go forwards.
        disabled={position === null || position <= 1}
        onClick={() => onStep(-1)}
      />
      <span className="px-1 font-mono text-[11px] tabular-nums text-muted-foreground">
        {position ?? '–'}/{total}
      </span>
      <Step
        label="Next issue"
        shortcut={KEYS.next}
        icon={ChevronDownIcon}
        disabled={position !== null && position >= total}
        onClick={() => onStep(1)}
      />
    </div>
  );
}

/**
 * The things that hold the keyboard while they are up — menus and alerts as
 * much as plain dialogs, since each brings its own typeahead and its own
 * Escape.
 *
 * Roles rather than open-state attributes, because the app speaks two dialects:
 * Radix stamps `data-state="open"`, Headless UI stamps `data-open`, and the
 * user menu is the second kind. Whether one is up is asked of the focus
 * instead, which is the thing at issue and which no library can spell
 * differently. Tooltips are left out on purpose — one is open for as long as
 * the pointer rests on a button, and they take no focus.
 */
const OVERLAYS = '[role="dialog"],[role="alertdialog"],[role="menu"],[role="listbox"]';

export function overlayHasKeyboard(target: EventTarget | null): boolean {
  const focused = document.activeElement;
  if (focused instanceof HTMLElement && focused.closest(OVERLAYS)) return true;
  return target instanceof HTMLElement && !!target.closest(OVERLAYS);
}

/** Widgets that steer themselves with the arrow keys and must keep them. */
const ARROW_OWNERS = '[role="menu"],[role="listbox"],[role="radiogroup"],[role="tablist"],[role="slider"]';

export function isTyping(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName);
}

/**
 * Whether the arrows are already spoken for where the press landed.
 *
 * Either a widget that navigates itself with them, or a region with more to the
 * side than it can show: the document gives wide tables, code and maths their
 * own horizontal scroll, a browser lets the keyboard pan those, and taking Left
 * and Right would strand the part hanging off the edge.
 */
function ownsArrows(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  if (target.closest(ARROW_OWNERS)) return true;

  for (let node: HTMLElement | null = target; node; node = node.parentElement) {
    if (node.scrollWidth > node.clientWidth && /auto|scroll/.test(getComputedStyle(node).overflowX)) return true;
  }
  return false;
}

/**
 * The stepper's keyboard half.
 *
 * Bound only while the stepper itself is on screen, so a reader never presses a
 * key belonging to a control they cannot see, and the keys never move a
 * document whose findings are hidden.
 */
export function useIssueShortcuts({
  enabled,
  onStep,
  onClose,
}: {
  enabled: boolean;
  onStep: (delta: 1 | -1) => void;
  onClose: () => void;
}) {
  // A window subscription is what an effect is for: nothing here is derived and
  // nothing is rendered, and the listener has to be taken back down.
  useEffect(() => {
    if (!enabled) return;

    const handle = (event: KeyboardEvent) => {
      // Chords belong to the browser and the system, and an open dialog owns
      // the keyboard until it closes — the Escape that dismisses it included.
      if (event.metaKey || event.ctrlKey || event.altKey || event.shiftKey) return;
      if (isTyping(event.target) || overlayHasKeyboard(event.target)) return;

      const key = event.key.toLowerCase();
      if (event.key === 'Escape') {
        // Left to bubble: something else may want it, and there may be no open
        // finding for this to close.
        onClose();
        return;
      }

      if (key.startsWith('arrow') && ownsArrows(event.target)) return;

      const delta = matches(KEYS.next, key) ? 1 : matches(KEYS.previous, key) ? -1 : null;
      if (delta === null) return;

      event.preventDefault();
      onStep(delta);
    };

    window.addEventListener('keydown', handle);
    return () => window.removeEventListener('keydown', handle);
  }, [enabled, onStep, onClose]);
}

function matches(binding: { shortcut: string; aliases: readonly string[] }, key: string): boolean {
  return binding.shortcut === key || binding.aliases.some((alias) => alias.toLowerCase() === key);
}

function Step({
  label,
  shortcut,
  icon: Icon,
  disabled,
  onClick,
}: {
  label: string;
  shortcut: { shortcut: string; aliases: readonly string[] };
  icon: typeof ChevronUpIcon;
  disabled: boolean;
  onClick: () => void;
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          onClick={onClick}
          disabled={disabled}
          aria-label={label}
          // The name stays clean for a screen reader, which announces the keys
          // from here rather than reading the tooltip's decoration aloud.
          aria-keyshortcuts={[shortcut.shortcut, ...shortcut.aliases].join(' ')}
          className={cn(
            'flex size-5 items-center justify-center rounded-sm text-muted-foreground transition-colors',
            disabled ? 'opacity-40' : 'hover:bg-accent/60 hover:text-foreground cursor-pointer',
          )}
        >
          <Icon className="size-3.5" />
        </button>
      </TooltipTrigger>
      {/* The advertised key only. A tooltip listing every alias reads as a
          manual; the reader who reaches for an arrow finds it works anyway. */}
      <TooltipContent>
        {label}
        <kbd className="ml-1.5 rounded border border-current/30 px-1 font-mono text-[10px] uppercase opacity-80">
          {shortcut.shortcut}
        </kbd>
      </TooltipContent>
    </Tooltip>
  );
}
