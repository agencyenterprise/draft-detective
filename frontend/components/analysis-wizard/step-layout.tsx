'use client';

import { ReactNode } from 'react';

/**
 * The frame every wizard step draws in: a scrolling body on a centred column,
 * and, when the step has actions, a footer that stays put below it. The same
 * arrangement as the Run assessments dialog, so the step that lists a dozen
 * assessments never puts its buttons a scroll away.
 */
export function StepLayout({ children, footer }: { children: ReactNode; footer?: ReactNode }) {
  return (
    <>
      <main className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-4xl px-6 py-6">{children}</div>
      </main>
      {footer && (
        <footer className="shrink-0 border-t py-4">
          {/* Same column and gutter as the body, so the footer's edges line up with the list above. */}
          <div className="mx-auto w-full max-w-4xl space-y-3 px-6">{footer}</div>
        </footer>
      )}
    </>
  );
}

/** A step's title and the sentence under it, at the scale the project view uses for its headings. */
export function StepHeading({ title, children }: { title: string; children: ReactNode }) {
  return (
    <header className="space-y-1">
      <h1 className="text-base font-semibold tracking-tight">{title}</h1>
      <p className="text-[13px] leading-relaxed text-muted-foreground">{children}</p>
    </header>
  );
}
