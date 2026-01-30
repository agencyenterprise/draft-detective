'use client';

import { Callout } from '@/components/ui/callout';
import { AlertTriangle } from 'lucide-react';

export type SectionWarningType = 'references' | 'preface' | 'authors';

interface SectionWarningConfig {
  errorTitle: string;
  errorDescription: string;
  notFoundTitle: string;
  notFoundDescription: string;
  sectionNames: string[];
  impact: string;
  /** Optional: for references, there's a special "section detected but empty" case */
  emptyTitle?: string;
  emptyDescription?: string;
  emptyReasons?: string[];
}

const WARNING_CONFIGS: Record<SectionWarningType, SectionWarningConfig> = {
  references: {
    errorTitle: 'Reference Extraction Incomplete',
    errorDescription:
      'Reference extraction encountered errors during processing and may not have completed successfully.',
    notFoundTitle: 'No Reference Section Found',
    notFoundDescription:
      'We could not find a Reference or Bibliography section heading in your document. Reference extraction requires a clearly titled section heading (e.g., "References", "Bibliography", "Works Cited").',
    sectionNames: ['Reference', 'Bibliography'],
    impact: 'Without extracted references, claim-reference validation cannot verify if claims are properly supported.',
    emptyTitle: 'Reference Section Empty or Unreadable',
    emptyDescription:
      'A reference section was detected in your document, but no references could be extracted from it.',
    emptyReasons: [
      'The reference section is empty',
      'The references are in an unsupported format (e.g., images, tables)',
      'The document conversion affected the reference text formatting',
    ],
  },
  preface: {
    errorTitle: 'Preface Analysis Incomplete',
    errorDescription: 'Preface analysis encountered errors during processing and may not have completed successfully.',
    notFoundTitle: 'No Preface Section Found',
    notFoundDescription:
      'We could not find an "About This Report", "Preface", or similar introductory section. Preface validation requires a clearly titled section heading.',
    sectionNames: ['About This Report', 'Preface', 'Introduction'],
    impact:
      'Without a preface section, the About This validation cannot verify context, objectives, audience, TASP boilerplate, or funding statements.',
  },
  authors: {
    errorTitle: 'Author Analysis Incomplete',
    errorDescription: 'Author analysis encountered errors during processing and may not have completed successfully.',
    notFoundTitle: 'No "About the Authors" Section Found',
    notFoundDescription:
      'We could not find an "About the Authors" or "Author Biographies" section. Author validation requires a section containing author biography paragraphs.',
    sectionNames: ['About the Authors', 'Author Biographies'],
    impact:
      'Without author biographies, the About Authors validation cannot verify sentence count, position, affiliation, or degree requirements.',
  },
};

interface SectionNotFoundCalloutProps {
  type: SectionWarningType;
  hasErrors?: boolean;
  /** For references: whether sections were detected but empty */
  sectionsDetectedButEmpty?: boolean;
  className?: string;
}

/**
 * Generic callout for when a required document section is not found.
 * Supports references, preface, and authors section warnings.
 */
export function SectionNotFoundCallout({
  type,
  hasErrors = false,
  sectionsDetectedButEmpty = false,
  className,
}: SectionNotFoundCalloutProps) {
  const config = WARNING_CONFIGS[type];

  if (hasErrors) {
    return (
      <Callout title={config.errorTitle} variant="warning" icon={AlertTriangle} className={className}>
        <div className="space-y-2">
          <p>{config.errorDescription}</p>
          <p>
            Check the <strong>Analyses tab</strong> for error details. You may need to re-run the analysis.
          </p>
          <p>{config.impact}</p>
        </div>
      </Callout>
    );
  }

  // Special case: references section detected but empty
  if (sectionsDetectedButEmpty && config.emptyTitle && config.emptyReasons) {
    return (
      <Callout title={config.emptyTitle} variant="warning" icon={AlertTriangle} className={className}>
        <div className="space-y-2">
          <p>{config.emptyDescription}</p>
          <p>This can happen when:</p>
          <ul className="list-disc list-inside space-y-1 ml-2">
            {config.emptyReasons.map((reason, i) => (
              <li key={i}>{reason}</li>
            ))}
          </ul>
          <p>{config.impact}</p>
        </div>
      </Callout>
    );
  }

  return (
    <Callout title={config.notFoundTitle} variant="warning" icon={AlertTriangle} className={className}>
      <div className="space-y-2">
        <p>{config.notFoundDescription}</p>
        <p>{config.impact}</p>
        <p className="font-medium">
          Please ensure your document contains an appropriately titled section and try again.
        </p>
      </div>
    </Callout>
  );
}
