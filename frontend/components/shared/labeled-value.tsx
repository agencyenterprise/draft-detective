export interface LabeledValueProps {
  label: string;
  children: React.ReactNode;
  className?: string;
}

export function LabeledValue({ label, children, className }: LabeledValueProps) {
  return (
    <div className={className}>
      <div className="inline font-medium">{label}:</div> <div className="inline text-foreground">{children}</div>
    </div>
  );
}
