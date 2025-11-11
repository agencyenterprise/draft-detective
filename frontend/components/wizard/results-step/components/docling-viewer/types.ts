import type { ChunkToItems, DoclingDocument, DoclingPage, Region } from '@/types/docling';

export interface DoclingViewerProps {
  docJson: DoclingDocument;
  chunkToItems: ChunkToItems;
  pageImagesBaseUrl: string;
  selectedChunkIndex: number | null;
  onChunkSelect: (chunkIndex: number | null) => void;
}

export interface DoclingPageProps {
  page: DoclingPage;
  pageNum: number;
  regions: RegionWithChunks[];
  selectedRegions: Region[];
  selectedChunkIndex: number | null;
  pageImagesBaseUrl: string;
  onChunkSelect: (chunkIndex: number | null) => void;
}

export interface RegionOverlayProps {
  region: RegionWithChunks;
  pageWidth: number;
  pageHeight: number;
  isSelected: boolean;
  currentChunkPosition?: number;
  onSelect: () => void;
}

export type RegionWithChunks = Region & { chunkIndices: number[] };
