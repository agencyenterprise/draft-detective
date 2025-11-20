import { LabeledValue } from '@/components/labeled-value';
import { apiUrl } from '@/lib/api';
import { BibliographyItem, FileDocumentOutput, Reference } from '@/lib/generated-api';
import Link from 'next/link';
import {
  ConfidenceBadge,
  PublicationQualityBadge,
  RecommendedActionBadge,
  ReferenceTypeBadge,
} from '../components/citation-suggestion-badges';

interface CitationReferenceItemProps {
  reference: Reference;
  references: BibliographyItem[];
  supportingFiles: FileDocumentOutput[];
}

export function CitationReferenceItem({ reference, references, supportingFiles }: CitationReferenceItemProps) {
  const associatedExistingReference =
    reference.indexOfAssociatedExistingReference !== -1
      ? references[reference.indexOfAssociatedExistingReference - 1]
      : null;

  const associatedSupportingFile = associatedExistingReference
    ? supportingFiles.find((file) => file.fileName === associatedExistingReference.nameOfAssociatedSupportingDocument)
    : null;

  return (
    <div className="space-y-1">
      <h5 className="font-medium">{reference.title}</h5>
      <div className="flex items-center gap-2 flex-wrap">
        <ReferenceTypeBadge type={reference.type} />
        {reference.isAlreadyCitedElsewhere && (
          <span className="px-2 py-1 rounded text-xs bg-cyan-100 text-cyan-800">Already cited</span>
        )}
        <RecommendedActionBadge action={reference.recommendedAction} />
        <ConfidenceBadge confidence={reference.confidenceInRecommendation} />
        <PublicationQualityBadge quality={reference.publicationQuality} />
      </div>

      {reference.link && (
        <p>
          <span className="font-medium">Link:</span>{' '}
          <a href={reference.link} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
            {reference.link}
          </a>
        </p>
      )}

      {associatedExistingReference && associatedSupportingFile && (
        <LabeledValue label="Existing Bibliography Reference">
          <Link
            href={`${apiUrl}/api/files/download/${associatedSupportingFile.filePath.split('/').pop()}/${associatedSupportingFile.fileName}`}
            target="_blank"
            className="text-blue-600 underline"
          >
            {associatedSupportingFile.fileName}
          </Link>{' '}
          - <span className="text-muted-foreground italic">{associatedExistingReference.text}</span>
        </LabeledValue>
      )}

      <LabeledValue label="Bibliography Entry">{reference.bibliographyInfo}</LabeledValue>

      <LabeledValue label="Related Excerpt (from our document)">&quot;{reference.relatedExcerpt}&quot;</LabeledValue>

      <LabeledValue label="Related Excerpt (from reference)">{reference.relatedExcerptFromReference}</LabeledValue>

      <LabeledValue label="Rationale">{reference.rationale}</LabeledValue>

      <LabeledValue label="Recommended Action">{reference.explanationForRecommendedAction}</LabeledValue>
    </div>
  );
}
