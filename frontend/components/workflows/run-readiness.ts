import { WorkflowRunType, WorkflowTypeDescription } from '@/lib/generated-api';
import { startBlocker, StartBlocker } from './utils';

/** The Run assessments dialog's message for each reason it cannot submit. */
export const RUN_BLOCKER_MESSAGES: Record<StartBlocker, string> = {
  'metadata-pending': 'Loading the available assessments…',
  'metadata-failed': 'The available assessments could not be loaded. Close this dialog and try again.',
  'none-selected': 'Select at least one assessment.',
  'consent-missing': 'Consent to web search to run the selected assessments.',
};

export interface RunReadiness {
  /** Why the selection cannot run, or null when it can. */
  blocker: StartBlocker | null;
  /** Every message the footer shows: the blocker's, then any field's. Empty while the form is pristine. */
  messages: string[];
  /** Whether the run button may be pressed. */
  ready: boolean;
}

/**
 * Whether the dialog's current values can be run, decided from the values
 * themselves rather than from a validation pass. A pristine form has not been
 * validated, and TanStack reports it as submittable, so a dialog opened with
 * nothing selected, or with a web-searching assessment preselected and no
 * consent, would otherwise offer an enabled Run button until the first change.
 *
 * The button is held either way, but a pristine form is not told off: nobody
 * has done anything yet, so the messages wait for the first touch.
 */
export function runReadiness({
  selectedTypes,
  webSearchConsent,
  workflowTypes,
  metadataPending,
  metadataFailed,
  fieldErrors = [],
  pristine = false,
}: {
  selectedTypes: WorkflowRunType[];
  webSearchConsent: boolean;
  workflowTypes: WorkflowTypeDescription[];
  metadataPending: boolean;
  metadataFailed: boolean;
  /** Messages from field validators, such as the publication date's. */
  fieldErrors?: string[];
  /** The form has not been touched since it opened. */
  pristine?: boolean;
}): RunReadiness {
  const blocker = startBlocker({ selectedTypes, workflowTypes, metadataPending, metadataFailed, webSearchConsent });
  const problems = [...(blocker ? [RUN_BLOCKER_MESSAGES[blocker]] : []), ...fieldErrors];
  return { blocker, messages: pristine ? [] : problems, ready: problems.length === 0 };
}
