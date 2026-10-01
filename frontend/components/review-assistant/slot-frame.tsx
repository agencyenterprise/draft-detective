import { ReactNode } from 'react';

interface SlotFrameProps {
  label: string;
  hint: string;
  optional: boolean;
  /** The section's header action, e.g. its upload button. */
  action?: ReactNode;
  children: ReactNode;
}

/** One input in the Inputs pane, in the same section shape as the Peer Review memos pane. */
export function SlotFrame({ label, hint, optional, action, children }: SlotFrameProps) {
  return (
    <section className="space-y-2 py-4">
      <div>
        <div className="flex h-6 items-center gap-2">
          <h3 className="font-mono text-[10px] tracking-wide text-muted-foreground uppercase">{label}</h3>
          {optional && (
            <span className="bg-muted rounded px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
              Optional
            </span>
          )}
          {action && <span className="ml-auto">{action}</span>}
        </div>
        <p className="text-[11px] leading-relaxed text-muted-foreground">{hint}</p>
      </div>
      {children}
    </section>
  );
}
