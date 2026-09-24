'use client';

import { Button } from '@/components/ui/button';
import { UploadSection } from '@/components/analysis-form/upload-section';
import { FileRole } from '@/lib/generated-api';
import { AlertCircle, Check, Loader2, Rocket, AlertTriangle, FileWarning } from 'lucide-react';
import { useStepUpload } from './use-step-upload';
import { StepHeading, StepLayout } from './step-layout';
import { PreflightStatus } from './wizard-context';
import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';

interface StepUploadProps {
  onComplete: () => void;
}

export function StepUpload({ onComplete }: StepUploadProps) {
  const {
    mainDocument,
    preflightStatus,
    isLoading,
    canContinue,
    uploadStage,
    stageMessage,
    uploadProgress,
    handleDocumentChange,
    handleContinue,
  } = useStepUpload(onComplete);

  const footer = (
    <>
      {/* Upload progress bar */}
      {uploadStage === 'uploading' && uploadProgress && (
        <div className="space-y-1.5">
          <div className="flex justify-between text-xs text-muted-foreground">
            <span>Uploading...</span>
            <span className="tabular-nums">{uploadProgress.progress_percent}%</span>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-muted">
            <div
              className="h-full bg-primary transition-all duration-300"
              style={{ width: `${uploadProgress.progress_percent}%` }}
            />
          </div>
        </div>
      )}

      <div className="flex justify-end">
        <Button onClick={handleContinue} disabled={!canContinue}>
          {isLoading ? (
            <>
              <Loader2 className="size-4 animate-spin" />
              {stageMessage || 'Setting up your project...'}
            </>
          ) : (
            'Next: Choose your assessments'
          )}
        </Button>
      </div>
    </>
  );

  return (
    <StepLayout footer={footer}>
      <div className="space-y-6">
        <StepHeading title={"Let's start with your draft"}>
          Upload the document you&apos;d like us to review. We&apos;ll extract its content and prepare it for analysis.
          This becomes <strong>revision 1</strong> of the main document. You can add new revisions later as your draft
          evolves.
        </StepHeading>

        <UploadSection
          title="Your document"
          description="Drop your file here — we support Word (.docx) and PDF formats. Word is recommended for best results."
          required
          onFilesChange={handleDocumentChange}
          multiple={false}
          files={mainDocument ? [mainDocument] : []}
          fileType={FileRole.Main}
          onRemoveFile={() => handleDocumentChange([])}
        />

        {mainDocument && isPdf(mainDocument) && <PdfQualityNotice />}

        <p className="text-sm text-muted-foreground -mt-4">
          <span className="font-medium">Tip:</span> You can upload only a <strong>specific section</strong> of your
          document if you prefer. For example, upload just the references section if you&apos;re only interested in
          running citation or reference analyses. This could be a good option if you want a guarantee that the body of
          your document will not be exposed to LLMs or Web Search.
        </p>

        <PreflightChecklist preflightStatus={preflightStatus} />
      </div>
    </StepLayout>
  );
}

function isPdf(file: File): boolean {
  return file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf');
}

/** PDFs lose structure on conversion, so steer the user to the Word file while they can still swap it. */
function PdfQualityNotice() {
  return (
    <div
      role="status"
      className="-mt-2 flex items-start gap-2.5 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm dark:border-amber-900 dark:bg-amber-950/30"
    >
      <FileWarning aria-hidden className="mt-0.5 size-4 shrink-0 text-amber-700 dark:text-amber-400" />
      <p className="text-amber-900 dark:text-amber-200">
        <span className="font-medium">PDFs convert with lower quality than Word files.</span> Headings, tables,
        footnotes and references can come through incomplete or out of order, which makes the assessments less accurate.
        If you have the .docx version of this draft, upload that instead.
      </p>
    </div>
  );
}

type ChecklistPhase = 'idle' | 'pending' | 'valid' | 'invalid';

const PHASE_CONFIG: Record<ChecklistPhase, { icon: React.ReactNode; header: string; containerClass: string }> = {
  invalid: {
    icon: <AlertCircle className="w-4 h-4 text-destructive" />,
    header: 'Hmm, something needs attention',
    containerClass: 'border-destructive/50 bg-destructive/5',
  },
  valid: {
    icon: <Check className="w-4 h-4 text-green-600" />,
    header: 'All set! Ready to continue',
    containerClass: 'border-green-600/50 bg-green-50/50 dark:bg-green-950/20',
  },
  pending: {
    icon: <Loader2 className="w-4 h-4 animate-spin text-primary" />,
    header: 'Checking things over...',
    containerClass: 'border-primary/50 bg-primary/5',
  },
  idle: {
    icon: <Rocket className="w-4 h-4 text-muted-foreground" />,
    header: "Before we continue, we'll verify:",
    containerClass: 'border-muted-foreground/30 bg-muted/20',
  },
};

function PreflightChecklist({ preflightStatus }: { preflightStatus: { format: PreflightStatus } }) {
  const formatStatus = preflightStatus.format;

  const phase: ChecklistPhase =
    formatStatus === 'invalid'
      ? 'invalid'
      : formatStatus === 'valid'
        ? 'valid'
        : formatStatus === 'pending'
          ? 'pending'
          : 'idle';

  const { icon, header, containerClass } = PHASE_CONFIG[phase];

  return (
    <div className={cn('rounded-lg border p-4 space-y-3 transition-all duration-300', containerClass)}>
      <div className="flex items-center gap-2">
        {icon}
        <h3 className="text-sm font-medium">{header}</h3>
      </div>

      <div className="space-y-2">
        <ChecklistItem
          status={formatStatus}
          labels={{
            idle: 'Document format',
            pending: 'Checking document...',
            valid: 'Document ready',
            invalid: 'Document too large or unsupported',
          }}
        />
      </div>
    </div>
  );
}

const ITEM_CONFIG: Record<PreflightStatus, { icon: React.ReactNode; className: string }> = {
  idle: { icon: <AlertTriangle className="w-4 h-4 text-muted-foreground/60" />, className: 'text-muted-foreground' },
  pending: { icon: <Loader2 className="w-4 h-4 animate-spin text-primary" />, className: 'text-foreground' },
  valid: { icon: <Check className="w-4 h-4 text-green-600" />, className: 'text-green-700 dark:text-green-500' },
  invalid: { icon: <AlertCircle className="w-4 h-4 text-destructive" />, className: 'text-destructive' },
};

function ChecklistItem({ status, labels }: { status: PreflightStatus; labels: Record<PreflightStatus, string> }) {
  const { icon, className } = ITEM_CONFIG[status];

  return (
    <div className={cn('flex items-center gap-2 text-sm transition-colors duration-200', className)}>
      {icon}
      <span>{labels[status]}</span>
      {status === 'idle' && (
        <Badge variant="outline" className="ml-auto text-[10px] px-1.5 py-0">
          Awaiting Input
        </Badge>
      )}
    </div>
  );
}
