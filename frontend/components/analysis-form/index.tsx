'use client';

import { StartAnalysisResponse } from '@/lib/generated-api';
import { uploadOrchestrator } from '@/lib/services/upload-orchestrator';
import { useForm } from '@tanstack/react-form';
import { useMutation } from '@tanstack/react-query';
import { AlertCircle, Loader2, Play } from 'lucide-react';
import { useRouter } from 'next/navigation';
import React from 'react';
import { Button } from '../ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card';
import { CheckboxWithDescription } from '../ui/checkbox-with-description';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Progress } from '../ui/progress';
import { RadioGroup, RadioGroupItemWithDescription } from '../ui/radio-group-with-description';
import { AnalysisConfig } from '../wizard/types';
import { UploadSection } from './upload-section';

export function AnalysisForm() {
  const router = useRouter();
  const [mainDocument, setMainDocument] = React.useState<File | null>(null);
  const [supportingDocuments, setSupportingDocuments] = React.useState<File[]>([]);
  const [uploadProgress, setUploadProgress] = React.useState(0);
  const [processingStage, setProcessingStage] = React.useState<'idle' | 'uploading' | 'complete'>('idle');

  const form = useForm({
    defaultValues: {
      reviewType: '',
      domain: '',
      targetAudience: '',
      documentPublicationDate: '',
      runLiteratureReview: false,
      runSuggestCitations: false,
      runReferenceValidation: false,
      webSearchConsent: false,
    },
    validators: {
      onChange: ({ value }) => {
        if (!value.reviewType) {
          return {
            fields: {
              reviewType: 'Review type is required',
            },
          };
        }

        if (value.runLiteratureReview || value.reviewType === 'live-reports') {
          if (!value.documentPublicationDate) {
            return {
              fields: {
                documentPublicationDate: 'Document publication date is required',
              },
            };
          }
        }
        if (value.runLiteratureReview || value.reviewType === 'live-reports' || value.runReferenceValidation) {
          if (!value.webSearchConsent) {
            return {
              fields: {
                webSearchConsent:
                  'Web search consent is required when using literature review, live reports, or reference validation',
              },
            };
          }
        }
        return undefined;
      },
    },
    onSubmit: ({ value }) => {
      if (!mainDocument) {
        return;
      }

      const allFiles = [mainDocument, ...supportingDocuments];
      const validation = uploadOrchestrator.validateFiles(allFiles);

      if (!validation.valid && validation.errors) {
        // Show validation errors
        return;
      }

      analysisMutation.mutate({
        mainDocument,
        supportingDocuments,
        config: {
          domain: value.domain,
          targetAudience: value.targetAudience,
          documentPublicationDate: value.documentPublicationDate,
          runLiveReports: value.reviewType === 'live-reports',
          runLiteratureReview: value.reviewType === 'peer-review' && value.runLiteratureReview,
          runSuggestCitations: value.reviewType === 'peer-review' && value.runSuggestCitations,
          runReferenceValidation: value.reviewType === 'peer-review' && value.runReferenceValidation,
        },
      });
    },
  });

  const analysisMutation = useMutation<
    StartAnalysisResponse,
    Error,
    {
      mainDocument: File;
      supportingDocuments: File[];
      config: AnalysisConfig;
    }
  >({
    mutationFn: async (data) => {
      return uploadOrchestrator.startAnalysisWithProgress(
        {
          mainDocument: data.mainDocument,
          supportingDocuments: data.supportingDocuments,
          config: {
            useToulmin: false,
            runLiteratureReview: data.config.runLiteratureReview,
            runSuggestCitations: data.config.runSuggestCitations,
            runLiveReports: data.config.runLiveReports,
            runReferenceValidation: data.config.runReferenceValidation,
            domain: data.config.domain || undefined,
            targetAudience: data.config.targetAudience || undefined,
            documentPublicationDate: data.config.documentPublicationDate
              ? new Date(data.config.documentPublicationDate)
              : undefined,
            sessionId: undefined,
          },
        },
        {
          onProgress: (progress) => {
            setUploadProgress(progress);
          },
          onStageChange: (stage) => {
            setProcessingStage(stage);
          },
        },
      );
    },
    onSuccess: (response) => {
      router.push(`/results/${response.workflowRunId}`);
    },
  });

  const removeFile = (type: 'main' | 'supporting', index?: number) => {
    if (type === 'main') {
      setMainDocument(null);
    } else if (typeof index === 'number') {
      const newFiles = supportingDocuments.filter((_, i) => i !== index);
      setSupportingDocuments(newFiles);
    }
  };

  const getStageInfo = () => {
    switch (processingStage) {
      case 'uploading':
        return {
          title: 'Uploading Documents',
          description: 'Uploading and converting your files...',
          detail: 'This may take a moment for large PDF files',
        };
      case 'complete':
        return {
          title: 'Upload Complete',
          description: 'Documents uploaded successfully',
          detail: 'Redirecting to analysis...',
        };
      default:
        return {
          title: 'Preparing Upload',
          description: 'Getting ready to upload your documents...',
          detail: 'Please wait',
        };
    }
  };

  if (analysisMutation.isPending) {
    const stageInfo = getStageInfo();

    return (
      <div className="space-y-6">
        <div className="text-center space-y-4">
          <Loader2 className="w-12 h-12 mx-auto animate-spin text-primary" />
          <h2 className="text-2xl font-bold">{stageInfo.title}</h2>
          <p className="text-muted-foreground max-w-md mx-auto">{stageInfo.description}</p>
        </div>
        <Card className="max-w-xl mx-auto">
          <CardContent className="py-8">
            <div className="space-y-4">
              <Progress value={uploadProgress} className="w-full" />
              <p className="text-sm text-center text-muted-foreground">{stageInfo.detail}</p>

              {processingStage === 'uploading' && uploadProgress > 0 && (
                <div className="text-center">
                  <p className="text-2xl font-semibold text-primary">{Math.round(uploadProgress)}%</p>
                  <p className="text-xs text-muted-foreground mt-1">
                    Uploading {mainDocument?.name}
                    {supportingDocuments.length > 0 &&
                      ` and ${supportingDocuments.length} supporting file${supportingDocuments.length > 1 ? 's' : ''}`}
                  </p>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (analysisMutation.isError) {
    return (
      <Card className="max-w-4xl mx-auto border-destructive">
        <CardHeader>
          <CardTitle className="text-destructive flex items-center gap-2">
            <AlertCircle className="h-5 w-5" />
            Analysis Failed
          </CardTitle>
          <CardDescription>There was an error processing your files</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="p-4 bg-destructive/10 border border-destructive/20 rounded-md">
            <p className="text-sm text-destructive whitespace-pre-line">
              {analysisMutation.error?.message || 'Failed to start analysis'}
            </p>
          </div>

          <Button
            onClick={() => {
              analysisMutation.reset();
              setUploadProgress(0);
              setProcessingStage('idle');
            }}
            variant="outline"
            className="w-full"
          >
            Try Again
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <form
      className="space-y-8"
      onSubmit={(e) => {
        e.preventDefault();
        e.stopPropagation();
        form.handleSubmit();
      }}
    >
      <div className="space-y-4">
        <div className="space-y-1">
          <h2 className="text-xl font-semibold">
            Review Type <span className="text-destructive">*</span>
          </h2>
          <p className="text-sm text-muted-foreground">Select the type of review to perform</p>
        </div>
        <form.Field name="reviewType">
          {(field) => (
            <RadioGroup
              value={field.state.value}
              onValueChange={(value) => field.handleChange(value)}
              disabled={analysisMutation.isPending}
              required={true}
              className="grid grid-cols-2 gap-3"
            >
              <div className="space-y-2">
                <RadioGroupItemWithDescription
                  id="peer-review"
                  value={field.state.value}
                  label="Peer Review"
                  description="Peer review analysis focusing on claim substantiation, evidence quality, and citation completeness."
                  disabled={analysisMutation.isPending}
                />
                {field.state.value === 'peer-review' && (
                  <>
                    <form.Field name="runReferenceValidation">
                      {(field) => (
                        <CheckboxWithDescription
                          id="use-reference-validation"
                          checked={field.state.value}
                          onCheckedChange={(checked) => field.handleChange(checked === true)}
                          label="Reference validation (Optional)"
                          description="Validates references by checking their online presence and verifying author, title, publisher, and year information using web search."
                          disabled={analysisMutation.isPending}
                        />
                      )}
                    </form.Field>
                    <form.Field name="runLiteratureReview">
                      {(field) => (
                        <CheckboxWithDescription
                          id="run-literature-review"
                          checked={field.state.value}
                          onCheckedChange={(checked) => field.handleChange(checked === true)}
                          label="Literature review (Optional)"
                          description="Finds and recommends the most relevant, high-quality references (from published literature up to the document's publication date) that should be cited, using advanced web research and analysis of the document's content and bibliography."
                          disabled={analysisMutation.isPending}
                        />
                      )}
                    </form.Field>
                    <form.Field name="runSuggestCitations">
                      {(field) => (
                        <CheckboxWithDescription
                          id="run-suggest-citations"
                          checked={field.state.value}
                          onCheckedChange={(checked) => field.handleChange(checked === true)}
                          label="Suggest citations (Optional)"
                          description="Examines every claim in the document and recommends relevant citations, prioritizing supporting documents first and then incorporating literature review findings when available."
                          disabled={analysisMutation.isPending}
                        />
                      )}
                    </form.Field>
                    <form.Subscribe selector={(state) => [state.values.runLiteratureReview]}>
                      {(showWhenTrue) =>
                        showWhenTrue.some((value) => !!value) && (
                          <form.Field name="documentPublicationDate">
                            {(field) => (
                              <div className="space-y-1 pt-2">
                                <Label htmlFor="publication-date">
                                  Document Publication Date
                                  <span className="text-destructive ml-1">*</span>
                                </Label>
                                <Input
                                  id="publication-date"
                                  type="date"
                                  value={field.state.value}
                                  onChange={(e) => field.handleChange(e.target.value)}
                                  className={field.state.meta.errors.length > 0 ? 'border-destructive' : ''}
                                  disabled={analysisMutation.isPending}
                                  required={true}
                                />
                                {!field.state.meta.isValid && (
                                  <p className="text-sm text-destructive">{field.state.meta.errors.join(', ')}</p>
                                )}
                              </div>
                            )}
                          </form.Field>
                        )
                      }
                    </form.Subscribe>
                  </>
                )}
              </div>
              <div>
                <RadioGroupItemWithDescription
                  id="live-reports"
                  value={field.state.value}
                  label="Live Reports"
                  description="Analyze whether claims remain accurate given newer literature published after the document's publication date."
                  disabled={analysisMutation.isPending}
                />
                {field.state.value === 'live-reports' && (
                  <>
                    <form.Field name="documentPublicationDate">
                      {(field) => (
                        <div className="space-y-1 pt-2">
                          <Label htmlFor="publication-date">
                            Document Publication Date
                            <span className="text-destructive ml-1">*</span>
                          </Label>
                          <Input
                            id="publication-date"
                            type="date"
                            value={field.state.value}
                            onChange={(e) => field.handleChange(e.target.value)}
                            className={field.state.meta.errors.length > 0 ? 'border-destructive' : ''}
                            disabled={analysisMutation.isPending}
                            required={true}
                          />
                          {!field.state.meta.isValid && (
                            <p className="text-sm text-destructive">{field.state.meta.errors.join(', ')}</p>
                          )}
                        </div>
                      )}
                    </form.Field>
                  </>
                )}
              </div>

              {!field.state.meta.isValid && (
                <p className="text-sm text-destructive">{field.state.meta.errors.join(', ')}</p>
              )}
            </RadioGroup>
          )}
        </form.Field>
      </div>

      <form.Subscribe
        selector={(state) => [
          state.values.runLiteratureReview,
          state.values.reviewType,
          state.values.runReferenceValidation,
        ]}
      >
        {([runLiteratureReview, reviewType, runReferenceValidation]) =>
          (runLiteratureReview || reviewType === 'live-reports' || runReferenceValidation) && (
            <form.Field name="webSearchConsent">
              {(field) => (
                <div>
                  <div className="bg-yellow-50 border border-yellow-400 rounded-lg">
                    <CheckboxWithDescription
                      id="web-search-consent"
                      checked={field.state.value}
                      onCheckedChange={(checked) => field.handleChange(checked === true)}
                      label="I consent to perform web search using parts of the document"
                      description={`Web search is required to perform "literature review", "live reports", or "reference validation". Parts of the document will be used to perform web search, so we don't recommend using confidential information. Disable "literature review", "live reports", or "reference validation" if you don't consent to perform web search.`}
                    />
                  </div>
                  {!field.state.meta.isValid && (
                    <p className="text-sm text-destructive mt-1 pl-6">{field.state.meta.errors.join(', ')}</p>
                  )}
                </div>
              )}
            </form.Field>
          )
        }
      </form.Subscribe>

      <div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <UploadSection
            title="Main Document"
            description="Primary document for analysis"
            required={true}
            onFilesChange={(files) => setMainDocument(files[0] || null)}
            multiple={false}
            files={mainDocument ? [mainDocument] : []}
            fileType="main"
            onRemoveFile={() => removeFile('main')}
          />

          <UploadSection
            title="Supporting Documents"
            description="Documents used as references for the main document"
            required={false}
            onFilesChange={setSupportingDocuments}
            multiple={true}
            files={supportingDocuments}
            fileType="supporting"
            onRemoveFile={(index) => removeFile('supporting', index)}
          />
        </div>
      </div>

      {/* Additional Context Section */}
      <div className="space-y-4">
        <div className="space-y-1">
          <h2 className="text-xl font-semibold">Additional Context</h2>
          <p className="text-sm text-muted-foreground">Provide context for more accurate analysis</p>
        </div>
        <div className="space-y-4">
          <form.Field name="domain">
            {(field) => (
              <div className="space-y-2">
                <Label htmlFor="domain">
                  Domain <span className="text-muted-foreground text-xs font-normal">(Optional)</span>
                </Label>
                <Input
                  id="domain"
                  placeholder="e.g., Healthcare, Technology, Finance..."
                  value={field.state.value}
                  onChange={(e) => field.handleChange(e.target.value)}
                  disabled={analysisMutation.isPending}
                />
                <p className="text-sm text-muted-foreground">
                  The subject area or field of expertise to contextualize the analysis. This helps tailor the evaluation
                  to domain-specific standards and terminology.
                </p>
              </div>
            )}
          </form.Field>
          <form.Field name="targetAudience">
            {(field) => (
              <div className="space-y-2">
                <Label htmlFor="target-audience">
                  Target Audience <span className="text-muted-foreground text-xs font-normal">(Optional)</span>
                </Label>
                <Input
                  id="target-audience"
                  placeholder="e.g., General public, Experts, Students..."
                  value={field.state.value}
                  onChange={(e) => field.handleChange(e.target.value)}
                  disabled={analysisMutation.isPending}
                />
                <p className="text-sm text-muted-foreground">
                  The intended readers of the document. Specifying the audience helps adjust the analysis to match
                  appropriate complexity level and expectations.
                </p>
              </div>
            )}
          </form.Field>
        </div>
      </div>

      <div className="flex justify-center">
        <form.Subscribe selector={(state) => [state.canSubmit, state.isSubmitting]}>
          {([canSubmit]) => (
            <Button
              type="submit"
              disabled={!mainDocument || !canSubmit || analysisMutation.isPending}
              size="lg"
              className="min-w-48 gap-2 font-semibold"
            >
              {analysisMutation.isPending ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Processing...
                </>
              ) : (
                <>
                  <Play className="w-4 h-4" />
                  Start Analysis
                </>
              )}
            </Button>
          )}
        </form.Subscribe>
      </div>
    </form>
  );
}
