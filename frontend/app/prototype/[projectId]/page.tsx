'use client';

import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { PrototypeClaim, getStatusTone, prototypeClaims, prototypeTabs } from '@/lib/prototype-exploration';
import { motion, useReducedMotion } from 'motion/react';
import { CheckCircle2 } from 'lucide-react';
import { useState } from 'react';

const easeOut = [0.22, 1, 0.36, 1] as const;
const easeInOut = [0.65, 0.05, 0.36, 1] as const;

const pageVariants = {
  hidden: {},
  show: {
    transition: {
      staggerChildren: 0.06,
    },
  },
};

const calmSection = {
  hidden: { opacity: 0, y: 14 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.42, ease: easeOut },
  },
};

function CalmClaimRow({ claim }: { claim: PrototypeClaim }) {
  const tone = getStatusTone(claim.status);
  const shouldReduceMotion = useReducedMotion();

  return (
    <motion.div
      whileHover={shouldReduceMotion ? {} : { y: -2 }}
      transition={{ duration: 0.18, ease: easeInOut }}
      className="rounded-xl border border-border/70 bg-white p-4 sm:p-5"
    >
      <div className="grid gap-4 sm:grid-cols-[140px_minmax(0,1fr)_120px] sm:items-start">
        <div>
          <Badge variant={tone.badge} className="gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium">
            <span className={`h-2 w-2 rounded-full ${tone.dot}`} />
            {claim.status}
          </Badge>
        </div>

        <div className="space-y-2">
          <p className="text-base font-medium leading-7 text-foreground">{claim.text}</p>
          <p className="text-sm leading-6 text-muted-foreground">{claim.note}</p>
        </div>

        <p className="text-sm text-muted-foreground sm:text-right">{claim.evidenceCount} references</p>
      </div>
    </motion.div>
  );
}

export default function PrototypeProjectPage() {
  const [activeTab, setActiveTab] = useState('summary');

  return (
    <div className="flex w-full flex-col gap-8 py-8 lg:py-10">
      <motion.div initial="hidden" animate="show" variants={pageVariants} className="space-y-8">
        <motion.section variants={calmSection} className="space-y-5 border-b border-border/70 pb-8">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div className="space-y-3">
              <div className="space-y-2">
                <h1 className="text-3xl font-semibold tracking-[-0.045em] text-foreground sm:text-4xl">
                  Vitamin D Supplementation Literature Review
                </h1>
                <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
                  <span className="inline-flex items-center gap-1.5 text-emerald-600">
                    <CheckCircle2 className="h-3.5 w-3.5" />
                    Completed
                  </span>
                  <span>·</span>
                  <span>Updated 2 days ago</span>
                  <span>·</span>
                  <span>Evidence synthesis completed 2 days ago</span>
                </div>
              </div>
            </div>
          </div>

          <Tabs value={activeTab} onValueChange={setActiveTab} className="gap-4">
            <TabsList className="h-auto w-full flex-wrap justify-start rounded-[1rem] bg-muted/70 p-1">
              {prototypeTabs.map((tab) => (
                <TabsTrigger
                  key={tab.value}
                  value={tab.value}
                  disabled={tab.disabled}
                  className="rounded-[0.8rem] px-3 py-2"
                >
                  {tab.label}
                </TabsTrigger>
              ))}
            </TabsList>

            <TabsContent value="summary" className="outline-none">
              <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_220px]">
                <Card className="rounded-xl border-border/70 shadow-none">
                  <CardHeader className="space-y-2">
                    <CardTitle className="text-base font-semibold">Document summary</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4 text-sm leading-7 text-muted-foreground">
                    <p>
                      This review evaluates current literature on vitamin D supplementation with a focus on
                      musculoskeletal outcomes, fall prevention, and biomarker response in adults with low baseline
                      vitamin D levels. Across the cited studies, supplementation most consistently improves serum
                      25-hydroxyvitamin D concentrations and appears to provide the clearest clinical benefit in
                      populations with documented deficiency rather than the general population.
                    </p>
                    <p>
                      Evidence for downstream outcomes is more nuanced. Several randomized trials and pooled analyses
                      suggest modest improvement in fall risk and functional performance among older adults, but the
                      magnitude of benefit varies by dosing cadence, adherence, and baseline health status. Claims about
                      universal benefit for bone density or respiratory outcomes are less stable and often depend on
                      subgroup interpretation.
                    </p>
                    <p>
                      Overall, the literature supports a measured conclusion: vitamin D supplementation is well
                      supported as a corrective intervention for deficiency and as part of broader bone-health
                      strategies, while stronger disease-specific claims require closer source review and tighter
                      qualification.
                    </p>
                  </CardContent>
                </Card>

                <div className="flex flex-col gap-3">
                  <Card className="rounded-xl border-border/70 shadow-none">
                    <CardContent className="p-4">
                      <p className="text-xs text-muted-foreground">Claims extracted</p>
                      <p className="mt-1 text-2xl font-semibold tracking-tight text-foreground">18</p>
                    </CardContent>
                  </Card>
                  <Card className="rounded-xl border-border/70 shadow-none">
                    <CardContent className="p-4">
                      <p className="text-xs text-muted-foreground">Citations found</p>
                      <p className="mt-1 text-2xl font-semibold tracking-tight text-foreground">26</p>
                    </CardContent>
                  </Card>
                  <Card className="rounded-xl border-border/70 shadow-none">
                    <CardContent className="p-4">
                      <p className="text-xs text-muted-foreground">Evidence coverage</p>
                      <p className="mt-1 text-2xl font-semibold tracking-tight text-foreground">84%</p>
                    </CardContent>
                  </Card>
                </div>
              </div>
            </TabsContent>
          </Tabs>
        </motion.section>

        <motion.section variants={calmSection} className="space-y-5">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h2 className="text-xl font-semibold tracking-[-0.03em] text-foreground">Claims overview</h2>
            </div>
            <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">5 claims</p>
          </div>
          <div className="space-y-3">
            {prototypeClaims.map((claim) => (
              <CalmClaimRow key={claim.id} claim={claim} />
            ))}
          </div>
        </motion.section>
      </motion.div>
    </div>
  );
}
