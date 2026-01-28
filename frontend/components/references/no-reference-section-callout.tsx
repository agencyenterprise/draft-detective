'use client';

import { Callout } from '@/components/ui/callout';
import { AlertTriangle } from 'lucide-react';

interface NoReferencesCalloutProps {
  /** Whether reference sections were detected in the document */
  sectionsDetected: boolean;
  /** Whether the workflow had errors during processing */
  hasErrors?: boolean;
  className?: string;
}

/**
 * Shared callout component displayed when reference extraction completes
 * but no references were found. Shows different messages based on why:
 *
 * - Has errors: Processing encountered issues
 * - No sections detected: Document lacks reference section headings (e.g., "# References")
 * - Sections detected but empty: Section heading exists but no references could be extracted
 */
export function NoReferencesCallout({ sectionsDetected, hasErrors = false, className }: NoReferencesCalloutProps) {
  if (hasErrors) {
    return (
      <Callout title="Reference Extraction Incomplete" variant="warning" icon={AlertTriangle} className={className}>
        <div className="space-y-2">
          <p>
            Reference extraction <strong>encountered errors</strong> during processing and may not have completed
            successfully.
          </p>
          <p>
            Check the <strong>Analyses tab</strong> for error details. You may need to re-run the analysis or check your
            document format.
          </p>
          <p>
            Without extracted references, <strong>claim-reference validation</strong> cannot verify if claims are
            properly supported by cited sources.
          </p>
        </div>
      </Callout>
    );
  }

  if (sectionsDetected) {
    return (
      <Callout
        title="Reference Section Empty or Unreadable"
        variant="warning"
        icon={AlertTriangle}
        className={className}
      >
        <div className="space-y-2">
          <p>
            A reference section was detected in your document, but <strong>no references could be extracted</strong>{' '}
            from it.
          </p>
          <p>This can happen when:</p>
          <ul className="list-disc list-inside space-y-1 ml-2">
            <li>The reference section is empty</li>
            <li>The references are in an unsupported format (e.g., images, tables)</li>
            <li>The document conversion affected the reference text formatting</li>
          </ul>
          <p>
            Without extracted references, <strong>claim-reference validation</strong> cannot verify if claims are
            properly supported by cited sources.
          </p>
        </div>
      </Callout>
    );
  }

  return (
    <Callout title="No Reference Section Found" variant="warning" icon={AlertTriangle} className={className}>
      <div className="space-y-2">
        <p>
          We could not find a <strong>Reference</strong> or <strong>Bibliography</strong> section heading in your
          document.
        </p>
        <p>
          Reference extraction requires a clearly titled section heading (e.g., &quot;References&quot;,
          &quot;Bibliography&quot;, &quot;Works Cited&quot;) to identify where the bibliographic entries are located.
        </p>
        <p>
          Without extracted references, <strong>claim-reference validation</strong> cannot verify if claims are properly
          supported by cited sources.
        </p>
        <p className="font-medium">
          Please ensure your document contains a heading that marks the start of your reference list and try again.
        </p>
      </div>
    </Callout>
  );
}
