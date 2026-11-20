'use client';

import { Button } from '@/components/ui/button';
import { FileText, FileUp } from 'lucide-react';
import { useState } from 'react';
import {
  FILE_OF,
  fileAnchor,
  fileContent,
  outputNames,
  OUTPUT_FILES,
  type FileLink,
  type Step,
} from './live-report-state';
import { Doc, ResearchProgress, Working } from './step-parts';
import type { LiveReport } from './use-live-report';

/** A step's own content: the upload box, its document, the research progress, or the outputs. */
interface StepBodyProps {
  step: Step;
  report: LiveReport;
  onStart: (file: File) => void;
  onFileLink: (link: FileLink) => void;
}

export function StepBody({ step, report, onStart, onFileLink }: StepBodyProps) {
  const { files } = report;
  if (step === 'upload') {
    // A finished upload shows what was uploaded; only the current one is a drop zone.
    if (report.step !== 'upload') return <UploadedReport name={report.title} />;
    if (report.conversation.length && !report.working) {
      return (
        <Notice>
          The agent stopped before it wrote the intake. Try again on the same report, or start a new live report.
        </Notice>
      );
    }
    return <UploadBox disabled={report.working} onFile={onStart} />;
  }
  if (step === 'research') {
    const items = report.research;
    const done = items.filter((item) => item.verdict).length;
    const stopped = report.step === 'research' && !report.working;
    return (
      <div className="flex flex-col gap-4">
        {stopped && !report.lastReply && (
          <Notice>
            The research stopped before it finished: {done} of {items.length} items are done. Resume it to research
            what&apos;s left (and any item you changed) and write the brief, or ask for changes to the plan.
          </Notice>
        )}
        <ResearchProgress items={items} running={report.working} />
      </div>
    );
  }
  if (step === 'outputs') {
    const addendum = fileContent(files, OUTPUT_FILES.addendum);
    const changePlan = fileContent(files, OUTPUT_FILES.changePlan);
    const { missing } = report;
    return (
      <div className="flex flex-col gap-10 [&>section+section]:border-t [&>section+section]:pt-10">
        {missing.length > 0 && (
          <Notice>
            The agent stopped before it wrote {outputNames(missing)}. Have it write {missing.length > 1 ? 'them' : 'it'}{' '}
            before approving.
          </Notice>
        )}
        {addendum && (
          <OutputDoc
            file={OUTPUT_FILES.addendum}
            label="For the report's readers"
            markdown={addendum}
            onFileLink={onFileLink}
          />
        )}
        {changePlan && (
          <OutputDoc
            file={OUTPUT_FILES.changePlan}
            label="For the authors"
            markdown={changePlan}
            onFileLink={onFileLink}
          />
        )}
      </div>
    );
  }
  const content = fileContent(files, FILE_OF[step]);
  return content ? <Doc markdown={content} onFileLink={onFileLink} /> : <Working label="Writing…" />;
}

interface OutputDocProps {
  file: string;
  label: string;
  markdown: string;
  onFileLink: (link: FileLink) => void;
}

function OutputDoc({ file, label, markdown, onFileLink }: OutputDocProps) {
  const [copied, setCopied] = useState(false);
  return (
    <section id={fileAnchor(file)} className="flex scroll-mt-6 flex-col gap-2">
      <div className="flex items-center gap-2">
        <span className="text-muted-foreground text-xs font-semibold tracking-wide uppercase">{label}</span>
        <Button
          variant="ghost"
          size="sm"
          className="ml-auto"
          onClick={() => navigator.clipboard.writeText(markdown).then(() => setCopied(true))}
        >
          {copied ? 'Copied' : 'Copy text'}
        </Button>
      </div>
      <Doc markdown={markdown} onFileLink={onFileLink} />
    </section>
  );
}

function UploadedReport({ name }: { name: string | null }) {
  return (
    <div className="flex items-center gap-3 rounded-lg border px-4 py-3 text-sm">
      <FileText className="text-muted-foreground size-5 shrink-0" />
      <span className="min-w-0 flex-1 truncate">{name ?? 'The uploaded report'}</span>
    </div>
  );
}

function UploadBox({ disabled, onFile }: { disabled: boolean; onFile: (file: File) => void }) {
  if (disabled) return <Working label="Reading the report and writing the intake…" />;
  return (
    <label
      className="hover:bg-muted/40 flex cursor-pointer flex-col items-center gap-3 rounded-lg border border-dashed py-12 text-center"
      onDragOver={(e) => e.preventDefault()}
      onDrop={(e) => {
        e.preventDefault();
        const file = e.dataTransfer.files[0];
        if (file) onFile(file);
      }}
    >
      <FileUp className="text-muted-foreground size-8" />
      <span className="text-sm">Drop a published report here (PDF or DOCX), or click to choose one.</span>
      <input
        type="file"
        accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        className="sr-only"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) onFile(file);
        }}
      />
    </label>
  );
}

/** Why a step stopped short, and what to do about it. */
function Notice({ children }: { children: React.ReactNode }) {
  return <p className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">{children}</p>;
}
