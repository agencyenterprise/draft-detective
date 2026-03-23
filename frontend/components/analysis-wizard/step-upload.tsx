'use client';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { UploadSection } from '@/components/analysis-form/upload-section';
import { AlertCircle, Check, Loader2, Eye, EyeOff, Rocket, AlertTriangle } from 'lucide-react';
import { useStepUpload } from './use-step-upload';
import { PreflightStatus } from './wizard-context';
import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';

interface StepUploadProps {
  onComplete: () => void;
}

export function StepUpload({ onComplete }: StepUploadProps) {
  const {
    mainDocument,
    apiKey,
    showApiKey,
    preflightStatus,
    hideApiKeyInput,
    isLoading,
    isValidating,
    canContinue,
    uploadStage,
    stageMessage,
    uploadProgress,
    setShowApiKey,
    handleDocumentChange,
    handleApiKeyChange,
    handleContinue,
  } = useStepUpload(onComplete);

  return (
    <div className="space-y-8">
      <div className="space-y-2">
        <h1 className="text-2xl font-bold">Let&apos;s start with your draft</h1>
        <p className="text-muted-foreground">
          Upload the document you&apos;d like us to review. We&apos;ll extract its content and prepare it for analysis.
        </p>
      </div>

      <UploadSection
        title="Your document"
        description="Drop your file here — we support Word (.docx) and PDF formats. Word is recommended for best results."
        required
        onFilesChange={handleDocumentChange}
        multiple={false}
        files={mainDocument ? [mainDocument] : []}
        fileType="main"
        onRemoveFile={() => handleDocumentChange([])}
      />

      <p className="text-sm text-muted-foreground -mt-4">
        <span className="font-medium">Tip:</span> You can upload only a <strong>specific section</strong> of your
        document if you prefer. For example, upload just the references section if you&apos;re only interested in
        running citation or reference analyses. This could be a good option if you don&apos;t want to{' '}
        <strong>expose your whole document</strong> to LLMs or Web Search.
      </p>

      {!hideApiKeyInput && (
        <div className="space-y-2">
          <Label htmlFor="openai-api-key">
            Your OpenAI API Key <span className="text-destructive ml-1">*</span>
          </Label>
          <div className="relative">
            <Input
              id="openai-api-key"
              type={showApiKey ? 'text' : 'password'}
              placeholder="sk-..."
              value={apiKey}
              onChange={(e) => handleApiKeyChange(e.target.value)}
              disabled={isLoading}
              className="pr-10"
            />
            <button
              type="button"
              onClick={() => setShowApiKey(!showApiKey)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
              tabIndex={-1}
            >
              {showApiKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          </div>
          <p className="text-sm text-muted-foreground">
            We use this to run the AI analysis. It&apos;s never stored on our servers.
          </p>
        </div>
      )}

      <PreflightChecklist preflightStatus={preflightStatus} hideApiKeyInput={hideApiKeyInput} />

      <div className="space-y-3">
        {/* Upload progress bar */}
        {uploadStage === 'uploading' && uploadProgress && (
          <div className="space-y-2">
            <div className="flex justify-between text-sm text-muted-foreground">
              <span>Uploading...</span>
              <span>{uploadProgress.progress_percent}%</span>
            </div>
            <div className="h-2 bg-muted rounded-full overflow-hidden">
              <div
                className="h-full bg-primary transition-all duration-300"
                style={{ width: `${uploadProgress.progress_percent}%` }}
              />
            </div>
          </div>
        )}

        <Button onClick={handleContinue} disabled={!canContinue} size="lg" className="w-full">
          {isLoading ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin mr-2" />
              {isValidating ? 'Validating...' : stageMessage || 'Setting up your project...'}
            </>
          ) : (
            'Next: Choose your analyses →'
          )}
        </Button>
      </div>
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

function PreflightChecklist({
  preflightStatus,
  hideApiKeyInput,
}: {
  preflightStatus: { apiKey: PreflightStatus; format: PreflightStatus };
  hideApiKeyInput: boolean;
}) {
  const apiKeyStatus = hideApiKeyInput ? 'valid' : preflightStatus.apiKey;
  const formatStatus = preflightStatus.format;

  // Determine phase (priority: invalid > valid > pending > idle)
  const phase: ChecklistPhase =
    apiKeyStatus === 'invalid' || formatStatus === 'invalid'
      ? 'invalid'
      : apiKeyStatus === 'valid' && formatStatus === 'valid'
        ? 'valid'
        : apiKeyStatus === 'pending' || formatStatus === 'pending'
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
        {!hideApiKeyInput && (
          <ChecklistItem
            status={apiKeyStatus}
            labels={{
              idle: 'API credentials',
              pending: 'Verifying API key...',
              valid: 'API key verified',
              invalid: 'API key invalid — please check and try again',
            }}
          />
        )}
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
