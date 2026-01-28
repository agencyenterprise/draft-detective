import { BibliographyItemValidation, ReferenceFetchResult } from '@/lib/generated-api';

export type ReferenceReviewStatus = 'unmatched' | 'fetching' | 'matched';

export interface MatchedFile {
  id: string;
  name: string;
  size: string;
}

export interface ReferenceReviewItem {
  id: string;
  index: number;
  text: string;
  status: ReferenceReviewStatus;
  matchedFile: null | MatchedFile;
  fetchResult?: ReferenceFetchResult | null;
  validation?: BibliographyItemValidation | null;
}
