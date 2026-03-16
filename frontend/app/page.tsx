'use client';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { getStatusTone, prototypeProjects } from '@/lib/prototype-exploration';
import { motion, useReducedMotion } from 'motion/react';
import { ArrowRight, Brain, ChevronRight, FlaskConical, Github } from 'lucide-react';
import Link from 'next/link';

const easeOut = [0.22, 1, 0.36, 1] as const;
const easeInOut = [0.65, 0.05, 0.36, 1] as const;

const containerVariants = {
  hidden: {},
  show: {
    transition: {
      staggerChildren: 0.06,
    },
  },
};

const warmSection = {
  hidden: { opacity: 0, y: 20 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.48, ease: easeOut },
  },
};

export default function Home() {
  const shouldReduceMotion = useReducedMotion();
  const metrics = [
    { label: 'Projects', value: '3', tone: 'bg-stone-200/70 text-stone-900' },
    { label: 'Claims', value: '42', tone: 'bg-indigo-100 text-indigo-900' },
    { label: 'Coverage', value: '84%', tone: 'bg-amber-100 text-amber-900' },
  ];

  return (
    <div className="bg-[radial-gradient(circle_at_top,_rgba(99,102,241,0.09),_transparent_32%),linear-gradient(to_bottom,_#fcfaf6,_#ffffff_30%)]">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-14 px-4 py-10 sm:px-6 lg:px-8 lg:py-14">
        <motion.div initial="hidden" animate="show" variants={containerVariants} className="space-y-14">
          <motion.section
            variants={warmSection}
            className="relative overflow-hidden rounded-[2rem] border border-stone-200/80 bg-[#fbf8f3] p-6 shadow-[0_30px_90px_-45px_rgba(120,113,108,0.4)] sm:p-8 lg:p-10"
          >
            <div
              className="pointer-events-none absolute inset-0 opacity-40"
              style={{
                backgroundImage: 'radial-gradient(rgba(120,113,108,0.12) 0.7px, transparent 0.7px)',
                backgroundSize: '12px 12px',
              }}
            />
            <div className="relative grid gap-10 lg:grid-cols-[minmax(0,1.05fr)_minmax(320px,0.95fr)] lg:items-end">
              <div className="space-y-8">
                <Badge
                  variant="secondary"
                  className="w-fit gap-1.5 rounded-full border border-stone-200 bg-white/80 px-3 py-1 text-xs font-medium text-stone-700 shadow-sm"
                >
                  <Brain className="h-3 w-3" />
                  AI-powered evidence review
                </Badge>

                <div className="space-y-4">
                  <h1 className="max-w-3xl text-4xl font-semibold tracking-[-0.055em] text-stone-950 sm:text-5xl lg:text-[3.9rem] lg:leading-[0.98]">
                    AI Reviewer
                  </h1>
                  <p className="max-w-2xl text-base leading-7 text-stone-600 sm:text-lg">
                    Extract claims, map evidence, and surface what needs attention.
                  </p>
                </div>

                <div className="flex flex-col gap-3 sm:flex-row">
                  <Link href="/">
                    <Button
                      size="lg"
                      className="gap-2 rounded-full bg-indigo-700 px-5 shadow-sm hover:bg-indigo-800 active:scale-[0.97]"
                    >
                      <FlaskConical className="h-4 w-4" />
                      Start new project
                      <ArrowRight className="h-4 w-4" />
                    </Button>
                  </Link>
                  <Link
                    href="https://github.com/agencyenterprise/ai-reviewer"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    <Button
                      variant="outline"
                      size="lg"
                      className="gap-2 rounded-full border-stone-300 bg-white/80 px-5 text-stone-700 active:scale-[0.97]"
                    >
                      <Github className="h-4 w-4" />
                      View on GitHub
                    </Button>
                  </Link>
                </div>
              </div>

              <div className="rounded-[1.75rem] border border-stone-200/80 bg-white/85 p-4 shadow-[0_18px_45px_-30px_rgba(41,37,36,0.25)] backdrop-blur-sm sm:p-5">
                <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-1 xl:grid-cols-3">
                  {metrics.map((metric) => (
                    <div key={metric.label} className={`rounded-[1.2rem] px-4 py-4 ${metric.tone}`}>
                      <p className="text-xs uppercase tracking-[0.18em] opacity-70">{metric.label}</p>
                      <p className="mt-2 text-2xl font-semibold tracking-[-0.04em]">{metric.value}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </motion.section>

          <motion.section variants={warmSection} className="space-y-6">
            <div>
              <p className="text-sm font-medium text-stone-900">Your projects</p>
            </div>

            <div className="grid gap-4 lg:grid-cols-3">
              {prototypeProjects.map((project) => {
                const tone = getStatusTone(project.status);
                const hover = shouldReduceMotion ? {} : { y: -6 };
                const tap = shouldReduceMotion ? {} : { scale: 0.985 };

                return (
                  <motion.div
                    key={project.id}
                    variants={warmSection}
                    whileHover={hover}
                    whileTap={tap}
                    transition={{ duration: 0.22, ease: easeInOut }}
                  >
                    <Link href={`/prototype/${project.id}`}>
                      <Card className="h-full overflow-hidden rounded-[1.7rem] border-stone-200/80 bg-[#fffdfa] shadow-[0_24px_70px_-42px_rgba(41,37,36,0.38)] transition-shadow hover:shadow-[0_30px_80px_-38px_rgba(41,37,36,0.42)]">
                        <CardContent className="flex h-full flex-col gap-5 p-5 sm:p-6">
                          <div className={`h-1.5 w-16 rounded-full ${tone.line}`} />
                          <div className="space-y-3">
                            <div className="flex items-center justify-between gap-3">
                              <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${tone.soft}`}>
                                {project.status}
                              </span>
                              <span className="text-xs uppercase tracking-[0.18em] text-stone-500">
                                {project.id.replace('demo-', 'demo ')}
                              </span>
                            </div>
                            <h2 className="text-2xl font-semibold tracking-[-0.04em] text-stone-950">
                              {project.title}
                            </h2>
                            <p className="text-sm leading-6 text-stone-600">{project.summary}</p>
                          </div>

                          <div className="mt-auto space-y-4">
                            <div className="grid grid-cols-2 gap-3 rounded-[1.2rem] bg-stone-100/80 p-3 text-sm text-stone-700">
                              <div>
                                <p className="text-xs uppercase tracking-[0.14em] text-stone-500">Claims</p>
                                <p className="mt-1 font-semibold text-stone-900">{project.claims ?? '—'}</p>
                              </div>
                              <div>
                                <p className="text-xs uppercase tracking-[0.14em] text-stone-500">Evidence</p>
                                <p className="mt-1 font-semibold text-stone-900">{project.citations ?? 'Pending'}</p>
                              </div>
                            </div>
                            <div className="flex items-center justify-between text-sm text-stone-600">
                              <span>{project.createdLabel}</span>
                              <span className="inline-flex items-center gap-1 font-medium text-indigo-700">
                                Open review
                                <ChevronRight className="h-4 w-4" />
                              </span>
                            </div>
                          </div>
                        </CardContent>
                      </Card>
                    </Link>
                  </motion.div>
                );
              })}
            </div>
          </motion.section>
        </motion.div>
      </div>
    </div>
  );
}
