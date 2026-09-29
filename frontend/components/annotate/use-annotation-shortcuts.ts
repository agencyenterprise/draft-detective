import { isTyping, overlayHasKeyboard } from '@/components/results/document-explorer/issue-nav';
import { useEffect } from 'react';

/**
 * Window-level keys for the annotation screen, guarded the way the document
 * explorer's issue stepper is: never while typing, under a chord, or while a
 * menu or dialog holds the keyboard. `onKey` returns true when it used the key;
 * it may be a new function every render, and is resubscribed when it is.
 */
export function useAnnotationShortcuts(onKey: (key: string) => boolean) {
  // A window subscription is what an effect is for: nothing is derived or
  // rendered here, and the listener has to be taken back down.
  useEffect(() => {
    const handle = (event: KeyboardEvent) => {
      if (event.metaKey || event.ctrlKey || event.altKey) return;
      if (isTyping(event.target) || overlayHasKeyboard(event.target)) return;
      if (onKey(event.key)) event.preventDefault();
    };
    window.addEventListener('keydown', handle);
    return () => window.removeEventListener('keydown', handle);
  }, [onKey]);
}
