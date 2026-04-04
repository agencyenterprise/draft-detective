// Mock data for the Stitch redesign prototype
// Simulates a real RAND document review with reconstructed document + issues

export interface StitchIssue {
  id: string;
  category:
    | 'reference-validation'
    | 'unsupported-assertion'
    | 'citation-suggestion'
    | 'acronym-check'
    | 'factual-inconsistency';
  severity: 'critical' | 'warning' | 'suggestion';
  title: string;
  description: string;
  paragraph: number;
  proposedChange?: string;
}

export interface StitchDocument {
  title: string;
  authors: string;
  date: string;
  paragraphs: {
    id: number;
    text: string;
    highlights?: { start: number; end: number; issueId: string; color: 'yellow' | 'blue' | 'red' }[];
  }[];
}

export const mockDocument: StitchDocument = {
  title: 'Vitamin D Supplementation and Musculoskeletal Outcomes: A Systematic Review',
  authors: 'Dr. Sarah Chen, Dr. Marcus Rivera, Dr. Elena Volkov',
  date: 'March 15, 2026',
  paragraphs: [
    {
      id: 1,
      text: 'Vitamin D supplementation has been widely investigated as a potential intervention for improving musculoskeletal health, particularly in populations with documented deficiency. The growing body of evidence suggests that while supplementation reliably increases serum 25-hydroxyvitamin D concentrations, the downstream clinical benefits remain context-dependent and population-specific.',
    },
    {
      id: 2,
      text: 'A meta-analysis by Bolland et al. (2018) concluded that vitamin D supplementation does not prevent fractures or falls, nor does it have clinically meaningful effects on bone mineral density. However, this analysis has been criticized for pooling heterogeneous populations, including those with adequate baseline vitamin D levels, which may dilute the observed treatment effect in truly deficient individuals.',
      highlights: [{ start: 20, end: 40, issueId: 'issue-1', color: 'yellow' }],
    },
    {
      id: 3,
      text: 'In contrast, a randomized controlled trial conducted by Dawson-Hughes et al. demonstrated that daily supplementation of 700-800 IU significantly reduced the incidence of hip and non-vertebral fractures in ambulatory older adults. The effect was most pronounced in subjects with baseline serum levels below 50 nmol/L, supporting a threshold model of vitamin D efficacy rather than a linear dose-response relationship.',
      highlights: [{ start: 55, end: 82, issueId: 'issue-2', color: 'blue' }],
    },
    {
      id: 4,
      text: 'The VITAL study, one of the largest randomized trials to date with over 25,000 participants, found no significant reduction in cancer incidence or cardiovascular events with vitamin D supplementation at 2000 IU/day. Nevertheless, subgroup analyses revealed potential benefits in individuals with BMI below 25 and in African American participants, though these findings require confirmation in dedicated trials.',
    },
    {
      id: 5,
      text: 'Recent evidence from the D-Health trial in Australia further complicates the picture. Among 21,315 participants aged 60-84 years, monthly high-dose vitamin D (60,000 IU) did not reduce all-cause mortality over a 5-year follow-up period. The authors noted that the predominantly vitamin D-sufficient population may explain the null finding, reinforcing the importance of baseline status in trial design.',
      highlights: [{ start: 0, end: 27, issueId: 'issue-4', color: 'red' }],
    },
    {
      id: 6,
      text: 'From a mechanistic standpoint, vitamin D influences calcium homeostasis through its active metabolite 1,25-dihydroxyvitamin D, which promotes intestinal calcium absorption and regulates parathyroid hormone secretion. Deficiency leads to secondary hyperparathyroidism, increased bone turnover, and ultimately reduced bone mineral density. This well-established pathway provides the biological rationale for supplementation in deficient populations.',
    },
    {
      id: 7,
      text: 'The optimal dosing strategy remains debated. While daily low-dose regimens (800-2000 IU) appear safe and effective for maintaining adequate serum levels, bolus dosing strategies have yielded inconsistent results. Sanders et al. reported an paradoxical increase in fall risk with annual high-dose supplementation, potentially due to acute changes in calcium signaling or neuromuscular function following rapid increases in serum vitamin D.',
      highlights: [{ start: 200, end: 220, issueId: 'issue-5', color: 'yellow' }],
    },
    {
      id: 8,
      text: 'In summary, the evidence supports vitamin D supplementation as a corrective intervention in individuals with documented deficiency, particularly for musculoskeletal outcomes in older adults. Universal supplementation of replete populations is not supported by current evidence and may divert resources from targeted screening and treatment programs. Future research should prioritize adaptive trial designs that stratify by baseline vitamin D status and include diverse populations to improve generalizability.',
    },
  ],
};

export const mockIssues: StitchIssue[] = [
  {
    id: 'issue-1',
    category: 'reference-validation',
    severity: 'warning',
    title: 'Citation date discrepancy',
    description:
      'The Bolland et al. meta-analysis referenced here was published in 2014, not 2018. The 2018 publication is a separate updated analysis with different inclusion criteria.',
    paragraph: 2,
    proposedChange:
      'Update citation to "Bolland et al. (2014)" or replace with the 2018 updated analysis (Bolland MJ, Grey A, Avenell A. BMJ 2018;362:k3225).',
  },
  {
    id: 'issue-2',
    category: 'citation-suggestion',
    severity: 'suggestion',
    title: 'More recent evidence available',
    description:
      'The Dawson-Hughes reference is from 1997. A more recent and larger trial by Bischoff-Ferrari et al. (2020) provides updated fracture reduction data with similar conclusions.',
    paragraph: 3,
    proposedChange:
      'Consider adding: Bischoff-Ferrari HA, et al. "Effect of Vitamin D Supplementation on Musculoskeletal Health." NEJM 2020;383:1789-1800.',
  },
  {
    id: 'issue-3',
    category: 'unsupported-assertion',
    severity: 'critical',
    title: 'Subgroup claim lacks statistical support',
    description:
      'The claim about benefits in individuals with BMI below 25 and African American participants from VITAL is based on exploratory subgroup analyses that were not pre-specified and did not meet the threshold for statistical significance after multiple comparison correction.',
    paragraph: 4,
  },
  {
    id: 'issue-4',
    category: 'factual-inconsistency',
    severity: 'warning',
    title: 'Sample size discrepancy',
    description:
      'The D-Health trial enrolled 21,315 participants, but the intention-to-treat analysis included 20,322 due to exclusions. The text should clarify which number is being referenced.',
    paragraph: 5,
    proposedChange: 'Specify: "Among 21,315 enrolled participants (20,322 in the intention-to-treat analysis)..."',
  },
  {
    id: 'issue-5',
    category: 'reference-validation',
    severity: 'warning',
    title: 'Incomplete citation',
    description:
      'Sanders et al. is referenced without a year or journal. This likely refers to Sanders KM, et al. JAMA 2010;303(18):1815-1822, which should be explicitly cited.',
    paragraph: 7,
    proposedChange:
      'Add full citation: Sanders KM, Stuart AL, Williamson EJ, et al. "Annual High-Dose Oral Vitamin D and Falls and Fractures in Older Women." JAMA 2010;303(18):1815-1822.',
  },
  {
    id: 'issue-6',
    category: 'acronym-check',
    severity: 'suggestion',
    title: 'Undefined acronym',
    description:
      'The acronym "IU" (International Units) is used throughout without definition. While commonly understood in medical literature, best practice suggests defining it on first use.',
    paragraph: 3,
  },
  {
    id: 'issue-7',
    category: 'unsupported-assertion',
    severity: 'critical',
    title: 'Causal language without sufficient evidence',
    description:
      'The phrase "Deficiency leads to secondary hyperparathyroidism" implies a direct causal relationship. While well-established in clinical practice, the cited sources in this review do not directly support this mechanistic claim. Consider adding a primary source.',
    paragraph: 6,
  },
  {
    id: 'issue-8',
    category: 'citation-suggestion',
    severity: 'suggestion',
    title: 'Missing key systematic review',
    description:
      'The Cochrane review by Bjelakovic et al. (2014) on vitamin D supplementation for prevention of mortality is a highly relevant and frequently cited source that is absent from this review.',
    paragraph: 8,
    proposedChange:
      'Consider citing: Bjelakovic G, et al. "Vitamin D supplementation for prevention of mortality in adults." Cochrane Database Syst Rev 2014;(1):CD007470.',
  },
];

export const categoryLabels: Record<StitchIssue['category'], string> = {
  'reference-validation': 'Reference Validation',
  'unsupported-assertion': 'Unsupported Assertion',
  'citation-suggestion': 'Citation Suggestion',
  'acronym-check': 'Acronym Check',
  'factual-inconsistency': 'Factual Inconsistency',
};

export const severityLabels: Record<StitchIssue['severity'], string> = {
  critical: 'Critical',
  warning: 'Warning',
  suggestion: 'Suggestion',
};
