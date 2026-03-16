export interface PrototypeProject {
  id: string;
  title: string;
  status: 'Completed' | 'Processing';
  claims: number | null;
  citations: number | null;
  createdLabel: string;
  summary: string;
}

export interface PrototypeClaim {
  id: string;
  status: 'Supported' | 'Needs Review' | 'Flagged';
  evidenceCount: number;
  note: string;
  text: string;
}

export const prototypeProjects: PrototypeProject[] = [
  {
    id: 'demo-1',
    title: 'Vitamin D Supplementation Literature Review',
    status: 'Completed',
    claims: 18,
    citations: 26,
    createdLabel: 'Created 2 days ago',
    summary:
      'A completed review focused on fall risk, biomarker response, and evidence quality in deficiency contexts.',
  },
  {
    id: 'demo-2',
    title: 'FDA Guidance on AI/ML Medical Devices',
    status: 'Completed',
    claims: 24,
    citations: 41,
    createdLabel: 'Created 5 days ago',
    summary:
      'Regulatory guidance mapped into claims, references, and review-ready evidence clusters for faster validation.',
  },
  {
    id: 'demo-3',
    title: 'Climate Impact Assessment 2024',
    status: 'Processing',
    claims: null,
    citations: null,
    createdLabel: 'Created 1 hour ago',
    summary: 'A newly ingested document still moving through extraction and evidence matching workflows.',
  },
];

export const prototypeClaims: PrototypeClaim[] = [
  {
    id: 'claim-1',
    status: 'Supported',
    evidenceCount: 4,
    note: 'Consistent across meta-analyses in older adults with baseline deficiency.',
    text: 'Vitamin D supplementation modestly reduces fall risk in older adults with low baseline vitamin D levels.',
  },
  {
    id: 'claim-2',
    status: 'Needs Review',
    evidenceCount: 3,
    note: 'Benefit appears dose- and population-dependent, with mixed outcomes in broader cohorts.',
    text: 'Daily vitamin D supplementation improves bone mineral density in postmenopausal adults.',
  },
  {
    id: 'claim-3',
    status: 'Supported',
    evidenceCount: 5,
    note: 'Strong agreement in reviews that supplementation raises serum 25(OH)D concentrations.',
    text: 'Supplementation reliably increases serum 25-hydroxyvitamin D concentrations over 8 to 12 weeks.',
  },
  {
    id: 'claim-4',
    status: 'Flagged',
    evidenceCount: 2,
    note: 'Evidence is inconsistent and several cited sources focus on correlation rather than causation.',
    text: 'Vitamin D supplementation significantly reduces respiratory infection rates in all adult populations.',
  },
  {
    id: 'claim-5',
    status: 'Supported',
    evidenceCount: 4,
    note: 'Multiple randomized trials support improved outcomes when deficiency is corrected.',
    text: 'Correcting vitamin D deficiency is associated with improved musculoskeletal function in deficient patients.',
  },
];

export const prototypeTabs = [
  { value: 'summary', label: 'Summary', disabled: false },
  { value: 'document-explorer', label: 'Document Explorer', disabled: true },
  { value: 'analyses', label: 'Analyses', disabled: true },
  { value: 'references', label: 'References', disabled: true },
  { value: 'files', label: 'Files', disabled: true },
] as const;

export function getStatusTone(status: PrototypeClaim['status'] | PrototypeProject['status']) {
  switch (status) {
    case 'Supported':
    case 'Completed':
      return {
        badge: 'success' as const,
        dot: 'bg-emerald-600',
        line: 'bg-emerald-500/85',
        text: 'text-emerald-700',
        soft: 'bg-emerald-50 text-emerald-700',
      };
    case 'Needs Review':
    case 'Processing':
      return {
        badge: 'warning' as const,
        dot: 'bg-amber-500',
        line: 'bg-amber-400/90',
        text: 'text-amber-700',
        soft: 'bg-amber-50 text-amber-700',
      };
    case 'Flagged':
    default:
      return {
        badge: 'destructive' as const,
        dot: 'bg-rose-600',
        line: 'bg-rose-500/85',
        text: 'text-rose-700',
        soft: 'bg-rose-50 text-rose-700',
      };
  }
}
