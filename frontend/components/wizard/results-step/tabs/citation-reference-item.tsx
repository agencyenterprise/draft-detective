import { LabeledValue } from '@/components/labeled-value';
import { FileDownloadLink } from '@/components/ui/file-download-link';
import { ComposedReference } from '@/lib/composed-references';
import { FileDocument, Reference } from '@/lib/generated-api';
import {
  ConfidenceBadge,
  PublicationQualityBadge,
  RecommendedActionBadge,
  ReferenceTypeBadge,
} from '../components/citation-suggestion-badges';

interface CitationReferenceItemProps {
  reference: Reference;
  references: ComposedReference[];
  supportingFiles: FileDocument[];
}

export function CitationReferenceItem({ reference, references, supportingFiles }: CitationReferenceItemProps) {
  const associatedExistingReference =
    reference.index_of_associated_existing_reference !== -1
      ? references[reference.index_of_associated_existing_reference - 1]
      : null;

  const associatedSupportingFile = associatedExistingReference
    ? supportingFiles.find((file) => file.file_id === associatedExistingReference.file_id)
    : null;

  return (
    <div className="space-y-1">
      <h5 className="font-medium">{reference.title}</h5>
      <div className="flex items-center gap-2 flex-wrap">
        <ReferenceTypeBadge type={reference.type} />
        {reference.is_already_cited_elsewhere && (
          <span className="px-2 py-1 rounded text-xs bg-cyan-100 text-cyan-800">Already cited</span>
        )}
        <RecommendedActionBadge action={reference.recommended_action} />
        <ConfidenceBadge confidence={reference.confidence_in_recommendation} />
        <PublicationQualityBadge quality={reference.publication_quality} />
      </div>

      {reference.link && (
        <p>
          <span className="font-medium">Link:</span>{' '}
          <a href={reference.link} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
            {reference.link}
          </a>
        </p>
      )}

      {associatedExistingReference && associatedSupportingFile && associatedSupportingFile.file_id && (
        <LabeledValue label="Existing Bibliography Reference">
          <FileDownloadLink fileId={associatedSupportingFile.file_id} className="text-blue-600 underline">
            {associatedSupportingFile.file_name}
          </FileDownloadLink>{' '}
          - <span className="text-muted-foreground italic">{associatedExistingReference.text}</span>
        </LabeledValue>
      )}

      <LabeledValue label="Bibliography Entry">{reference.bibliography_info}</LabeledValue>

      <LabeledValue label="Related Excerpt (from our document)">&quot;{reference.related_excerpt}&quot;</LabeledValue>

      <LabeledValue label="Related Excerpt (from reference)">{reference.related_excerpt_from_reference}</LabeledValue>

      <LabeledValue label="Rationale">{reference.rationale}</LabeledValue>

      <LabeledValue label="Recommended Action">{reference.explanation_for_recommended_action}</LabeledValue>
    </div>
  );
}
