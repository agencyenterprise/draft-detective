'use client';

import { mockDocument, mockIssues, categoryLabels, severityLabels, StitchIssue } from '@/lib/stitch-mock-data';
import { useCallback, useEffect, useRef, useState } from 'react';

/* ── Severity dot ── */

function SeverityDot({ severity, size = 'sm' }: { severity: StitchIssue['severity']; size?: 'sm' | 'md' }) {
  const bg = { critical: '#f43f5e', warning: '#f59e0b', suggestion: '#60a5fa' }[severity];
  const cls = size === 'md' ? 'w-2.5 h-2.5' : 'w-2 h-2';
  return (
    <span
      className={`${cls} rounded-full shrink-0 inline-block`}
      style={{ backgroundColor: bg }}
      role="img"
      aria-label={`${severity} severity`}
    />
  );
}

/* ── Issue Card ── */

function IssueCard({ issue, isActive, onClick }: { issue: StitchIssue; isActive: boolean; onClick: () => void }) {
  const severityColor = { critical: '#f43f5e', warning: '#f59e0b', suggestion: '#60a5fa' }[issue.severity];

  return (
    <button
      id={`issue-card-${issue.id}`}
      onClick={onClick}
      aria-pressed={isActive}
      className="w-full text-left rounded-[4px] p-4 transition-[background-color,box-shadow,border-color] duration-150 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#002045]"
      style={{
        fontFamily: "'Inter', sans-serif",
        backgroundColor: isActive ? '#fafbfc' : '#ffffff',
        boxShadow: isActive ? '0 4px 20px rgba(24,28,30,0.08)' : '0 1px 3px rgba(24,28,30,0.04)',
        borderLeft: `3px solid ${isActive ? severityColor : 'transparent'}`,
        borderTop: '1px solid #e5e9eb',
        borderRight: '1px solid #e5e9eb',
        borderBottom: '1px solid #e5e9eb',
      }}
      onMouseEnter={(e) => {
        if (!isActive) e.currentTarget.style.backgroundColor = '#f7fafc';
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.backgroundColor = isActive ? '#fafbfc' : '#ffffff';
      }}
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          <SeverityDot severity={issue.severity} />
          <span className="text-[11px] font-semibold" style={{ fontFamily: "'Manrope', sans-serif", color: '#43474e' }}>
            {categoryLabels[issue.category]}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span
            className="text-[10px] px-1.5 py-0.5 rounded-[3px] font-semibold"
            style={{
              backgroundColor:
                issue.severity === 'critical' ? '#fef2f2' : issue.severity === 'warning' ? '#fffbeb' : '#eff6ff',
              color: severityColor,
            }}
          >
            {severityLabels[issue.severity]}
          </span>
          <span className="text-[10px]" style={{ color: '#545f72' }}>
            ¶{issue.paragraph}
          </span>
        </div>
      </div>

      {/* Title */}
      <p className="text-[13px] font-semibold mb-1.5" style={{ fontFamily: "'Manrope', sans-serif", color: '#181c1e' }}>
        {issue.title}
      </p>

      {/* Description */}
      <p className="italic text-[13px] leading-relaxed" style={{ fontFamily: "'Newsreader', serif", color: '#43474e' }}>
        {issue.description}
      </p>

      {/* Proposed change */}
      {issue.proposedChange && (
        <div className="mt-3 p-3 rounded-[3px]" style={{ backgroundColor: '#f7fafc' }}>
          <p className="text-[10px] font-semibold mb-1" style={{ fontFamily: "'Inter', sans-serif", color: '#545f72' }}>
            Proposed change
          </p>
          <p className="text-[13px]" style={{ fontFamily: "'Newsreader', serif", color: '#002045' }}>
            {issue.proposedChange}
          </p>
        </div>
      )}

      {/* Actions — all cards get at least Dismiss */}
      <div className="flex gap-2 mt-3">
        {issue.proposedChange && (
          <span
            className="flex-1 py-1.5 text-[11px] font-bold rounded-[3px] text-center cursor-pointer hover:opacity-90 transition-opacity"
            style={{
              background: 'linear-gradient(135deg, #002045, #1a365d)',
              color: '#fff',
            }}
          >
            Accept
          </span>
        )}
        <span
          className="flex-1 py-1.5 text-[11px] font-bold rounded-[3px] text-center cursor-pointer transition-[background-color] duration-150"
          style={{ backgroundColor: '#e5e9eb', color: '#181c1e' }}
          onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#e0e3e5')}
          onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = '#e5e9eb')}
        >
          Dismiss
        </span>
      </div>
    </button>
  );
}

/* ── Inline highlight renderer ── */

function HighlightedText({
  text,
  highlights,
}: {
  text: string;
  highlights?: { start: number; end: number; issueId: string; color: 'yellow' | 'blue' | 'red' }[];
}) {
  if (!highlights || highlights.length === 0) {
    return <>{text}</>;
  }

  const colorMap = {
    yellow: { bg: 'rgba(251, 191, 36, 0.15)', border: '#f59e0b' },
    blue: { bg: 'rgba(96, 165, 250, 0.12)', border: '#60a5fa' },
    red: { bg: 'rgba(244, 63, 94, 0.12)', border: '#f43f5e' },
  };

  const sorted = [...highlights].sort((a, b) => a.start - b.start);
  const parts: React.ReactNode[] = [];
  let cursor = 0;

  sorted.forEach((h, i) => {
    if (h.start > cursor) {
      parts.push(<span key={`t-${i}`}>{text.slice(cursor, h.start)}</span>);
    }
    const c = colorMap[h.color];
    parts.push(
      <span
        key={`h-${i}`}
        style={{
          backgroundColor: c.bg,
          borderBottom: `2px solid ${c.border}`,
          padding: '1px 2px',
          borderRadius: '2px',
        }}
      >
        {text.slice(h.start, h.end)}
      </span>,
    );
    cursor = h.end;
  });

  if (cursor < text.length) {
    parts.push(<span key="end">{text.slice(cursor)}</span>);
  }

  return <>{parts}</>;
}

/* ── Loading skeleton ── */

function LoadingSkeleton() {
  return (
    <div className="min-h-screen flex" style={{ backgroundColor: '#f7fafc' }}>
      <div className="flex-[65] p-12" style={{ backgroundColor: '#ffffff' }}>
        <div className="max-w-3xl mx-auto space-y-6 animate-pulse">
          <div className="h-10 w-3/4 rounded-[3px]" style={{ backgroundColor: '#e5e9eb' }} />
          <div className="h-4 w-1/3 rounded-[3px]" style={{ backgroundColor: '#ebeef0' }} />
          <div className="space-y-4 mt-8">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="space-y-2">
                <div className="h-4 w-full rounded-[3px]" style={{ backgroundColor: '#ebeef0' }} />
                <div className="h-4 w-5/6 rounded-[3px]" style={{ backgroundColor: '#ebeef0' }} />
                <div className="h-4 w-4/6 rounded-[3px]" style={{ backgroundColor: '#ebeef0' }} />
              </div>
            ))}
          </div>
        </div>
      </div>
      <div className="flex-[35] p-5 space-y-4" style={{ backgroundColor: '#f1f4f6' }}>
        <div className="h-5 w-1/2 rounded-[3px] animate-pulse" style={{ backgroundColor: '#e5e9eb' }} />
        {[...Array(3)].map((_, i) => (
          <div key={i} className="h-32 rounded-[4px] animate-pulse" style={{ backgroundColor: '#e5e9eb' }} />
        ))}
      </div>
    </div>
  );
}

/* ── Error state ── */

function ErrorState({ message }: { message: string }) {
  return (
    <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: '#f7fafc' }}>
      <div className="text-center max-w-md px-8">
        <div
          className="w-12 h-12 rounded-full flex items-center justify-center mx-auto mb-4"
          style={{ backgroundColor: '#fef2f2' }}
        >
          <span className="text-lg" style={{ color: '#f43f5e' }}>
            !
          </span>
        </div>
        <h2 className="text-lg font-semibold mb-2" style={{ fontFamily: "'Manrope', sans-serif", color: '#181c1e' }}>
          Unable to load review
        </h2>
        <p className="text-sm mb-6" style={{ fontFamily: "'Newsreader', serif", color: '#545f72' }}>
          {message}
        </p>
        <button
          onClick={() => window.location.reload()}
          className="px-4 py-2 rounded-[3px] text-sm font-semibold transition-opacity hover:opacity-90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#002045]"
          style={{
            background: 'linear-gradient(135deg, #002045, #1a365d)',
            color: '#fff',
            fontFamily: "'Inter', sans-serif",
          }}
        >
          Try again
        </button>
      </div>
    </div>
  );
}

/* ── Main Page ── */

export default function StitchPrototypePage() {
  const [activeIssueId, setActiveIssueId] = useState<string | null>(null);
  const [filter, setFilter] = useState<StitchIssue['category'] | 'all'>('all');
  const [isLoading, setIsLoading] = useState(true);
  const [error] = useState<string | null>(null);

  const issuesPanelRef = useRef<HTMLDivElement>(null);
  const documentRef = useRef<HTMLDivElement>(null);

  // Simulate data loading for prototype
  useEffect(() => {
    const timer = setTimeout(() => setIsLoading(false), 600);
    return () => clearTimeout(timer);
  }, []);

  const filteredIssues = filter === 'all' ? mockIssues : mockIssues.filter((i) => i.category === filter);

  const criticalCount = mockIssues.filter((i) => i.severity === 'critical').length;
  const warningCount = mockIssues.filter((i) => i.severity === 'warning').length;
  const suggestionCount = mockIssues.filter((i) => i.severity === 'suggestion').length;

  const categories = [...new Set(mockIssues.map((i) => i.category))];

  // Scroll-into-view on both sides
  const selectIssue = useCallback((issueId: string | null) => {
    setActiveIssueId(issueId);
    if (!issueId) return;

    requestAnimationFrame(() => {
      const card = document.getElementById(`issue-card-${issueId}`);
      card?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    });

    const issue = mockIssues.find((i) => i.id === issueId);
    if (issue) {
      requestAnimationFrame(() => {
        const para = document.getElementById(`para-${issue.paragraph}`);
        para?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      });
    }
  }, []);

  if (error) return <ErrorState message={error} />;
  if (isLoading) return <LoadingSkeleton />;

  return (
    <div className="min-h-screen" style={{ backgroundColor: '#f7fafc' }}>
      {/* ── Top Bar ── */}
      <header
        className="h-14 flex items-center justify-between px-4 sm:px-6 lg:px-8"
        style={{
          backgroundColor: '#ffffff',
          borderBottom: '1px solid rgba(196, 198, 207, 0.15)',
        }}
      >
        <div className="flex items-center gap-4 min-w-0 flex-1">
          <h1
            className="font-bold text-base lg:text-lg tracking-tight truncate"
            style={{ fontFamily: "'Manrope', sans-serif", color: '#002045' }}
            title={mockDocument.title}
          >
            {mockDocument.title}
          </h1>
          <span
            className="text-xs px-2 py-0.5 rounded-[3px] shrink-0 hidden sm:inline"
            style={{
              fontFamily: "'Inter', sans-serif",
              backgroundColor: '#e5e9eb',
              color: '#43474e',
            }}
          >
            Draft — {mockDocument.date}
          </span>
        </div>
        <div className="flex items-center gap-2 lg:gap-3 shrink-0">
          <button
            className="text-sm font-semibold px-3 py-1.5 rounded-[3px] transition-[background-color] duration-150 hover:bg-[#f1f4f6] hidden sm:inline-flex focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#002045]"
            style={{ fontFamily: "'Inter', sans-serif", color: '#002045' }}
          >
            Share
          </button>
          <button
            className="text-sm font-semibold px-3 py-1.5 rounded-[3px] transition-[background-color] duration-150 hover:bg-[#f1f4f6] hidden sm:inline-flex focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#002045]"
            style={{ fontFamily: "'Inter', sans-serif", color: '#002045' }}
          >
            Export
          </button>
          <button
            className="px-4 py-2 rounded-[3px] text-xs font-bold tracking-wide hover:opacity-90 transition-opacity focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
            style={{
              background: 'linear-gradient(135deg, #002045, #1a365d)',
              color: '#fff',
              fontFamily: "'Inter', sans-serif",
            }}
          >
            Re-analyze
          </button>
        </div>
      </header>

      {/* ── Two-Column Layout (65/35, responsive) ── */}
      <div className="flex flex-col lg:flex-row" style={{ height: 'calc(100vh - 3.5rem)' }}>
        {/* ── Document Panel ── */}
        <section
          ref={documentRef}
          className="overflow-y-auto py-8 px-6 lg:py-10 lg:px-8 flex-1 lg:flex-none"
          style={{ backgroundColor: '#ffffff' }}
          /* lg gets 65% via inline style below */
        >
          <div className="max-w-3xl mx-auto lg:pl-10">
            {/* Document Header */}
            <div className="mb-8 lg:mb-10">
              <h2
                className="text-2xl lg:text-3xl font-extrabold tracking-tight mb-3"
                style={{ fontFamily: "'Manrope', sans-serif", color: '#002045', letterSpacing: '-0.02em' }}
              >
                {mockDocument.title}
              </h2>
              <p className="text-base italic" style={{ fontFamily: "'Newsreader', serif", color: '#545f72' }}>
                {mockDocument.authors}
              </p>
              <p className="text-sm mt-1" style={{ fontFamily: "'Inter', sans-serif", color: '#43474e' }}>
                {mockDocument.date}
              </p>
            </div>

            {/* Document Body */}
            <article className="space-y-5">
              {mockDocument.paragraphs.map((para) => {
                const paragraphIssues = mockIssues.filter((i) => i.paragraph === para.id);
                const isHighlighted = activeIssueId ? paragraphIssues.some((i) => i.id === activeIssueId) : false;
                const activeIssue = activeIssueId ? paragraphIssues.find((i) => i.id === activeIssueId) : null;
                const severityColor = activeIssue
                  ? { critical: '#f43f5e', warning: '#f59e0b', suggestion: '#60a5fa' }[activeIssue.severity]
                  : '#f59e0b';

                return (
                  <div
                    key={para.id}
                    id={`para-${para.id}`}
                    className="relative transition-[background-color,padding,margin,border-color] duration-200"
                    style={{
                      backgroundColor: isHighlighted
                        ? activeIssue?.severity === 'critical'
                          ? 'rgba(244, 63, 94, 0.07)'
                          : activeIssue?.severity === 'suggestion'
                            ? 'rgba(96, 165, 250, 0.07)'
                            : 'rgba(251, 191, 36, 0.08)'
                        : 'transparent',
                      margin: isHighlighted ? '0 -1rem' : '0',
                      padding: isHighlighted ? '0.75rem 1rem' : '0',
                      borderRadius: '4px',
                      borderLeft: isHighlighted ? `3px solid ${severityColor}` : '3px solid transparent',
                    }}
                  >
                    {/* Issue dots in margin */}
                    {paragraphIssues.length > 0 && (
                      <div className="absolute -left-8 top-1 flex flex-col gap-1.5 hidden lg:flex">
                        {paragraphIssues.map((issue) => (
                          <button
                            key={issue.id}
                            onClick={() => selectIssue(issue.id === activeIssueId ? null : issue.id)}
                            className="opacity-70 hover:opacity-100 hover:scale-125 transition-[opacity,transform] duration-150 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#002045]"
                            title={issue.title}
                            aria-label={`${issue.title} — ${severityLabels[issue.severity]}`}
                          >
                            <SeverityDot severity={issue.severity} size="md" />
                          </button>
                        ))}
                      </div>
                    )}

                    <p
                      style={{
                        fontFamily: "'Newsreader', serif",
                        fontSize: '1.0625rem',
                        lineHeight: 1.8,
                        color: '#181c1e',
                      }}
                    >
                      <HighlightedText text={para.text} highlights={para.highlights} />
                    </p>
                  </div>
                );
              })}
            </article>

            {/* Decorative footer */}
            <div className="mt-16 flex justify-center opacity-20">
              <div className="w-16 h-1 rounded-full" style={{ backgroundColor: '#1a365d' }} />
            </div>
          </div>
        </section>

        {/* ── Issues Panel (35%) ── */}
        <aside
          className="overflow-hidden flex flex-col w-full lg:w-[35%] lg:min-w-[380px] lg:max-w-[520px]"
          style={{ backgroundColor: '#f1f4f6' }}
        >
          {/* Panel Header */}
          <div className="px-4 lg:px-5 pt-4 lg:pt-5 pb-3 flex-shrink-0">
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-bold text-sm" style={{ fontFamily: "'Manrope', sans-serif", color: '#002045' }}>
                Review Findings
              </h3>
              <span
                className="text-[11px] px-2 py-0.5 rounded-full font-medium"
                style={{
                  fontFamily: "'Inter', sans-serif",
                  backgroundColor: '#e5e9eb',
                  color: '#43474e',
                }}
              >
                {filter === 'all'
                  ? `${mockIssues.length} issues`
                  : `${filteredIssues.length} of ${mockIssues.length} issues`}
              </span>
            </div>

            {/* Severity Summary */}
            <div
              className="flex flex-wrap gap-x-4 gap-y-1 mb-3 text-[11px]"
              style={{ fontFamily: "'Inter', sans-serif" }}
            >
              <span className="flex items-center gap-1.5" role="status">
                <SeverityDot severity="critical" />
                <span style={{ color: '#43474e' }}>{criticalCount} critical</span>
              </span>
              <span className="flex items-center gap-1.5" role="status">
                <SeverityDot severity="warning" />
                <span style={{ color: '#43474e' }}>{warningCount} warning</span>
              </span>
              <span className="flex items-center gap-1.5" role="status">
                <SeverityDot severity="suggestion" />
                <span style={{ color: '#43474e' }}>{suggestionCount} suggestion</span>
              </span>
            </div>

            {/* Category Filter */}
            <div className="flex flex-wrap gap-1.5" role="group" aria-label="Filter by category">
              <button
                onClick={() => setFilter('all')}
                className="px-2.5 py-1 text-[11px] font-medium rounded-[3px] transition-[background-color,color] duration-150 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#002045]"
                style={{
                  fontFamily: "'Inter', sans-serif",
                  backgroundColor: filter === 'all' ? '#002045' : '#e5e9eb',
                  color: filter === 'all' ? '#fff' : '#43474e',
                }}
                aria-pressed={filter === 'all'}
              >
                All
              </button>
              {categories.map((cat) => {
                const count = mockIssues.filter((i) => i.category === cat).length;
                return (
                  <button
                    key={cat}
                    onClick={() => setFilter(cat === filter ? 'all' : cat)}
                    className="px-2.5 py-1 text-[11px] font-medium rounded-[3px] transition-[background-color,color] duration-150 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#002045]"
                    style={{
                      fontFamily: "'Inter', sans-serif",
                      backgroundColor: filter === cat ? '#002045' : '#e5e9eb',
                      color: filter === cat ? '#fff' : '#43474e',
                    }}
                    aria-pressed={filter === cat}
                  >
                    {categoryLabels[cat]} ({count})
                  </button>
                );
              })}
            </div>
          </div>

          {/* Issue Cards */}
          <div ref={issuesPanelRef} className="flex-1 overflow-y-auto px-4 pb-4 space-y-2.5">
            {filteredIssues.length === 0 && (
              <div className="py-8 text-center">
                <p className="text-sm" style={{ fontFamily: "'Newsreader', serif", color: '#545f72' }}>
                  No issues match the selected filter.
                </p>
                <button
                  onClick={() => setFilter('all')}
                  className="text-xs font-semibold mt-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#002045]"
                  style={{ fontFamily: "'Inter', sans-serif", color: '#002045' }}
                >
                  Clear filter
                </button>
              </div>
            )}
            {filteredIssues.map((issue) => (
              <IssueCard
                key={issue.id}
                issue={issue}
                isActive={activeIssueId === issue.id}
                onClick={() => selectIssue(issue.id === activeIssueId ? null : issue.id)}
              />
            ))}
          </div>

          {/* AI footer — compact, good contrast */}
          <div className="px-4 pb-4 pt-2 flex-shrink-0">
            <div className="rounded-[3px] px-4 py-2.5 flex items-center gap-3" style={{ backgroundColor: '#1a365d' }}>
              <div
                className="w-6 h-6 rounded-full flex items-center justify-center shrink-0"
                style={{ backgroundColor: 'rgba(214, 227, 255, 0.15)' }}
              >
                <span className="text-[10px]" style={{ color: '#d6e3ff' }}>
                  ✦
                </span>
              </div>
              <div>
                <p
                  className="text-[10px] font-semibold"
                  style={{ fontFamily: "'Inter', sans-serif", color: '#d6e3ff' }}
                >
                  AI Review Engine
                </p>
                <p className="text-[10px]" style={{ fontFamily: "'Inter', sans-serif", color: '#adc7f7' }}>
                  {mockIssues.length} findings · {mockDocument.paragraphs.length} paragraphs analyzed
                </p>
              </div>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}
