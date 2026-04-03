'use client';

import { mockDocument, mockIssues, categoryLabels, StitchIssue } from '@/lib/stitch-mock-data';
import { useState } from 'react';

/* ── Palette (matches stitch layout.tsx CSS vars) ── */
const C = {
  primary: '#002045',
  primaryContainer: '#1a365d',
  surface: '#f7fafc',
  surfaceLow: '#f1f4f6',
  surfaceContainer: '#ebeef0',
  surfaceHigh: '#e5e9eb',
  surfaceHighest: '#e0e3e5',
  surfaceLowest: '#ffffff',
  onSurface: '#181c1e',
  onSurfaceVariant: '#43474e',
  secondary: '#545f72',
  outlineVariant: '#c4c6cf',
  onPrimaryContainer: '#86a0cd',
};

const F = {
  headline: "'Manrope', sans-serif",
  body: "'Newsreader', serif",
  label: "'Inter', sans-serif",
};

/* ── Tiny components ── */

function SeverityDot({ severity }: { severity: StitchIssue['severity'] }) {
  const bg = { critical: '#f43f5e', warning: '#f59e0b', suggestion: '#60a5fa' }[severity];
  return <span className="w-2 h-2 rounded-full shrink-0 inline-block" style={{ backgroundColor: bg }} />;
}

/* ── Issue Card ── */

function IssueCard({ issue, isActive, onClick }: { issue: StitchIssue; isActive: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="w-full text-left rounded-[3px] p-5 transition-all duration-150"
      style={{
        backgroundColor: C.surfaceLowest,
        boxShadow: isActive ? '0 8px 32px rgba(24,28,30,0.06)' : 'none',
        border: isActive ? `1px solid ${C.outlineVariant}26` : '1px solid transparent',
      }}
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <SeverityDot severity={issue.severity} />
          <span
            className="text-[11px] font-bold uppercase tracking-wider"
            style={{ fontFamily: F.headline, color: C.onSurfaceVariant }}
          >
            {categoryLabels[issue.category]}
          </span>
        </div>
        <span className="text-[10px]" style={{ fontFamily: F.label, color: C.secondary }}>
          ¶{issue.paragraph}
        </span>
      </div>

      {/* Title */}
      <p className="text-sm font-semibold mb-2" style={{ fontFamily: F.headline, color: C.onSurface }}>
        {issue.title}
      </p>

      {/* Description */}
      <p className="italic text-sm leading-relaxed" style={{ fontFamily: F.body, color: C.onSurfaceVariant }}>
        {issue.description}
      </p>

      {/* Proposed change */}
      {issue.proposedChange && (
        <div className="mt-3 p-3 rounded-[3px]" style={{ backgroundColor: C.surface }}>
          <p
            className="text-[10px] uppercase font-bold mb-1 tracking-wider"
            style={{ fontFamily: F.label, color: C.secondary }}
          >
            Proposed Change
          </p>
          <p className="text-sm" style={{ fontFamily: F.body, color: C.primary }}>
            {issue.proposedChange}
          </p>
        </div>
      )}

      {/* Actions */}
      {issue.proposedChange && (
        <div className="flex gap-2 mt-3">
          <span
            className="flex-1 py-2 text-xs font-bold rounded-[3px] text-center cursor-pointer hover:opacity-90 transition-opacity"
            style={{
              background: `linear-gradient(135deg, ${C.primary}, ${C.primaryContainer})`,
              color: '#fff',
            }}
          >
            Accept
          </span>
          <span
            className="flex-1 py-2 text-xs font-bold rounded-[3px] text-center cursor-pointer transition-colors"
            style={{ backgroundColor: C.surfaceHigh, color: C.onSurface }}
          >
            Dismiss
          </span>
        </div>
      )}
    </button>
  );
}

/* ── Main Page ── */

export default function StitchPrototypePage() {
  const [activeIssueId, setActiveIssueId] = useState<string | null>(null);
  const [filter, setFilter] = useState<StitchIssue['category'] | 'all'>('all');

  const filteredIssues = filter === 'all' ? mockIssues : mockIssues.filter((i) => i.category === filter);

  const criticalCount = mockIssues.filter((i) => i.severity === 'critical').length;
  const warningCount = mockIssues.filter((i) => i.severity === 'warning').length;
  const suggestionCount = mockIssues.filter((i) => i.severity === 'suggestion').length;

  const categories = [...new Set(mockIssues.map((i) => i.category))];

  return (
    <div className="min-h-screen" style={{ backgroundColor: C.surface }}>
      {/* ── Top Bar ── */}
      <header
        className="h-14 flex items-center justify-between px-8"
        style={{
          backgroundColor: C.surfaceLowest,
          borderBottom: `1px solid ${C.outlineVariant}1a`,
        }}
      >
        <div className="flex items-center gap-4">
          <h1 className="font-bold text-lg tracking-tight" style={{ fontFamily: F.headline, color: C.primary }}>
            {mockDocument.title}
          </h1>
          <span
            className="text-xs px-2 py-0.5 rounded-[3px]"
            style={{
              fontFamily: F.label,
              backgroundColor: C.surfaceHigh,
              color: C.onSurfaceVariant,
            }}
          >
            Draft — {mockDocument.date}
          </span>
        </div>
        <div className="flex items-center gap-3">
          <button
            className="text-sm font-semibold px-3 py-1.5 rounded-[3px] transition-colors"
            style={{ fontFamily: F.label, color: C.primary }}
          >
            Share
          </button>
          <button
            className="text-sm font-semibold px-3 py-1.5 rounded-[3px] transition-colors"
            style={{ fontFamily: F.label, color: C.primary }}
          >
            Export
          </button>
          <button
            className="px-4 py-2 rounded-[3px] text-xs font-bold uppercase tracking-widest hover:opacity-90 transition-opacity"
            style={{
              background: `linear-gradient(135deg, ${C.primary}, ${C.primaryContainer})`,
              color: '#fff',
              fontFamily: F.label,
            }}
          >
            Re-analyze
          </button>
        </div>
      </header>

      {/* ── Two-Column Layout ── */}
      <div className="flex" style={{ height: 'calc(100vh - 3.5rem)' }}>
        {/* ── Document Panel (70%) ── */}
        <section className="overflow-y-auto p-12" style={{ flex: 7, backgroundColor: C.surfaceLowest }}>
          <div className="max-w-3xl mx-auto">
            {/* Document Header */}
            <div className="mb-10">
              <h2
                className="text-4xl font-extrabold tracking-tight mb-3"
                style={{ fontFamily: F.headline, color: C.primary, letterSpacing: '-0.02em' }}
              >
                {mockDocument.title}
              </h2>
              <p className="text-base italic" style={{ fontFamily: F.body, color: C.secondary }}>
                {mockDocument.authors}
              </p>
              <p className="text-sm mt-1" style={{ fontFamily: F.label, color: C.onSurfaceVariant }}>
                {mockDocument.date}
              </p>
            </div>

            {/* Document Body */}
            <article className="space-y-6">
              {mockDocument.paragraphs.map((para) => {
                const paragraphIssues = mockIssues.filter((i) => i.paragraph === para.id);
                const isHighlighted = activeIssueId ? paragraphIssues.some((i) => i.id === activeIssueId) : false;

                return (
                  <div
                    key={para.id}
                    className="relative transition-all duration-200 group"
                    style={{
                      backgroundColor: isHighlighted ? 'rgba(251, 191, 36, 0.08)' : 'transparent',
                      margin: isHighlighted ? '0 -1rem' : '0',
                      padding: isHighlighted ? '0.75rem 1rem' : '0',
                      borderRadius: '3px',
                      borderLeft: isHighlighted ? `3px solid #f59e0b` : '3px solid transparent',
                    }}
                  >
                    {/* Issue dots in margin */}
                    {paragraphIssues.length > 0 && (
                      <div className="absolute -left-10 top-1 flex flex-col gap-1.5">
                        {paragraphIssues.map((issue) => (
                          <button
                            key={issue.id}
                            onClick={() => setActiveIssueId(issue.id === activeIssueId ? null : issue.id)}
                            className="opacity-40 hover:opacity-100 transition-opacity"
                            title={issue.title}
                          >
                            <SeverityDot severity={issue.severity} />
                          </button>
                        ))}
                      </div>
                    )}

                    <p
                      style={{
                        fontFamily: F.body,
                        fontSize: '1.125rem',
                        lineHeight: 1.8,
                        color: C.onSurface,
                      }}
                    >
                      {para.text}
                    </p>
                  </div>
                );
              })}
            </article>

            {/* Decorative footer */}
            <div className="mt-16 flex justify-center opacity-20">
              <div className="w-16 h-1 rounded-full" style={{ backgroundColor: C.primaryContainer }} />
            </div>
          </div>
        </section>

        {/* ── Issues Panel (30%) ── */}
        <aside className="overflow-y-auto flex flex-col" style={{ flex: 3, backgroundColor: C.surfaceLow }}>
          {/* Panel Header */}
          <div className="px-5 pt-5 pb-3 flex-shrink-0">
            <div className="flex items-center justify-between mb-4">
              <h3
                className="font-bold text-sm uppercase tracking-widest"
                style={{ fontFamily: F.headline, color: C.secondary }}
              >
                Review Findings
              </h3>
              <span
                className="text-xs px-2 py-1 rounded-full"
                style={{
                  fontFamily: F.label,
                  backgroundColor: C.surfaceHigh,
                  color: C.onSurfaceVariant,
                }}
              >
                {mockIssues.length} Issues
              </span>
            </div>

            {/* Severity Summary */}
            <div className="flex gap-4 mb-4 text-xs" style={{ fontFamily: F.label }}>
              <span className="flex items-center gap-1.5">
                <SeverityDot severity="critical" />
                <span style={{ color: C.onSurfaceVariant }}>{criticalCount} Critical</span>
              </span>
              <span className="flex items-center gap-1.5">
                <SeverityDot severity="warning" />
                <span style={{ color: C.onSurfaceVariant }}>{warningCount} Warning</span>
              </span>
              <span className="flex items-center gap-1.5">
                <SeverityDot severity="suggestion" />
                <span style={{ color: C.onSurfaceVariant }}>{suggestionCount} Suggestion</span>
              </span>
            </div>

            {/* Category Filter */}
            <div className="flex flex-wrap gap-1">
              <button
                onClick={() => setFilter('all')}
                className="px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider rounded-[3px] transition-colors whitespace-nowrap"
                style={{
                  fontFamily: F.label,
                  backgroundColor: filter === 'all' ? C.primary : C.surfaceHigh,
                  color: filter === 'all' ? '#fff' : C.onSurfaceVariant,
                }}
              >
                All
              </button>
              {categories.map((cat) => {
                const count = mockIssues.filter((i) => i.category === cat).length;
                return (
                  <button
                    key={cat}
                    onClick={() => setFilter(cat === filter ? 'all' : cat)}
                    className="px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider rounded-[3px] transition-colors whitespace-nowrap"
                    style={{
                      fontFamily: F.label,
                      backgroundColor: filter === cat ? C.primary : C.surfaceHigh,
                      color: filter === cat ? '#fff' : C.onSurfaceVariant,
                    }}
                  >
                    {categoryLabels[cat]} ({count})
                  </button>
                );
              })}
            </div>
          </div>

          {/* Issue Cards */}
          <div className="flex-1 overflow-y-auto px-5 pb-5 space-y-3">
            {filteredIssues.map((issue) => (
              <IssueCard
                key={issue.id}
                issue={issue}
                isActive={activeIssueId === issue.id}
                onClick={() => setActiveIssueId(issue.id === activeIssueId ? null : issue.id)}
              />
            ))}
          </div>

          {/* AI Status Footer */}
          <div className="px-5 pb-5 pt-3 flex-shrink-0">
            <div className="rounded-[3px] p-4 flex items-center gap-4" style={{ backgroundColor: C.primaryContainer }}>
              <div>
                <p
                  className="text-[10px] font-bold uppercase tracking-widest"
                  style={{ fontFamily: F.label, color: C.onPrimaryContainer }}
                >
                  AI Review Engine
                </p>
                <p className="text-xs font-medium" style={{ fontFamily: F.label, color: C.onPrimaryContainer }}>
                  Analysis complete — {mockIssues.length} findings across {mockDocument.paragraphs.length} paragraphs
                </p>
              </div>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}
