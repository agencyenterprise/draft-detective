export type BBox = {
  l: number; // left (x0)
  b: number; // bottom (y0)
  r: number; // right (x1)
  t: number; // top (y1)
};

export type RegionKind = 'text' | 'table' | 'picture' | 'kv';

export type Region = {
  id: string;
  page: number;
  bbox: BBox;
  kind: RegionKind;
};

export type ChunkToItems = Record<string, Region[]>;

export type DoclingPage = {
  page?: number;
  size?: {
    width: number;
    height: number;
  };
  width?: number;
  height?: number;
  image?: string; // Base64 image data
  [key: string]: any;
};

export type DoclingItem = {
  self_ref?: string;
  text?: string;
  content?: string;
  prov?: Array<{
    page: number;
    bbox: BBox;
    [key: string]: any;
  }>;
  [key: string]: any;
};

export type DoclingJsonContent = {
  pages?: DoclingPage[];
  texts?: DoclingItem[];
  tables?: DoclingItem[];
  pictures?: DoclingItem[];
  body?: DoclingItem[];
  key_value_items?: DoclingItem[];
  [key: string]: any;
};

export type DoclingDocument = DoclingJsonContent;
