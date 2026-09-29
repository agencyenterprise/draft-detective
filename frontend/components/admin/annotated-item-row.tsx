'use client';

import { PassageDocument } from '@/components/annotate/passage-document';
import { Badge } from '@/components/ui/badge';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { AnnotationItemKind, type AnnotatedItem, type AnnotationRecord } from '@/lib/generated-api';
import { format } from 'date-fns';
import { ChevronDown, CircleCheck, CircleHelp, CircleX } from 'lucide-react';
import { useState } from 'react';

function answerText(answers: Record<string, string>): string {
  return Object.values(answers).join(', ');
}

function Verdict({ agrees }: { agrees: boolean | null | undefined }) {
  if (agrees === true) return <CircleCheck className="size-4 text-green-600" aria-label="Agrees" />;
  if (agrees === false) return <CircleX className="size-4 text-amber-600" aria-label="Disagrees" />;
  return <CircleHelp className="size-4 text-muted-foreground" aria-label="Not sure" />;
}

function AnnotationLine({ record }: { record: AnnotationRecord }) {
  return (
    <li className="flex gap-3 py-2 text-sm">
      <Verdict agrees={record.agrees} />
      <div className="min-w-0 flex-1">
        <p>
          <span className="font-medium">{record.user_name}</span>{' '}
          <span className="text-muted-foreground">({record.user_email})</span>{' '}
          <span className="text-muted-foreground">
            answered “{answerText(record.answers)}” · {format(new Date(record.created_at), 'MMM d, yyyy')}
            {record.time_spent_ms != null && ` · ${Math.round(record.time_spent_ms / 1000)}s`}
          </span>
        </p>
        {record.comment && <p className="mt-1 whitespace-pre-wrap">{record.comment}</p>}
      </div>
    </li>
  );
}

/** One annotated item: the passage and tallies, expanding to the document and every answer. */
export function AnnotatedItemRow({ item }: { item: AnnotatedItem }) {
  const [open, setOpen] = useState(false);

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <CollapsibleTrigger className="flex w-full items-start gap-3 px-3 py-2.5 text-left hover:bg-muted/50">
        <ChevronDown className={`mt-0.5 size-4 shrink-0 transition-transform ${open ? '' : '-rotate-90'}`} />
        <div className="min-w-0 flex-1 space-y-1">
          <p className="text-sm">“{item.passage.anchor}”</p>
          <div className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
            <Badge variant="outline" className="font-normal">
              Test case: {item.kind === AnnotationItemKind.ExpectedIssue ? 'flag' : 'leave alone'}
            </Badge>
            <span>
              {item.agreements} agree · {item.disagreements} disagree · {item.abstentions} not sure
            </span>
          </div>
        </div>
      </CollapsibleTrigger>
      <CollapsibleContent className="space-y-3 px-3 pb-3 pl-10">
        {item.reference_explanation && <p className="text-sm text-muted-foreground">{item.reference_explanation}</p>}
        <PassageDocument
          document={item.passage.document}
          anchor={item.passage.anchor}
          className="max-h-80 rounded-md border"
        />
        <ul className="divide-y">
          {item.annotations.map((record, index) => (
            <AnnotationLine key={`${record.user_email}-${index}`} record={record} />
          ))}
        </ul>
      </CollapsibleContent>
    </Collapsible>
  );
}
