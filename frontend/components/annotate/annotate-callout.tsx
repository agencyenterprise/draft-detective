'use client';

import { Button } from '@/components/ui/button';
import { Sparkles, X } from 'lucide-react';
import Link from 'next/link';
import { useSyncExternalStore } from 'react';

const SNOOZED_UNTIL_KEY = 'annotate-callout-snoozed-until';
const SNOOZE_MS = 14 * 24 * 60 * 60 * 1000;
const listeners = new Set<() => void>();
// Stands in for storage when it is blocked, so dismissing still hides the card
// for the rest of the page view.
let snoozedThisPage = false;

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function isSnoozed(): boolean {
  if (snoozedThisPage) return true;
  try {
    return Date.now() < Number(window.localStorage.getItem(SNOOZED_UNTIL_KEY));
  } catch {
    return false;
  }
}

function snooze() {
  snoozedThisPage = true;
  try {
    window.localStorage.setItem(SNOOZED_UNTIL_KEY, String(Date.now() + SNOOZE_MS));
  } catch {
    // Storage blocked: the card hides for this page view only.
  }
  listeners.forEach((listener) => listener());
}

/**
 * The invitation to annotate: a card floating over the bottom corner of the
 * projects list, so it reads as a message rather than one more project.
 * "Not now" and the close button both snooze it for 14 days, per browser.
 * Hidden on the server render (the server snapshot says snoozed) so it never
 * flashes for someone who snoozed it; the account menu keeps a permanent link.
 */
export function AnnotateCallout() {
  const snoozed = useSyncExternalStore(subscribe, isSnoozed, () => true);
  if (snoozed) return null;

  return (
    <aside
      aria-label="Help improve Draft Detective"
      className="animate-in fade-in slide-in-from-bottom-4 fixed right-4 bottom-12 z-40 w-[min(22rem,calc(100vw-2rem))] overflow-hidden rounded-xl border bg-popover text-popover-foreground shadow-lg duration-500"
    >
      <div className="h-1 bg-gradient-to-r from-primary via-primary/60 to-amber-400" aria-hidden />
      <div className="relative p-4">
        <Button
          size="icon"
          variant="ghost"
          aria-label="Dismiss"
          onClick={snooze}
          className="absolute top-2 right-2 size-7 text-muted-foreground"
        >
          <X className="size-3.5" />
        </Button>
        <div className="flex size-8 items-center justify-center rounded-full bg-primary/10 text-primary">
          <Sparkles className="size-4" />
        </div>
        <p className="mt-3 pr-6 text-sm font-semibold">Want to help make Draft Detective more accurate?</p>
        <p className="mt-1 text-[13px] leading-snug text-muted-foreground">
          Tell us whether you would flag a few example sentences. It takes a couple of minutes, and you can stop any
          time.
        </p>
        <div className="mt-3 flex items-center gap-2">
          <Button size="sm" asChild>
            <Link href="/annotate">Take a look</Link>
          </Button>
          <Button size="sm" variant="ghost" className="text-muted-foreground" onClick={snooze}>
            Not now
          </Button>
        </div>
      </div>
    </aside>
  );
}
