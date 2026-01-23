'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { Loader2, AlertCircle, FileText } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Callout } from '@/components/ui/callout';
import { useWizard } from './wizard-context';
import { useProjectDetails } from '@/lib/hooks/use-project-details';
import { useReferenceReviewReferences } from '@/components/wizard/results-step/tabs/reference-review/queries';
import { ReferenceReviewList } from '@/components/wizard/results-step/tabs/reference-review/reference-review-list';
import { useFetchAllFromWebMutation } from '@/components/wizard/results-step/tabs/reference-review/mutations';
import { WorkflowConfigDialog, WorkflowConfigFormValues } from '@/components/workflows/workflow-config-dialog';
import {
  ProjectDetailed,
  WorkflowRunType,
  ApprovalCheckpoint,
  approveCheckpointApiProjectProjectIdApprovePost,
} from '@/lib/generated-api';
import { getWorkflowRunByType, isWorkflowProcessing } from '@/lib/workflow-state';

type StepStatus = 'loading-project' | 'extracting' | 'ready' | 'no-references';

function getStepStatus(project: ProjectDetailed | undefined, isLoading: boolean): StepStatus {
  if (isLoading || !project) return 'loading-project';

  const workflowRuns = project.workflow_runs ?? [];
  const referenceExtraction = getWorkflowRunByType(workflowRuns, WorkflowRunType.ReferenceExtraction);

  if (!referenceExtraction || isWorkflowProcessing(referenceExtraction)) {
    return 'extracting';
  }

  const extractedReferences = referenceExtraction.state?.extracted_references ?? [];
  if (extractedReferences.length === 0) {
    return 'no-references';
  }

  return 'ready';
}

export function StepReferences() {
  const wizard = useWizard();
  const { project, isLoading } = useProjectDetails(wizard.projectId);

  const stepStatus = getStepStatus(project, isLoading);

  if (stepStatus === 'loading-project') {
    return <LoadingCard title="Loading Project" description="Fetching project data..." />;
  }

  if (stepStatus === 'extracting') {
    return (
      <LoadingCard
        title="Extracting References"
        description="AI is analyzing your document to find references. This may take a moment..."
      />
    );
  }

  if (stepStatus === 'no-references') {
    return <NoReferencesView projectId={wizard.projectId!} />;
  }

  return <ReferencesReady project={project!} />;
}

function LoadingCard({ title, description }: { title: string; description: string }) {
  return (
    <Card className="max-w-xl mx-auto">
      <CardContent className="py-12">
        <div className="flex flex-col items-center justify-center space-y-4">
          <Loader2 className="w-12 h-12 animate-spin text-primary" />
          <div className="text-center space-y-2">
            <h2 className="text-xl font-semibold">{title}</h2>
            <p className="text-sm text-muted-foreground">{description}</p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function NoReferencesView({ projectId }: { projectId: string }) {
  const router = useRouter();
  const queryClient = useQueryClient();

  const approveMutation = useMutation({
    mutationFn: () =>
      approveCheckpointApiProjectProjectIdApprovePost({
        path: { project_id: projectId },
        body: { checkpoint: ApprovalCheckpoint.ReferenceReview },
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['project', projectId] });
      toast.success('Continuing to project...');
      router.push(`/projects/${projectId}?fromWizard=true`);
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : 'Failed to continue');
    },
  });

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <h1 className="text-2xl font-bold">Review References</h1>
      </div>

      <Callout variant="warning" icon={AlertCircle} title="No References Found">
        No references were detected in your document. This could mean:
        <ul className="list-disc ml-6 mt-2 space-y-1">
          <li>The document doesn&apos;t contain a references/bibliography section</li>
          <li>The references are in an unexpected format</li>
        </ul>
      </Callout>

      <Button
        onClick={() => approveMutation.mutate()}
        disabled={approveMutation.isPending}
        size="lg"
        className="w-full"
      >
        {approveMutation.isPending ? (
          <>
            <Loader2 className="w-4 h-4 animate-spin mr-2" />
            Processing...
          </>
        ) : (
          'Continue to Project'
        )}
      </Button>
    </div>
  );
}

function ReferencesReady({ project }: { project: ProjectDetailed }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [isConfigDialogOpen, setIsConfigDialogOpen] = useState(false);

  const projectId = project.project.id;
  const workflowDetails = project.workflow_runs ?? [];
  const references = useReferenceReviewReferences(project);
  const fetchAllFromWebMutation = useFetchAllFromWebMutation(projectId);
  const referenceDownloader = getWorkflowRunByType(workflowDetails, WorkflowRunType.ReferenceDownloader);

  const approveMutation = useMutation({
    mutationFn: () =>
      approveCheckpointApiProjectProjectIdApprovePost({
        path: { project_id: projectId },
        body: { checkpoint: ApprovalCheckpoint.ReferenceReview },
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['project', projectId] });
      toast.success('References confirmed! Analyses will now proceed.');
      router.push(`/projects/${projectId}?fromWizard=true`);
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : 'Failed to confirm references');
    },
  });

  const handleOpenDialog = () => setIsConfigDialogOpen(true);

  const handleConfirm = (values: WorkflowConfigFormValues) => {
    const unmatchedReferences = references
      .filter((ref) => ref.status === 'unmatched')
      .map((ref) => ({ index: ref.index, text: ref.text }));
    fetchAllFromWebMutation.mutate(
      { references: unmatchedReferences, openaiApiKey: values.openaiApiKey },
      { onSuccess: () => setIsConfigDialogOpen(false) },
    );
  };

  return (
    <div className="space-y-8">
      <div className="space-y-2">
        <h1 className="text-2xl font-bold">Review References</h1>
        <p className="text-muted-foreground">
          We found {references.length} references in your document. Match them with supporting documents for validation.
        </p>
      </div>

      <WorkflowConfigDialog
        isOpen={isConfigDialogOpen}
        type={WorkflowRunType.ReferenceDownloader}
        onConfirm={handleConfirm}
        onCancel={() => setIsConfigDialogOpen(false)}
      />

      <ReferenceReviewList
        references={references}
        projectId={projectId}
        readOnly={false}
        onFetchAll={handleOpenDialog}
        isFetchingAllFromWeb={fetchAllFromWebMutation.isPending || isWorkflowProcessing(referenceDownloader)}
      />

      <Button
        onClick={() => approveMutation.mutate()}
        disabled={approveMutation.isPending}
        size="lg"
        className="w-full"
      >
        {approveMutation.isPending ? (
          <>
            <Loader2 className="w-4 h-4 animate-spin mr-2" />
            Confirming...
          </>
        ) : (
          <>
            <FileText className="w-4 h-4 mr-2" />
            Confirm References & Continue
          </>
        )}
      </Button>
    </div>
  );
}
