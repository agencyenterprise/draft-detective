import { BibliographyItemValidation, ReferenceFetchResult } from '@/lib/generated-api';

export type ReferenceReviewStatus = 'unmatched' | 'fetching' | 'matched';

export interface MatchedFile {
  id: string;
  name: string;
  url: string;
  size: string;
}

export interface ReferenceReviewItem {
  index: number;
  text: string;
  status: ReferenceReviewStatus;
  matchedFile: null | MatchedFile;
  fetchResult?: ReferenceFetchResult | null;
  validation?: BibliographyItemValidation | null;
}
