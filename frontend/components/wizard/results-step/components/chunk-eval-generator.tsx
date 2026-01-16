import { downloadFile, generateEvalFilename } from '@/lib/file-download';
import { generateChunkEvalPackageApiGenerateChunkEvalPackagePost } from '@/lib/generated-api';
import { FileText } from 'lucide-react';
import * as React from 'react';
import { useSupportedAgents } from '../hooks/use-supported-agents';
import { ExpandableControl } from './expandable-control';

interface ChunkEvalGeneratorProps {
  chunkIndex: number;
  projectId: string;
}

interface OptimizationInfoProps {
  selectedAgents: Set<string>;
}

function OptimizationInfo({ selectedAgents }: OptimizationInfoProps) {
  const agents = Array.from(selectedAgents);
  const needsSupporting = agents.some((agent) => ['references', 'substantiation'].includes(agent));

  const optimization = {
    mainDocument: true,
    supportingDocuments: needsSupporting,
    yamlFiles: agents.length,
  };

  return (
    <div className="text-xs text-blue-600 bg-blue-100 p-2 rounded">
      <div className="font-medium">Package will include:</div>
      <div>• Main document: ✅</div>
      <div>• Supporting docs: {optimization.supportingDocuments ? '✅' : '❌ (not needed)'}</div>
      <div>• YAML files: {optimization.yamlFiles}</div>
    </div>
  );
}

export function ChunkEvalGenerator({ chunkIndex, projectId }: ChunkEvalGeneratorProps) {
  const [isGenerating, setIsGenerating] = React.useState(false);
  const { supportedAgents, supportedAgentsError } = useSupportedAgents();

  const handleGenerateEval = async (selectedAgents: Set<string>) => {
    setIsGenerating(true);

    try {
      const testName = `chunk_${chunkIndex}_eval_${Date.now()}`;
      const description = `Generated from chunk ${chunkIndex} analysis on ${new Date().toLocaleDateString()}`;

      const { data } = (await generateChunkEvalPackageApiGenerateChunkEvalPackagePost({
        responseStyle: 'fields',
        body: {
          project_id: projectId,
          test_name: testName,
          description: description,
          chunk_index: chunkIndex,
          selected_agents: Array.from(selectedAgents),
        },
      })) as { response: Response; data: Blob };

      downloadFile({
        filename: generateEvalFilename(testName, chunkIndex),
        blob: data,
      });
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <ExpandableControl
      title="Generate Eval Test"
      buttonText={
        <div className="flex items-center">
          <FileText className="w-3 h-3 mr-1" />
          Create Eval
        </div>
      }
      expandedButtonText="Cancel"
      isProcessing={isGenerating}
      processingText="Generating..."
      chunkIndex={chunkIndex}
      supportedAgents={supportedAgents}
      supportedAgentsError={supportedAgentsError}
      agentSelectorTitle="Select Agents for Eval:"
      backgroundClassName="bg-blue-50"
      footerText="Optimized package for chunk {chunkIndex}"
      actionButtonText="Download Eval Package"
      onAction={handleGenerateEval}
    >
      {(selectedAgents) => (selectedAgents.size > 0 ? <OptimizationInfo selectedAgents={selectedAgents} /> : null)}
    </ExpandableControl>
  );
}
