import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { CheckCircle2, FileText } from 'lucide-react';

const mockClaims = [
  {
    id: '1',
    text: 'Vitamin D supplementation modestly reduces fall risk in older adults with low baseline vitamin D levels.',
    status: 'Supported',
    evidence: 4,
  },
  {
    id: '2',
    text: 'Daily vitamin D supplementation improves bone mineral density in postmenopausal adults.',
    status: 'Needs Review',
    evidence: 3,
  },
  {
    id: '3',
    text: 'Supplementation reliably increases serum 25-hydroxyvitamin D concentrations over 8 to 12 weeks.',
    status: 'Supported',
    evidence: 5,
  },
  {
    id: '4',
    text: 'Vitamin D supplementation significantly reduces respiratory infection rates in all adult populations.',
    status: 'Flagged',
    evidence: 2,
  },
  {
    id: '5',
    text: 'Correcting vitamin D deficiency is associated with improved musculoskeletal function in deficient patients.',
    status: 'Supported',
    evidence: 4,
  },
];

export default function OriginalProjectDetail() {
  return (
    <div className="container mx-auto max-w-6xl space-y-8 px-4 py-8">
      <div className="space-y-4">
        <div className="flex items-center gap-3">
          <h1 className="text-3xl font-bold">Vitamin D Supplementation Literature Review</h1>
          <Badge variant="default" className="gap-1">
            <CheckCircle2 className="h-3 w-3" />
            Completed
          </Badge>
        </div>
        <p className="text-sm text-muted-foreground">Created 2 days ago</p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Claims Extracted</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold">18</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Citations Found</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold">26</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Evidence Coverage</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold">84%</p>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="summary">
        <TabsList>
          <TabsTrigger value="summary">Summary</TabsTrigger>
          <TabsTrigger value="document-explorer" disabled>
            Document Explorer
          </TabsTrigger>
          <TabsTrigger value="analyses" disabled>
            Analyses
          </TabsTrigger>
          <TabsTrigger value="references" disabled>
            References
          </TabsTrigger>
          <TabsTrigger value="files" disabled>
            Files
          </TabsTrigger>
        </TabsList>

        <TabsContent value="summary" className="space-y-8">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FileText className="h-5 w-5" />
                Document Summary
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-muted-foreground">
              <p>
                This review evaluates current literature on vitamin D supplementation with a focus on musculoskeletal
                outcomes, fall prevention, and biomarker response in adults with low baseline vitamin D levels. Across
                the cited studies, supplementation most consistently improves serum 25-hydroxyvitamin D concentrations
                and appears to provide the clearest clinical benefit in populations with documented deficiency rather
                than the general population.
              </p>
              <p>
                Evidence for downstream outcomes is more nuanced. Several randomized trials and pooled analyses suggest
                modest improvement in fall risk and functional performance among older adults, but the magnitude of
                benefit varies by dosing cadence, adherence, and baseline health status.
              </p>
            </CardContent>
          </Card>

          <div className="space-y-4">
            <h2 className="text-xl font-bold">Claims</h2>
            <div className="space-y-3">
              {mockClaims.map((claim) => (
                <Card key={claim.id}>
                  <CardContent className="flex items-start gap-4 p-4">
                    <Badge
                      variant={
                        claim.status === 'Supported'
                          ? 'default'
                          : claim.status === 'Flagged'
                            ? 'destructive'
                            : 'secondary'
                      }
                    >
                      {claim.status}
                    </Badge>
                    <div className="flex-1">
                      <p className="font-medium">{claim.text}</p>
                    </div>
                    <p className="text-sm text-muted-foreground whitespace-nowrap">{claim.evidence} evidence</p>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
