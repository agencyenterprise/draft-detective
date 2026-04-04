'use client';

import {
  mockDocument,
  mockIssues as initialIssues,
  categoryLabels,
  severityLabels,
  StitchIssue,
} from '@/lib/stitch-mock-data';
import { useCallback, useEffect, useRef, useState } from 'react';

/* ── Colors from stitch design system ── */
const S = {
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
  primaryFixed: '#d6e3ff',
  primaryFixedDim: '#adc7f7',
};

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

/* ── Issue Card (stitch-compliant: no borders, bg shift on hover, shadow-glow) ── */
function IssueCard({
  issue,
  isActive,
  onClick,
  onAccept,
  onDismiss,
}: {
  issue: StitchIssue;
  isActive: boolean;
  onClick: () => void;
  onAccept: () => void;
  onDismiss: () => void;
}) {
  const severityColor = { critical: '#f43f5e', warning: '#f59e0b', suggestion: '#60a5fa' }[issue.severity];

  return (
    <div
      id={`issue-card-${issue.id}`}
      onClick={onClick}
      role="button"
      tabIndex={0}
      aria-pressed={isActive}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onClick();
        }
      }}
      className="cursor-pointer rounded-[6px] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#002045]"
      style={{
        /* Stitch: cards use surfaceLowest bg, hover→white, no borders, shadow-glow */
        backgroundColor: isActive ? S.surfaceLowest : S.surfaceLow,
        boxShadow: isActive
          ? `0 8px 32px rgba(24,28,30,0.04), inset 3px 0 0 ${severityColor}`
          : '0 1px 2px rgba(24,28,30,0.02)',
        padding: '1.25rem',
        transition: 'background-color 200ms, box-shadow 200ms',
      }}
      onMouseEnter={(e) => {
        if (!isActive) e.currentTarget.style.backgroundColor = S.surfaceLowest;
      }}
      onMouseLeave={(e) => {
        if (!isActive) e.currentTarget.style.backgroundColor = S.surfaceLow;
      }}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-2" style={{ marginBottom: '0.5rem' }}>
        <div className="flex items-center gap-1.5 min-w-0">
          <SeverityDot severity={issue.severity} />
          <span
            style={{
              fontFamily: "'Manrope', sans-serif",
              color: S.onSurfaceVariant,
              fontSize: '0.6875rem',
              fontWeight: 600,
            }}
          >
            {categoryLabels[issue.category]}
          </span>
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          <span
            style={{
              fontSize: '0.625rem',
              padding: '2px 6px',
              borderRadius: '3px',
              fontWeight: 600,
              backgroundColor:
                issue.severity === 'critical' ? '#fef2f2' : issue.severity === 'warning' ? '#fffbeb' : '#eff6ff',
              color: severityColor,
            }}
          >
            {severityLabels[issue.severity]}
          </span>
          <span style={{ fontSize: '0.625rem', color: S.secondary }}>¶{issue.paragraph}</span>
        </div>
      </div>

      {/* Title */}
      <p
        style={{
          fontFamily: "'Manrope', sans-serif",
          color: S.onSurface,
          fontSize: '0.8125rem',
          fontWeight: 600,
          marginBottom: '0.375rem',
          overflowWrap: 'break-word',
        }}
      >
        {issue.title}
      </p>

      {/* Description — Newsreader per stitch rules */}
      <p
        style={{
          fontFamily: "'Newsreader', serif",
          color: S.onSurfaceVariant,
          fontSize: '0.8125rem',
          fontStyle: 'italic',
          lineHeight: 1.6,
          overflowWrap: 'break-word',
        }}
      >
        {issue.description}
      </p>

      {/* Proposed change */}
      {issue.proposedChange && (
        <div style={{ marginTop: '0.75rem', padding: '0.75rem', borderRadius: '4px', backgroundColor: S.surface }}>
          <p
            style={{
              fontFamily: "'Inter', sans-serif",
              color: S.secondary,
              fontSize: '0.625rem',
              fontWeight: 600,
              marginBottom: '0.25rem',
            }}
          >
            Proposed change
          </p>
          <p
            style={{
              fontFamily: "'Newsreader', serif",
              color: S.primary,
              fontSize: '0.8125rem',
              lineHeight: 1.5,
              overflowWrap: 'break-word',
            }}
          >
            {issue.proposedChange}
          </p>
        </div>
      )}

      {/* Actions — Accept/Dismiss (stitch: gradient primary + surface secondary) */}
      <div className="flex gap-2" style={{ marginTop: '0.75rem' }}>
        {issue.proposedChange && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onAccept();
            }}
            className="flex-1 rounded-[6px] text-center cursor-pointer hover:opacity-90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
            style={{
              background: `linear-gradient(135deg, ${S.primary}, ${S.primaryContainer})`,
              color: '#fff',
              fontFamily: "'Inter', sans-serif",
              fontSize: '0.6875rem',
              fontWeight: 700,
              padding: '0.5rem 0',
              transition: 'opacity 150ms',
            }}
          >
            Accept
          </button>
        )}
        <button
          onClick={(e) => {
            e.stopPropagation();
            onDismiss();
          }}
          className="flex-1 rounded-[6px] text-center cursor-pointer focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#002045]"
          style={{
            backgroundColor: S.surfaceHigh,
            color: S.onSurface,
            fontFamily: "'Inter', sans-serif",
            fontSize: '0.6875rem',
            fontWeight: 700,
            padding: '0.5rem 0',
            transition: 'background-color 150ms',
          }}
          onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = S.surfaceHighest)}
          onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = S.surfaceHigh)}
        >
          Dismiss
        </button>
      </div>
    </div>
  );
}

/* ── Inline highlights ── */
function HighlightedText({
  text,
  highlights,
}: {
  text: string;
  highlights?: { start: number; end: number; issueId: string; color: 'yellow' | 'blue' | 'red' }[];
}) {
  if (!highlights || highlights.length === 0) return <>{text}</>;
  const cm = {
    yellow: { bg: 'rgba(251,191,36,0.15)', b: '#f59e0b' },
    blue: { bg: 'rgba(96,165,250,0.12)', b: '#60a5fa' },
    red: { bg: 'rgba(244,63,94,0.12)', b: '#f43f5e' },
  };
  const sorted = [...highlights].sort((a, b) => a.start - b.start);
  const parts: React.ReactNode[] = [];
  let cur = 0;
  sorted.forEach((h, i) => {
    if (h.start > cur) parts.push(<span key={`t${i}`}>{text.slice(cur, h.start)}</span>);
    const c = cm[h.color];
    parts.push(
      <span
        key={`h${i}`}
        style={{ backgroundColor: c.bg, borderBottom: `2px solid ${c.b}`, padding: '1px 2px', borderRadius: '2px' }}
      >
        {text.slice(h.start, h.end)}
      </span>,
    );
    cur = h.end;
  });
  if (cur < text.length) parts.push(<span key="e">{text.slice(cur)}</span>);
  return <>{parts}</>;
}

/* ── Loading ── */
function LoadingSkeleton() {
  return (
    <div className="h-screen flex" style={{ backgroundColor: S.surface }}>
      <div style={{ width: '65%', backgroundColor: S.surfaceLowest, padding: '2.5rem' }}>
        <div className="max-w-3xl mx-auto space-y-6 animate-pulse">
          <div className="h-10 w-3/4 rounded-[4px]" style={{ backgroundColor: S.surfaceHigh }} />
          <div className="h-4 w-1/3 rounded-[4px]" style={{ backgroundColor: S.surfaceContainer }} />
          {[...Array(5)].map((_, i) => (
            <div key={i} className="space-y-2">
              <div className="h-4 w-full rounded-[4px]" style={{ backgroundColor: S.surfaceContainer }} />
              <div className="h-4 w-5/6 rounded-[4px]" style={{ backgroundColor: S.surfaceContainer }} />
            </div>
          ))}
        </div>
      </div>
      <div style={{ width: '35%', backgroundColor: S.surfaceLow, padding: '1.25rem' }} className="space-y-4">
        <div className="h-5 w-1/2 rounded-[4px] animate-pulse" style={{ backgroundColor: S.surfaceHigh }} />
        {[...Array(3)].map((_, i) => (
          <div key={i} className="h-32 rounded-[6px] animate-pulse" style={{ backgroundColor: S.surfaceHigh }} />
        ))}
      </div>
    </div>
  );
}

/* ── Error ── */
function ErrorState({ message }: { message: string }) {
  return (
    <div className="h-screen flex items-center justify-center" style={{ backgroundColor: S.surface }}>
      <div className="text-center max-w-md px-8">
        <div
          className="w-12 h-12 rounded-full flex items-center justify-center mx-auto mb-4"
          style={{ backgroundColor: '#fef2f2' }}
        >
          <span style={{ color: '#f43f5e', fontSize: '1.125rem' }}>!</span>
        </div>
        <h2
          style={{
            fontFamily: "'Manrope', sans-serif",
            color: S.onSurface,
            fontSize: '1.125rem',
            fontWeight: 600,
            marginBottom: '0.5rem',
          }}
        >
          Unable to load review
        </h2>
        <p style={{ fontFamily: "'Newsreader', serif", color: S.secondary, marginBottom: '1.5rem' }}>{message}</p>
        <button
          onClick={() => window.location.reload()}
          className="focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
          style={{
            background: `linear-gradient(135deg, ${S.primary}, ${S.primaryContainer})`,
            color: '#fff',
            fontFamily: "'Inter', sans-serif",
            fontSize: '0.875rem',
            fontWeight: 600,
            padding: '0.5rem 1rem',
            borderRadius: '6px',
          }}
        >
          Try again
        </button>
      </div>
    </div>
  );
}

/* ── Accepted toast animation ── */
function AcceptedToast({ text, onDone }: { text: string; onDone: () => void }) {
  useEffect(() => {
    const t = setTimeout(onDone, 2200);
    return () => clearTimeout(t);
  }, [onDone]);
  return (
    <div
      className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 animate-[fadeInUp_300ms_ease-out]"
      style={{
        backgroundColor: S.primaryContainer,
        color: S.primaryFixed,
        fontFamily: "'Inter', sans-serif",
        fontSize: '0.8125rem',
        fontWeight: 600,
        padding: '0.625rem 1.25rem',
        borderRadius: '6px',
        boxShadow: '0 8px 32px rgba(0,32,69,0.15)',
      }}
    >
      ✓ {text}
    </div>
  );
}

/* ══════════════════ Main Page ══════════════════ */

export default function StitchPrototypePage() {
  const [issues, setIssues] = useState(initialIssues);
  const [activeIssueId, setActiveIssueId] = useState<string | null>(null);
  const [filter, setFilter] = useState<StitchIssue['category'] | 'all'>('all');
  const [isLoading, setIsLoading] = useState(true);
  const [error] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [accepted, setAccepted] = useState<Set<string>>(new Set());
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());

  const issuesPanelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const t = setTimeout(() => setIsLoading(false), 600);
    return () => clearTimeout(t);
  }, []);

  const visibleIssues = issues.filter((i) => !dismissed.has(i.id));
  const filteredIssues = filter === 'all' ? visibleIssues : visibleIssues.filter((i) => i.category === filter);
  const criticalCount = visibleIssues.filter((i) => i.severity === 'critical').length;
  const warningCount = visibleIssues.filter((i) => i.severity === 'warning').length;
  const suggestionCount = visibleIssues.filter((i) => i.severity === 'suggestion').length;
  const categories = [...new Set(visibleIssues.map((i) => i.category))];

  const selectIssue = useCallback(
    (issueId: string | null) => {
      setActiveIssueId(issueId);
      if (!issueId) return;
      requestAnimationFrame(() => {
        document.getElementById(`issue-card-${issueId}`)?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        const issue = issues.find((i) => i.id === issueId);
        if (issue)
          document.getElementById(`para-${issue.paragraph}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      });
    },
    [issues],
  );

  const handleAccept = useCallback(
    (issueId: string) => {
      setAccepted((prev) => new Set(prev).add(issueId));
      const issue = issues.find((i) => i.id === issueId);
      setToast(`Applied: ${issue?.title || 'change'}`);
      // Animate out after brief delay
      setTimeout(() => {
        setDismissed((prev) => new Set(prev).add(issueId));
        if (activeIssueId === issueId) setActiveIssueId(null);
      }, 400);
    },
    [issues, activeIssueId],
  );

  const handleDismiss = useCallback(
    (issueId: string) => {
      const issue = issues.find((i) => i.id === issueId);
      setToast(`Dismissed: ${issue?.title || 'issue'}`);
      setTimeout(() => {
        setDismissed((prev) => new Set(prev).add(issueId));
        if (activeIssueId === issueId) setActiveIssueId(null);
      }, 400);
    },
    [issues, activeIssueId],
  );

  if (error) return <ErrorState message={error} />;
  if (isLoading) return <LoadingSkeleton />;

  return (
    <div className="h-screen flex flex-col overflow-hidden" style={{ backgroundColor: S.surface }}>
      {/* Toast */}
      {toast && <AcceptedToast text={toast} onDone={() => setToast(null)} />}

      {/* Keyframe for toast */}
      <style>{`@keyframes fadeInUp { from { opacity: 0; transform: translate(-50%, 12px); } to { opacity: 1; transform: translate(-50%, 0); } }`}</style>

      {/* ── Top Bar ── */}
      <header
        className="flex items-center justify-between shrink-0"
        style={{
          height: '52px',
          backgroundColor: S.surfaceLowest,
          padding: '0 1.5rem',
          borderBottom: `1px solid rgba(196,198,207,0.1)`,
        }}
      >
        <div className="flex items-center gap-3 min-w-0 mr-4">
          <h1
            className="truncate"
            title={mockDocument.title}
            style={{
              fontFamily: "'Manrope', sans-serif",
              color: S.primary,
              fontSize: '0.9375rem',
              fontWeight: 700,
              letterSpacing: '-0.01em',
            }}
          >
            {mockDocument.title}
          </h1>
          <span
            style={{
              fontFamily: "'Inter', sans-serif",
              backgroundColor: S.surfaceHigh,
              color: S.onSurfaceVariant,
              fontSize: '0.6875rem',
              padding: '2px 8px',
              borderRadius: '4px',
              whiteSpace: 'nowrap',
            }}
          >
            Draft
          </span>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button
            className="hover:bg-[#f1f4f6] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#002045]"
            style={{
              fontFamily: "'Inter', sans-serif",
              color: S.primary,
              fontSize: '0.8125rem',
              fontWeight: 600,
              padding: '0.375rem 0.625rem',
              borderRadius: '4px',
              transition: 'background-color 150ms',
            }}
          >
            Share
          </button>
          <button
            className="hover:bg-[#f1f4f6] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#002045]"
            style={{
              fontFamily: "'Inter', sans-serif",
              color: S.primary,
              fontSize: '0.8125rem',
              fontWeight: 600,
              padding: '0.375rem 0.625rem',
              borderRadius: '4px',
              transition: 'background-color 150ms',
            }}
          >
            Export
          </button>
          <button
            className="hover:opacity-90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
            style={{
              background: `linear-gradient(135deg, ${S.primary}, ${S.primaryContainer})`,
              color: '#fff',
              fontFamily: "'Inter', sans-serif",
              fontSize: '0.6875rem',
              fontWeight: 700,
              padding: '0.375rem 0.75rem',
              borderRadius: '6px',
            }}
          >
            Re-analyze
          </button>
        </div>
      </header>

      {/* ── Two-Column Layout ── */}
      <div className="flex flex-1 min-h-0">
        {/* ── Document Panel (65%) — "Manuscript" per stitch ── */}
        <section
          className="overflow-y-auto"
          style={{ width: '65%', backgroundColor: S.surfaceLowest, padding: '2.5rem 2rem 2.5rem 3.5rem' }}
        >
          <div style={{ maxWidth: '660px', margin: '0 auto' }}>
            <div style={{ marginBottom: '2rem' }}>
              <h2
                style={{
                  fontFamily: "'Manrope', sans-serif",
                  color: S.primary,
                  fontSize: '1.625rem',
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
                  color: S.secondary,
                  fontSize: '0.9375rem',
                  fontStyle: 'italic',
                }}
              >
                {mockDocument.authors}
              </p>
              <p
                style={{
                  fontFamily: "'Inter', sans-serif",
                  color: S.onSurfaceVariant,
                  fontSize: '0.8125rem',
                  marginTop: '0.25rem',
                }}
              >
                {mockDocument.date}
              </p>
            </div>

            {/* Body paragraphs */}
            <div>
              {mockDocument.paragraphs.map((para) => {
                const paragraphIssues = visibleIssues.filter((i) => i.paragraph === para.id);
                const isHighlighted = activeIssueId ? paragraphIssues.some((i) => i.id === activeIssueId) : false;
                const activeIssue = activeIssueId ? paragraphIssues.find((i) => i.id === activeIssueId) : null;
                const sc = activeIssue
                  ? { critical: '#f43f5e', warning: '#f59e0b', suggestion: '#60a5fa' }[activeIssue.severity]
                  : '#f59e0b';
                const bg = isHighlighted
                  ? activeIssue?.severity === 'critical'
                    ? 'rgba(244,63,94,0.07)'
                    : activeIssue?.severity === 'suggestion'
                      ? 'rgba(96,165,250,0.07)'
                      : 'rgba(251,191,36,0.08)'
                  : 'transparent';

                return (
                  <div
                    key={para.id}
                    id={`para-${para.id}`}
                    className="relative"
                    style={{
                      backgroundColor: bg,
                      padding: isHighlighted ? '0.625rem 0.75rem' : '0.375rem 0',
                      marginBottom: '0.25rem',
                      borderRadius: '4px',
                      borderLeft: isHighlighted ? `3px solid ${sc}` : '3px solid transparent',
                      transition: 'background-color 200ms, padding 200ms',
                    }}
                  >
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
                        color: S.onSurface,
                        overflowWrap: 'break-word',
                      }}
                    >
                      <HighlightedText text={para.text} highlights={para.highlights} />
                    </p>
                  </div>
                );
              })}
            </div>

            <div className="mt-16 flex justify-center opacity-20">
              <div className="w-16 h-1 rounded-full" style={{ backgroundColor: S.primaryContainer }} />
            </div>
          </div>
        </section>

        {/* ── Issues Panel (35%) ── */}
        <aside className="flex flex-col overflow-hidden" style={{ width: '35%', backgroundColor: S.surfaceLow }}>
          {/* Header */}
          <div className="shrink-0" style={{ padding: '1rem 1rem 0.625rem' }}>
            <div className="flex items-center justify-between" style={{ marginBottom: '0.5rem' }}>
              <h3
                style={{
                  fontFamily: "'Manrope', sans-serif",
                  color: S.primary,
                  fontSize: '0.8125rem',
                  fontWeight: 700,
                }}
              >
                Review Findings
              </h3>
              <span
                style={{
                  fontFamily: "'Inter', sans-serif",
                  backgroundColor: S.surfaceHigh,
                  color: S.onSurfaceVariant,
                  fontSize: '0.6875rem',
                  padding: '2px 8px',
                  borderRadius: '10px',
                }}
              >
                {filter === 'all'
                  ? `${visibleIssues.length} issues`
                  : `${filteredIssues.length} of ${visibleIssues.length}`}
              </span>
            </div>

            {/* Severity counts */}
            <div
              className="flex items-center gap-3 flex-wrap"
              style={{ marginBottom: '0.5rem', fontSize: '0.6875rem', fontFamily: "'Inter', sans-serif" }}
            >
              <span className="flex items-center gap-1">
                <SeverityDot severity="critical" />
                <span style={{ color: S.onSurfaceVariant }}>{criticalCount}</span>
              </span>
              <span className="flex items-center gap-1">
                <SeverityDot severity="warning" />
                <span style={{ color: S.onSurfaceVariant }}>{warningCount}</span>
              </span>
              <span className="flex items-center gap-1">
                <SeverityDot severity="suggestion" />
                <span style={{ color: S.onSurfaceVariant }}>{suggestionCount}</span>
              </span>
              {accepted.size > 0 && (
                <span style={{ color: '#22c55e', fontWeight: 600 }}>✓ {accepted.size} applied</span>
              )}
            </div>

            {/* Filters */}
            <div className="flex flex-wrap gap-1" role="group" aria-label="Filter by category">
              <button
                onClick={() => setFilter('all')}
                aria-pressed={filter === 'all'}
                className="focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-[#002045]"
                style={{
                  fontFamily: "'Inter', sans-serif",
                  fontSize: '0.625rem',
                  fontWeight: 500,
                  padding: '3px 8px',
                  borderRadius: '4px',
                  backgroundColor: filter === 'all' ? S.primary : S.surfaceHigh,
                  color: filter === 'all' ? '#fff' : S.onSurfaceVariant,
                  transition: 'background-color 150ms',
                  whiteSpace: 'nowrap',
                }}
              >
                All
              </button>
              {categories.map((cat) => {
                const count = visibleIssues.filter((i) => i.category === cat).length;
                return (
                  <button
                    key={cat}
                    onClick={() => setFilter(cat === filter ? 'all' : cat)}
                    aria-pressed={filter === cat}
                    className="focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-[#002045]"
                    style={{
                      fontFamily: "'Inter', sans-serif",
                      fontSize: '0.625rem',
                      fontWeight: 500,
                      padding: '3px 8px',
                      borderRadius: '4px',
                      backgroundColor: filter === cat ? S.primary : S.surfaceHigh,
                      color: filter === cat ? '#fff' : S.onSurfaceVariant,
                      transition: 'background-color 150ms',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {categoryLabels[cat]} ({count})
                  </button>
                );
              })}
            </div>
          </div>

          {/* Cards — stitch: no dividers, spacing only */}
          <div
            ref={issuesPanelRef}
            className="flex-1 overflow-y-auto overflow-x-hidden"
            style={{ padding: '0 1rem 1rem' }}
          >
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.625rem' }}>
              {filteredIssues.length === 0 && (
                <div style={{ padding: '2rem 0', textAlign: 'center' }}>
                  <p style={{ fontFamily: "'Newsreader', serif", color: S.secondary, fontSize: '0.875rem' }}>
                    {visibleIssues.length === 0
                      ? 'All issues have been resolved.'
                      : 'No issues match the selected filter.'}
                  </p>
                  {visibleIssues.length > 0 && (
                    <button
                      onClick={() => setFilter('all')}
                      style={{
                        fontFamily: "'Inter', sans-serif",
                        color: S.primary,
                        fontSize: '0.75rem',
                        fontWeight: 600,
                        marginTop: '0.5rem',
                      }}
                      className="focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#002045]"
                    >
                      Clear filter
                    </button>
                  )}
                </div>
              )}
              {filteredIssues.map((issue) => (
                <div
                  key={issue.id}
                  style={{
                    opacity: accepted.has(issue.id) ? 0.4 : 1,
                    transform: accepted.has(issue.id) ? 'scale(0.98)' : 'scale(1)',
                    transition: 'opacity 300ms, transform 300ms',
                  }}
                >
                  <IssueCard
                    issue={issue}
                    isActive={activeIssueId === issue.id}
                    onClick={() => selectIssue(issue.id === activeIssueId ? null : issue.id)}
                    onAccept={() => handleAccept(issue.id)}
                    onDismiss={() => handleDismiss(issue.id)}
                  />
                </div>
              ))}
            </div>
          </div>

          {/* AI footer */}
          <div className="shrink-0" style={{ padding: '0.5rem 1rem 1rem' }}>
            <div
              style={{
                backgroundColor: S.primaryContainer,
                borderRadius: '6px',
                padding: '0.5rem 0.75rem',
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
              }}
            >
              <span
                style={{
                  color: S.primaryFixed,
                  fontSize: '0.625rem',
                  fontFamily: "'Inter', sans-serif",
                  fontWeight: 600,
                }}
              >
                AI Review Engine
              </span>
              <span style={{ color: S.primaryFixedDim, fontSize: '0.625rem', fontFamily: "'Inter', sans-serif" }}>
                · {visibleIssues.length} findings
              </span>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}
