'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent } from '@/components/ui/card';
import { UploadSection } from '@/components/analysis-form/upload-section';
import { WorkflowTypeSelector } from '@/components/workflows/workflow-type-selector';
import { useWizard } from './wizard-context';
import { useWorkflowTypes } from '@/lib/hooks/use-workflow-types';
import { useSessionStorage } from '@/lib/hooks/use-session-storage';
import { hasSupportingDocumentsRequirement } from '@/components/workflows/utils';
import {
  WorkflowRunType,
  startMultipleWorkflowsApiWorkflowsStartMultiplePost,
  updateProjectEndpointApiProjectProjectIdPatch,
} from '@/lib/generated-api';
import { projectService } from '@/lib/services/project-service';
import { useMutation } from '@tanstack/react-query';
import { toast } from 'sonner';
import { Loader2 } from 'lucide-react';

export function StepAnalyses() {
  const router = useRouter();
  const wizard = useWizard();
  const { data: workflowTypes } = useWorkflowTypes();
  const [storedApiKey] = useSessionStorage<string>('openai-api-key', '');

  const [selectedWorkflowTypes, setSelectedWorkflowTypes] = useState<WorkflowRunType[]>([]);
  const [supportingDocuments, setSupportingDocuments] = useState<File[]>([]);
  const [domain, setDomain] = useState('');
  const [targetAudience, setTargetAudience] = useState('');

  const showSupportingDocs = hasSupportingDocumentsRequirement(selectedWorkflowTypes);

  const startAnalysisMutation = useMutation({
    mutationFn: async () => {
      if (!wizard.projectId) throw new Error('No project ID');
      if (selectedWorkflowTypes.length === 0) throw new Error('No workflow types selected');

      // 1. Upload supporting documents if any
      if (supportingDocuments.length > 0) {
        await projectService.addFilesToProject(wizard.projectId, supportingDocuments);
      }

      // 2. Update project metadata if domain or target audience is set
      if (domain || targetAudience) {
        await updateProjectEndpointApiProjectProjectIdPatch({
          path: { project_id: wizard.projectId },
          body: {
            domain: domain || undefined,
            target_audience: targetAudience || undefined,
          },
        });
      }

      // 3. Start workflows
      // If supporting documents were uploaded, we need to re-run DOCUMENT_PROCESSING
      // to process them (it was already run in step 1 for main doc only)
      const workflowsToStart =
        supportingDocuments.length > 0
          ? [WorkflowRunType.DocumentProcessing, ...selectedWorkflowTypes]
          : selectedWorkflowTypes;

      const apiKey = wizard.openaiApiKey || storedApiKey;
      return startMultipleWorkflowsApiWorkflowsStartMultiplePost({
        body: {
          project_id: wizard.projectId,
          workflow_types: workflowsToStart,
          openai_api_key: apiKey || undefined,
        },
      });
    },
    onSuccess: () => {
      toast.success('Analysis started! Redirecting to your project...');
      // Use fromWizard param to prevent redirect loop (race condition with workflow creation)
      router.push(`/projects/${wizard.projectId}?fromWizard=true`);
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : 'Failed to start analysis');
    },
  });

  const handleRemoveSupportingFile = (index?: number) => {
    if (typeof index === 'number') {
      setSupportingDocuments((files) => files.filter((_, i) => i !== index));
    }
  };

  const handleStartAnalysis = () => {
    if (startAnalysisMutation.isPending || startAnalysisMutation.isSuccess) return;
    startAnalysisMutation.mutate();
  };

  const canContinue = selectedWorkflowTypes.length > 0;
  const isSubmitting = startAnalysisMutation.isPending || startAnalysisMutation.isSuccess;

  // Show loading screen when submitting
  if (isSubmitting) {
    return (
      <Card className="max-w-xl mx-auto">
        <CardContent className="py-12">
          <div className="flex flex-col items-center justify-center space-y-4">
            <Loader2 className="w-12 h-12 animate-spin text-primary" />
            <div className="text-center space-y-2">
              <h2 className="text-xl font-semibold">Starting Analysis</h2>
              <p className="text-sm text-muted-foreground">
                {supportingDocuments.length > 0
                  ? 'Uploading and processing supporting documents...'
                  : 'Starting workflows...'}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-8">
      <div className="space-y-2">
        <h1 className="text-2xl font-bold">What do you want to analyze today?</h1>
      </div>

      {/* Workflow Type Selection */}
      <WorkflowTypeSelector
        workflowTypes={workflowTypes}
        selectedTypes={selectedWorkflowTypes}
        onSelectionChange={setSelectedWorkflowTypes}
        headerDescription="Select which types of analyses to perform"
      />

      {/* Supporting Documents - Conditional */}
      {showSupportingDocs && (
        <UploadSection
          title="Supporting Documents"
          description="Reference documents cited in your main document's reference section (e.g., PDFs of cited papers or news websites). These enable validation of claims against their cited sources."
          required={true}
          onFilesChange={setSupportingDocuments}
          multiple={true}
          files={supportingDocuments}
          fileType="supporting"
          onRemoveFile={handleRemoveSupportingFile}
        />
      )}

      {/* Domain and Target Audience */}
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label htmlFor="domain">
            Domain <span className="text-muted-foreground text-xs font-normal">(Optional)</span>
          </Label>
          <Input
            id="domain"
            placeholder="e.g., Policy research, Healthcare..."
            value={domain}
            onChange={(e) => setDomain(e.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="target-audience">
            Target Audience <span className="text-muted-foreground text-xs font-normal">(Optional)</span>
          </Label>
          <Input
            id="target-audience"
            placeholder="e.g., Policy makers, General public..."
            value={targetAudience}
            onChange={(e) => setTargetAudience(e.target.value)}
          />
        </div>
      </div>

      {/* Continue Button */}
      <Button onClick={handleStartAnalysis} disabled={!canContinue} size="lg" className="w-full">
        Start Analysis
      </Button>
    </div>
  );
}
