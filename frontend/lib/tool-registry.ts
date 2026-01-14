import { FileSearchIcon, FileDownIcon } from 'lucide-react';
import { WorkflowRunType } from './generated-api';

export interface ToolDefinition {
  name: string;
  route: string;
  icon: React.ComponentType<{ className?: string }>;
  workflowTypes: Set<WorkflowRunType>;
  description: string;
}

/**
 * Internal workflows that should not be displayed to users in project lists.
 * These workflows run as dependencies or internal processes.
 */
export const INTERNAL_WORKFLOW_TYPES = new Set<WorkflowRunType>([
  WorkflowRunType.DocumentProcessing,
  WorkflowRunType.ReferenceExtraction,
]);

/**
 * Registry of all registered tools.
 * Each tool is identified by its unique combination of workflow types.
 */
export const REGISTERED_TOOLS: ToolDefinition[] = [
  {
    name: 'Reference Extractor',
    route: '/tools/reference-extractor',
    icon: FileSearchIcon,
    workflowTypes: new Set([WorkflowRunType.DocumentProcessing, WorkflowRunType.ReferenceExtraction]),
    description: 'Extract bibliographic references from academic documents',
  },
  {
    name: 'Reference Downloader',
    route: '/tools/reference-downloader',
    icon: FileDownIcon,
    workflowTypes: new Set([WorkflowRunType.ReferenceDownloader]),
    description: 'Download PDF sources for bibliographic references',
  },
];

/**
 * Detect if a project matches a tool signature based on its workflow types.
 * Uses exact matching - the workflow types must match exactly (no partial matches).
 *
 * @param workflowTypes - Array of workflow types from a project
 * @returns The matching tool definition, or null if no match
 */
export function detectToolFromWorkflows(workflowTypes: WorkflowRunType[]): ToolDefinition | null {
  const workflowSet = new Set(workflowTypes);

  for (const tool of REGISTERED_TOOLS) {
    // Check if sets are equal (same size and all elements match)
    if (
      workflowSet.size === tool.workflowTypes.size &&
      [...workflowSet].every((type) => tool.workflowTypes.has(type))
    ) {
      return tool;
    }
  }

  return null;
}

/**
 * Get tool metadata by tool name.
 *
 * @param toolName - The name of the tool
 * @returns Tool metadata (icon, description) or undefined if not found
 */
export function getToolMetadata(toolName: string): Pick<ToolDefinition, 'icon' | 'description'> | undefined {
  const tool = REGISTERED_TOOLS.find((t) => t.name === toolName);
  if (!tool) return undefined;

  return {
    icon: tool.icon,
    description: tool.description,
  };
}
