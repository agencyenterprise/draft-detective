'use client';

import { UploadSection } from '@/components/analysis-form/upload-section';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { ReferenceExtractionState, startAnalysisApiStartAnalysisPost, WorkflowRunType } from '@/lib/generated-api';
import { useProjectDetails } from '@/lib/hooks/use-project-details';
import { useWorkflowStatusNotifications } from '@/hooks/use-workflow-status-notifications';
import { useMutation } from '@tanstack/react-query';
import { Loader2 } from 'lucide-react';
import { useCallback, useMemo, useState } from 'react';
import { toast } from 'sonner';

// type ExtractionResults = Pick<ReferenceExtractionState, 'detected_sections' | 'references'>;
type ExtractionResults = ReferenceExtractionState;

export function ReferenceExtractorTool() {
  const [mainDocument, setMainDocument] = useState<File | null>(null);
  const [supportingDocuments, setSupportingDocuments] = useState<File[]>([]);
  const [projectId, setProjectId] = useState<string | null>(null);
  const [results, setResults] = useState<ExtractionResults | null>(null);

  const { project, workflowDetails, isProcessing: isWorkflowProcessing } = useProjectDetails(projectId!);

  const docProcessingRun = useMemo(
    () => workflowDetails.find((w) => w.run.type === WorkflowRunType.DocumentProcessing),
    [workflowDetails],
  );
  const refExtractionRun = useMemo(
    () => workflowDetails.find((w) => w.run.type === WorkflowRunType.ReferenceExtraction),
    [workflowDetails],
  );

  const handleWorkflowCompleted = useCallback(
    (type: WorkflowRunType) => {
      if (type === WorkflowRunType.ReferenceExtraction && refExtractionRun) {
        const state = refExtractionRun.state as ReferenceExtractionState;
        // setResults({
        //   detected_sections: state.detected_sections || [],
        //   references: state.references || [],
        // });
        // toast.success(
        //   `Extracted ${state.references?.length || 0} references from ${state.detected_sections?.length || 0} section(s)!`,
        // );
      }
    },
    [refExtractionRun],
  );

  useWorkflowStatusNotifications({
    workflows: [
      {
        type: WorkflowRunType.DocumentProcessing,
        status: docProcessingRun?.run.status,
        messages: {
          running: 'Converting document to markdown...',
        },
      },
      {
        type: WorkflowRunType.ReferenceExtraction,
        status: refExtractionRun?.run.status,
        messages: {
          pending: 'Waiting for extraction to start...',
          running: 'Extracting references from sections...',
        },
      },
    ],
    onCompleted: handleWorkflowCompleted,
  });

  const startWorkflowMutation = useMutation({
    mutationFn: async () => {
      return await startAnalysisApiStartAnalysisPost({
        body: {
          main_document: mainDocument!,
          supporting_documents: supportingDocuments.length > 0 ? supportingDocuments : undefined,
          workflow_types: `${WorkflowRunType.DocumentProcessing},${WorkflowRunType.ReferenceExtraction}`,
          use_toulmin: false,
        },
      });
    },
    onSuccess: (response) => {
      setProjectId(response.project_id!);
      setResults(null);
      toast.success('Documents uploaded, processing...');
    },
    onError: (error) => {
      console.error('Error extracting references:', error);
      toast.error(error instanceof Error ? error.message : 'Failed to extract references');
    },
  });

  const handleExtract = () => {
    if (!mainDocument) return;
    toast.info('Uploading documents...');
    startWorkflowMutation.mutate();
  };

  const handleReset = () => {
    setResults(null);
    setProjectId(null);
  };

  const isProcessing = startWorkflowMutation.isPending || (projectId ? isWorkflowProcessing : false);

  return (
    <div className="space-y-6">
      {!isProcessing && !results && (
        <Card className="p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Upload Documents</h2>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
            <UploadSection
              title="Main Document"
              description="Academic document with bibliography"
              required={true}
              onFilesChange={(files) => setMainDocument(files[0] || null)}
              multiple={false}
              files={mainDocument ? [mainDocument] : []}
              fileType="main"
              onRemoveFile={() => setMainDocument(null)}
            />

            <UploadSection
              title="Supporting Documents"
              description="Optional - for matching references with sources"
              required={false}
              onFilesChange={setSupportingDocuments}
              multiple={true}
              files={supportingDocuments}
              fileType="supporting"
              onRemoveFile={(index) => setSupportingDocuments((prev) => prev.filter((_, i) => i !== index))}
            />
          </div>

          <Button onClick={handleExtract} disabled={!mainDocument} className="w-full">
            Extract References
          </Button>
        </Card>
      )}

      {isProcessing && (
        <Card className="p-8">
          <div className="text-center space-y-4">
            <Loader2 className="mx-auto h-12 w-12 animate-spin text-primary" />
            <div>
              <h3 className="text-lg font-semibold text-gray-900">Processing Document</h3>
              <p className="text-sm text-muted-foreground mt-2">
                Detecting reference sections and extracting bibliography entries...
              </p>
              <p className="text-xs text-muted-foreground mt-1">This may take 2-4 minutes for large documents</p>
            </div>
          </div>
        </Card>
      )}

      {results && (
        <Card className="p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900">
              Extracted References ({results.references?.length || 0})
            </h2>
            <Button variant="outline" size="sm" onClick={handleReset}>
              Extract Another
            </Button>
          </div>

          <div className="space-y-4">
            {/* {results.detected_sections && results.detected_sections.length > 0 && (
              <div className="p-4 bg-blue-50 border border-blue-200 rounded-md">
                <h3 className="text-sm font-medium text-blue-900 mb-2">Detected Sections</h3>
                <ul className="text-xs text-blue-700 space-y-1">
                  {results.detected_sections.map((section, idx) => (
                    <li key={idx}>
                      {section.section_type} (chunks {section.start_chunk_index}-{section.end_chunk_index || 'end'}) -
                      Confidence: {(section.confidence * 100).toFixed(0)}%
                    </li>
                  ))}
                </ul>
              </div>
            )} */}

            {results.references && results.references.length > 0 ? (
              <div className="space-y-2">
                {results.references.map((ref, idx) => (
                  <div key={idx} className="p-3 border border-gray-200 rounded-md hover:border-gray-300 transition">
                    <div className="flex items-start gap-3">
                      <span className="text-xs font-medium text-gray-500 mt-0.5">#{idx + 1}</span>
                      <div className="flex-1">
                        <p className="text-sm text-gray-900">{ref.text}</p>
                        {ref.has_associated_supporting_document && (
                          <p className="text-xs text-green-600 mt-1">
                            ✓ Matched with: {ref.name_of_associated_supporting_document}
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground text-center py-8">No references found in this document</p>
            )}
          </div>
        </Card>
      )}
    </div>
  );
}
