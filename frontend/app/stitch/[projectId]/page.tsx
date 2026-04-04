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
      className="w-full text-left rounded-[4px] p-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#002045]"
      style={{
        backgroundColor: isActive ? '#fafbfc' : '#ffffff',
        boxShadow: isActive ? '0 4px 20px rgba(24,28,30,0.08)' : '0 1px 3px rgba(24,28,30,0.04)',
        borderLeft: `3px solid ${isActive ? severityColor : 'transparent'}`,
        borderTop: '1px solid #e5e9eb',
        borderRight: '1px solid #e5e9eb',
        borderBottom: '1px solid #e5e9eb',
        transition: 'background-color 150ms, box-shadow 150ms',
      }}
      onMouseEnter={(e) => {
        if (!isActive) e.currentTarget.style.backgroundColor = '#f7fafc';
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.backgroundColor = isActive ? '#fafbfc' : '#ffffff';
      }}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex items-center gap-1.5 min-w-0">
          <SeverityDot severity={issue.severity} />
          <span
            className="text-[11px] font-semibold truncate"
            style={{ fontFamily: "'Manrope', sans-serif", color: '#43474e' }}
          >
            {categoryLabels[issue.category]}
          </span>
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
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
      <p
        className="text-[13px] font-semibold mb-1.5"
        style={{ fontFamily: "'Manrope', sans-serif", color: '#181c1e', overflowWrap: 'break-word' }}
      >
        {issue.title}
      </p>

      {/* Description */}
      <p
        className="italic text-[13px] leading-relaxed"
        style={{ fontFamily: "'Newsreader', serif", color: '#43474e', overflowWrap: 'break-word' }}
      >
        {issue.description}
      </p>

      {/* Proposed change */}
      {issue.proposedChange && (
        <div className="mt-3 p-3 rounded-[3px]" style={{ backgroundColor: '#f7fafc' }}>
          <p className="text-[10px] font-semibold mb-1" style={{ fontFamily: "'Inter', sans-serif", color: '#545f72' }}>
            Proposed change
          </p>
          <p
            className="text-[13px]"
            style={{ fontFamily: "'Newsreader', serif", color: '#002045', overflowWrap: 'break-word' }}
          >
            {issue.proposedChange}
          </p>
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-2 mt-3">
        {issue.proposedChange && (
          <span
            className="flex-1 py-1.5 text-[11px] font-bold rounded-[3px] text-center cursor-pointer hover:opacity-90"
            style={{
              background: 'linear-gradient(135deg, #002045, #1a365d)',
              color: '#fff',
              transition: 'opacity 150ms',
            }}
          >
            Accept
          </span>
        )}
        <span
          className="flex-1 py-1.5 text-[11px] font-bold rounded-[3px] text-center cursor-pointer"
          style={{ backgroundColor: '#e5e9eb', color: '#181c1e', transition: 'background-color 150ms' }}
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
  if (!highlights || highlights.length === 0) return <>{text}</>;

  const colorMap = {
    yellow: { bg: 'rgba(251, 191, 36, 0.15)', border: '#f59e0b' },
    blue: { bg: 'rgba(96, 165, 250, 0.12)', border: '#60a5fa' },
    red: { bg: 'rgba(244, 63, 94, 0.12)', border: '#f43f5e' },
  };

  const sorted = [...highlights].sort((a, b) => a.start - b.start);
  const parts: React.ReactNode[] = [];
  let cursor = 0;

  sorted.forEach((h, i) => {
    if (h.start > cursor) parts.push(<span key={`t-${i}`}>{text.slice(cursor, h.start)}</span>);
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
  if (cursor < text.length) parts.push(<span key="end">{text.slice(cursor)}</span>);
  return <>{parts}</>;
}

/* ── Loading skeleton ── */

function LoadingSkeleton() {
  return (
    <div className="h-screen flex" style={{ backgroundColor: '#f7fafc' }}>
      <div className="w-[65%] p-10" style={{ backgroundColor: '#ffffff' }}>
        <div className="max-w-3xl mx-auto space-y-6 animate-pulse">
          <div className="h-10 w-3/4 rounded-[3px]" style={{ backgroundColor: '#e5e9eb' }} />
          <div className="h-4 w-1/3 rounded-[3px]" style={{ backgroundColor: '#ebeef0' }} />
          <div className="space-y-4 mt-8">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="space-y-2">
                <div className="h-4 w-full rounded-[3px]" style={{ backgroundColor: '#ebeef0' }} />
                <div className="h-4 w-5/6 rounded-[3px]" style={{ backgroundColor: '#ebeef0' }} />
              </div>
            ))}
          </div>
        </div>
      </div>
      <div className="w-[35%] p-5 space-y-4" style={{ backgroundColor: '#f1f4f6' }}>
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
    <div className="h-screen flex items-center justify-center" style={{ backgroundColor: '#f7fafc' }}>
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
          className="px-4 py-2 rounded-[3px] text-sm font-semibold hover:opacity-90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#002045]"
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

  useEffect(() => {
    const timer = setTimeout(() => setIsLoading(false), 600);
    return () => clearTimeout(timer);
  }, []);

  const filteredIssues = filter === 'all' ? mockIssues : mockIssues.filter((i) => i.category === filter);
  const criticalCount = mockIssues.filter((i) => i.severity === 'critical').length;
  const warningCount = mockIssues.filter((i) => i.severity === 'warning').length;
  const suggestionCount = mockIssues.filter((i) => i.severity === 'suggestion').length;
  const categories = [...new Set(mockIssues.map((i) => i.category))];

  const selectIssue = useCallback((issueId: string | null) => {
    setActiveIssueId(issueId);
    if (!issueId) return;
    requestAnimationFrame(() => {
      document.getElementById(`issue-card-${issueId}`)?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    });
    const issue = mockIssues.find((i) => i.id === issueId);
    if (issue) {
      requestAnimationFrame(() => {
        document.getElementById(`para-${issue.paragraph}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      });
    }
  }, []);

  if (error) return <ErrorState message={error} />;
  if (isLoading) return <LoadingSkeleton />;

  return (
    <div className="h-screen flex flex-col overflow-hidden" style={{ backgroundColor: '#f7fafc' }}>
      {/* ── Top Bar ── */}
      <header
        className="flex items-center justify-between px-6 shrink-0"
        style={{
          height: '52px',
          backgroundColor: '#ffffff',
          borderBottom: '1px solid rgba(196, 198, 207, 0.15)',
        }}
      >
        <div className="flex items-center gap-3 min-w-0 mr-4">
          <h1
            className="font-bold text-[15px] tracking-tight truncate"
            style={{ fontFamily: "'Manrope', sans-serif", color: '#002045' }}
            title={mockDocument.title}
          >
            {mockDocument.title}
          </h1>
          <span
            className="text-[11px] px-2 py-0.5 rounded-[3px] shrink-0"
            style={{ fontFamily: "'Inter', sans-serif", backgroundColor: '#e5e9eb', color: '#43474e' }}
          >
            Draft
          </span>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button
            className="text-[13px] font-semibold px-2.5 py-1 rounded-[3px] hover:bg-[#f1f4f6] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#002045]"
            style={{ fontFamily: "'Inter', sans-serif", color: '#002045', transition: 'background-color 150ms' }}
          >
            Share
          </button>
          <button
            className="text-[13px] font-semibold px-2.5 py-1 rounded-[3px] hover:bg-[#f1f4f6] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#002045]"
            style={{ fontFamily: "'Inter', sans-serif", color: '#002045', transition: 'background-color 150ms' }}
          >
            Export
          </button>
          <button
            className="px-3 py-1.5 rounded-[3px] text-[11px] font-bold tracking-wide hover:opacity-90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
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

      {/* ── Two-Column Layout ── */}
      <div className="flex flex-1 min-h-0">
        {/* ── Document Panel (65%) ── */}
        <section
          className="overflow-y-auto"
          style={{ width: '65%', backgroundColor: '#ffffff', padding: '2.5rem 2rem 2.5rem 3rem' }}
        >
          <div style={{ maxWidth: '680px', margin: '0 auto' }}>
            {/* Document Header */}
            <div style={{ marginBottom: '2rem' }}>
              <h2
                style={{
                  fontFamily: "'Manrope', sans-serif",
                  color: '#002045',
                  fontSize: '1.75rem',
                  fontWeight: 800,
                  letterSpacing: '-0.02em',
                  lineHeight: 1.2,
                  marginBottom: '0.5rem',
                }}
              >
                {mockDocument.title}
              </h2>
              <p
                style={{
                  fontFamily: "'Newsreader', serif",
                  color: '#545f72',
                  fontSize: '0.9375rem',
                  fontStyle: 'italic',
                }}
              >
                {mockDocument.authors}
              </p>
              <p
                style={{
                  fontFamily: "'Inter', sans-serif",
                  color: '#43474e',
                  fontSize: '0.8125rem',
                  marginTop: '0.25rem',
                }}
              >
                {mockDocument.date}
              </p>
            </div>

            {/* Document Body */}
            <div>
              {mockDocument.paragraphs.map((para) => {
                const paragraphIssues = mockIssues.filter((i) => i.paragraph === para.id);
                const isHighlighted = activeIssueId ? paragraphIssues.some((i) => i.id === activeIssueId) : false;
                const activeIssue = activeIssueId ? paragraphIssues.find((i) => i.id === activeIssueId) : null;
                const severityColor = activeIssue
                  ? { critical: '#f43f5e', warning: '#f59e0b', suggestion: '#60a5fa' }[activeIssue.severity]
                  : '#f59e0b';
                const bgTint = isHighlighted
                  ? activeIssue?.severity === 'critical'
                    ? 'rgba(244, 63, 94, 0.07)'
                    : activeIssue?.severity === 'suggestion'
                      ? 'rgba(96, 165, 250, 0.07)'
                      : 'rgba(251, 191, 36, 0.08)'
                  : 'transparent';

                return (
                  <div
                    key={para.id}
                    id={`para-${para.id}`}
                    className="relative"
                    style={{
                      backgroundColor: bgTint,
                      padding: isHighlighted ? '0.625rem 0.75rem' : '0.375rem 0',
                      marginBottom: '0.375rem',
                      borderRadius: '4px',
                      borderLeft: isHighlighted ? `3px solid ${severityColor}` : '3px solid transparent',
                      transition: 'background-color 200ms, padding 200ms',
                    }}
                  >
                    {/* Issue dots in margin */}
                    {paragraphIssues.length > 0 && (
                      <div
                        style={{
                          position: 'absolute',
                          left: '-1.75rem',
                          top: '0.5rem',
                          display: 'flex',
                          flexDirection: 'column',
                          gap: '4px',
                        }}
                      >
                        {paragraphIssues.map((issue) => (
                          <button
                            key={issue.id}
                            onClick={() => selectIssue(issue.id === activeIssueId ? null : issue.id)}
                            style={{
                              opacity: activeIssueId === issue.id ? 1 : 0.6,
                              transition: 'opacity 150ms, transform 150ms',
                            }}
                            className="hover:opacity-100 hover:scale-125 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#002045]"
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
                        fontSize: '1rem',
                        lineHeight: 1.8,
                        color: '#181c1e',
                        overflowWrap: 'break-word',
                      }}
                    >
                      <HighlightedText text={para.text} highlights={para.highlights} />
                    </p>
                  </div>
                );
              })}
            </div>
          </div>
        </section>

        {/* ── Issues Panel (35%) ── */}
        <aside className="flex flex-col overflow-hidden" style={{ width: '35%', backgroundColor: '#f1f4f6' }}>
          {/* Panel Header — compact */}
          <div className="shrink-0" style={{ padding: '1rem 1rem 0.75rem' }}>
            {/* Title row */}
            <div className="flex items-center justify-between" style={{ marginBottom: '0.5rem' }}>
              <h3
                style={{
                  fontFamily: "'Manrope', sans-serif",
                  color: '#002045',
                  fontSize: '0.8125rem',
                  fontWeight: 700,
                }}
              >
                Review Findings
              </h3>
              <span
                style={{
                  fontFamily: "'Inter', sans-serif",
                  backgroundColor: '#e5e9eb',
                  color: '#43474e',
                  fontSize: '0.6875rem',
                  padding: '2px 8px',
                  borderRadius: '10px',
                }}
              >
                {filter === 'all' ? `${mockIssues.length} issues` : `${filteredIssues.length} of ${mockIssues.length}`}
              </span>
            </div>

            {/* Severity + filters in one compact row */}
            <div
              className="flex items-center gap-3 flex-wrap"
              style={{ marginBottom: '0.5rem', fontSize: '0.6875rem', fontFamily: "'Inter', sans-serif" }}
            >
              <span className="flex items-center gap-1" role="status">
                <SeverityDot severity="critical" />
                <span style={{ color: '#43474e' }}>{criticalCount}</span>
              </span>
              <span className="flex items-center gap-1" role="status">
                <SeverityDot severity="warning" />
                <span style={{ color: '#43474e' }}>{warningCount}</span>
              </span>
              <span className="flex items-center gap-1" role="status">
                <SeverityDot severity="suggestion" />
                <span style={{ color: '#43474e' }}>{suggestionCount}</span>
              </span>
            </div>

            {/* Category Filter — compact pills */}
            <div className="flex flex-wrap gap-1" role="group" aria-label="Filter by category">
              <button
                onClick={() => setFilter('all')}
                className="focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-[#002045]"
                style={{
                  fontFamily: "'Inter', sans-serif",
                  fontSize: '0.625rem',
                  fontWeight: 500,
                  padding: '3px 8px',
                  borderRadius: '3px',
                  backgroundColor: filter === 'all' ? '#002045' : '#e5e9eb',
                  color: filter === 'all' ? '#fff' : '#43474e',
                  transition: 'background-color 150ms',
                  whiteSpace: 'nowrap',
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
                    className="focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-[#002045]"
                    style={{
                      fontFamily: "'Inter', sans-serif",
                      fontSize: '0.625rem',
                      fontWeight: 500,
                      padding: '3px 8px',
                      borderRadius: '3px',
                      backgroundColor: filter === cat ? '#002045' : '#e5e9eb',
                      color: filter === cat ? '#fff' : '#43474e',
                      transition: 'background-color 150ms',
                      whiteSpace: 'nowrap',
                    }}
                    aria-pressed={filter === cat}
                  >
                    {categoryLabels[cat]} ({count})
                  </button>
                );
              })}
            </div>
          </div>

          {/* Issue Cards — scrollable, takes remaining space */}
          <div
            ref={issuesPanelRef}
            className="flex-1 overflow-y-auto overflow-x-hidden"
            style={{ padding: '0 1rem 1rem' }}
          >
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {filteredIssues.length === 0 && (
                <div style={{ padding: '2rem 0', textAlign: 'center' }}>
                  <p style={{ fontFamily: "'Newsreader', serif", color: '#545f72', fontSize: '0.875rem' }}>
                    No issues match the selected filter.
                  </p>
                  <button
                    onClick={() => setFilter('all')}
                    style={{
                      fontFamily: "'Inter', sans-serif",
                      color: '#002045',
                      fontSize: '0.75rem',
                      fontWeight: 600,
                      marginTop: '0.5rem',
                    }}
                    className="focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#002045]"
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
          </div>

          {/* AI footer — minimal */}
          <div className="shrink-0" style={{ padding: '0.5rem 1rem 1rem' }}>
            <div
              style={{
                backgroundColor: '#1a365d',
                borderRadius: '3px',
                padding: '0.5rem 0.75rem',
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
              }}
            >
              <span
                style={{ color: '#d6e3ff', fontSize: '0.625rem', fontFamily: "'Inter', sans-serif", fontWeight: 600 }}
              >
                AI Review Engine
              </span>
              <span style={{ color: '#adc7f7', fontSize: '0.625rem', fontFamily: "'Inter', sans-serif" }}>
                · {mockIssues.length} findings
              </span>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}
