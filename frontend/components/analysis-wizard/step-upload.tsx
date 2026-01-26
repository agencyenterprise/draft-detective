'use client';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { UploadSection } from '@/components/analysis-form/upload-section';
import { AlertCircle, Check, Loader2, Eye, EyeOff } from 'lucide-react';
import { useStepUpload } from './use-step-upload';
import { PreflightStatus } from './wizard-context';

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

      <div className="space-y-3">
        <h3 className="text-lg font-semibold">Getting things ready...</h3>
        <div className="space-y-2">
          {!hideApiKeyInput && <ValidationItem label="API key looks good" status={preflightStatus.apiKey} />}
          <ValidationItem label="Document ready to process" status={preflightStatus.format} />
        </div>
      </div>

      <Button onClick={handleContinue} disabled={!canContinue} size="lg" className="w-full">
        {isLoading ? (
          <>
            <Loader2 className="w-4 h-4 animate-spin mr-2" />
            {isValidating ? 'Validating...' : 'Setting up your project...'}
          </>
        ) : (
          'Next: Choose your analyses →'
        )}
      </Button>
    </div>
  );
}

function ValidationItem({ label, status }: { label: string; status: PreflightStatus }) {
  const icons = {
    idle: <div className="w-5 h-5 rounded-full border-2 border-muted-foreground/30" />,
    pending: <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />,
    valid: <Check className="w-5 h-5 text-green-600" />,
    invalid: <AlertCircle className="w-5 h-5 text-destructive" />,
  };

  return (
    <div className="flex items-center gap-2">
      {icons[status]}
      <span className={status === 'invalid' ? 'text-destructive' : 'text-foreground'}>{label}</span>
    </div>
  );
}
